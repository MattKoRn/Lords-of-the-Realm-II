#!/usr/bin/env python3
from __future__ import annotations

import copy
import curses
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field

import autonomous_mode as auto
import dynasty_ascendant as asc
import game_core as g
import kingdom_evolved as evolved
import neural_30s
import neural_reign as reign
import neural_reign_launch  # Applies hardened loaders.

D = g.D
STATE_FILE = g.SAVE_DIR / 'sovereign_mind_v6.json'
LOOKAHEAD_SECONDS = 30

DIRECTIVES = ['Survive', 'Prosper', 'Fortify', 'Expand', 'Innovate', 'Unify']
INTELLIGENCE_EVENTS = [
    'Rival levies are gathering near the frontier.',
    'Merchants report strong demand for iron.',
    'Village elders expect pressure on food reserves.',
    'Court agents report improving public confidence.',
    'Surveyors identify promising land beyond the marches.',
    'Scholars predict a productive research cycle.',
]


@dataclass
class SovereignState:
    version: int = 6
    last_saved: float = field(default_factory=time.time)
    directive: str = 'Survive'
    directive_age: float = 0.0
    peasants_influence: str = '45'
    burghers_influence: str = '20'
    nobles_influence: str = '25'
    clergy_influence: str = '10'
    intelligence: list[str] = field(default_factory=lambda: ['The intelligence council is forming its first assessment.'])
    next_intelligence: float = 90.0
    forecast_action: str = 'wait'
    forecast_gain: float = 0.0
    forecast_risk: float = 0.0
    alternatives: list[str] = field(default_factory=list)
    deliberations: int = 0
    successful_forecasts: int = 0
    failed_forecasts: int = 0
    last_predecision_worth: str = '0'


def load_state():
    try:
        raw = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        allowed = SovereignState.__dataclass_fields__
        state = SovereignState(**{k: v for k, v in raw.items() if k in allowed})
        state.directive = state.directive if state.directive in DIRECTIVES else 'Survive'
        state.directive_age = max(0.0, min(3600.0, float(state.directive_age)))
        state.next_intelligence = max(1.0, min(600.0, float(state.next_intelligence)))
        state.intelligence = [str(x)[:240] for x in state.intelligence[-40:]]
        state.alternatives = [str(x)[:80] for x in state.alternatives[:5]]
        state.deliberations = max(0, int(state.deliberations))
        state.successful_forecasts = max(0, int(state.successful_forecasts))
        state.failed_forecasts = max(0, int(state.failed_forecasts))
        for name in ('peasants_influence', 'burghers_influence', 'nobles_influence', 'clergy_influence'):
            value = max(D(0), min(D(100), D(getattr(state, name))))
            setattr(state, name, str(value))
        state.forecast_gain = float(state.forecast_gain) if math.isfinite(float(state.forecast_gain)) else 0.0
        state.forecast_risk = max(0.0, min(1.0, float(state.forecast_risk)))
        return state
    except (OSError, ValueError, TypeError, ArithmeticError, json.JSONDecodeError):
        return SovereignState()


def save_state(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(STATE_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


def estate_values(state):
    return {
        'Peasants': D(state.peasants_influence),
        'Burghers': D(state.burghers_influence),
        'Nobles': D(state.nobles_influence),
        'Clergy': D(state.clergy_influence),
    }


def normalize_estates(state):
    values = estate_values(state)
    total = sum(values.values(), D(0))
    if total <= 0:
        values = {'Peasants': D(45), 'Burghers': D(20), 'Nobles': D(25), 'Clergy': D(10)}
        total = D(100)
    for key, value in values.items():
        normalized = value * D(100) / total
        setattr(state, key.lower() + '_influence', str(normalized))


def update_estates(state, game, dt):
    r = game.r
    peasants = D(state.peasants_influence)
    burghers = D(state.burghers_influence)
    nobles = D(state.nobles_influence)
    clergy = D(state.clergy_influence)

    peasants += (r.happiness - D(50)) * D('.0004') * D(dt)
    burghers += g.decimal_log_feature(r.gold + D(1)) * D('.004') * D(dt)
    nobles += g.decimal_log_feature(r.military_power() + D(1)) * D('.003') * D(dt)
    clergy += (D(100) - abs(r.happiness - D(65))) * D('.00008') * D(dt)

    state.peasants_influence = str(max(D(1), peasants))
    state.burghers_influence = str(max(D(1), burghers))
    state.nobles_influence = str(max(D(1), nobles))
    state.clergy_influence = str(max(D(1), clergy))
    normalize_estates(state)


def select_directive(game):
    r = game.r
    food_days = r.food / max(D(1), r.population * D('.08'))
    power_ratio = r.military_power() / max(D(1), g.enemy_power(r))
    if game.asc.disaster or food_days < D(45) or r.happiness < D(30):
        return 'Survive'
    if power_ratio < D('.8'):
        return 'Fortify'
    if g.realm_worth(r) >= g.prestige_requirement(r):
        return 'Unify'
    if game.world.research_value < D(25000) and len(game.world.unlocked) < len(evolved.TECHS):
        return 'Innovate'
    if r.territory < r.population / D(20):
        return 'Expand'
    return 'Prosper'


def directive_bonus(directive, action):
    groups = {
        'Survive': {'wait', 'farmer', 'farm', 'tax_down', 'wall'},
        'Prosper': {'market', 'tax_up', 'woodcutter', 'miner', 'wait'},
        'Fortify': {'soldier', 'archer', 'knight', 'barracks', 'wall', 'castle'},
        'Expand': {'attack', 'soldier', 'archer', 'knight'},
        'Innovate': {'builder', 'market', 'mine', 'quarry'},
        'Unify': {'prestige', 'wait', 'tax_down'},
    }
    return 1.5 if action in groups.get(directive, set()) else 0.0


def projected_score(realm):
    worth = g.decimal_log_feature(g.realm_worth(realm) + D(1)) * 10
    food_security = float(min(D(4), realm.food / max(D(1), realm.population * D(8))))
    happiness = float(realm.happiness / D(20))
    power = g.decimal_log_feature(realm.military_power() + D(1)) * 3
    threat_penalty = g.decimal_log_feature(realm.threat + D(1)) * 1.5
    return worth + food_security + happiness + power - threat_penalty


def simulate_action(game, action):
    simulated = copy.deepcopy(game.r)
    before = projected_score(simulated)
    try:
        auto.execute(game.ai, simulated, action)
        simulated.tick(LOOKAHEAD_SECONDS)
        after = projected_score(simulated)
        food_ratio = simulated.food / max(D(1), simulated.population * D(5))
        military_ratio = simulated.military_power() / max(D(1), g.enemy_power(simulated))
        risk = 0.0
        if food_ratio < D(1): risk += 0.45
        if simulated.happiness < D(25): risk += 0.30
        if military_ratio < D('.5'): risk += 0.20
        if simulated.gold <= 0: risk += 0.10
        return after - before, min(1.0, risk)
    except (ArithmeticError, ValueError, TypeError, KeyError):
        return -100.0, 1.0


def neural_scores(ai, realm):
    x = ai.features(realm)
    hidden = [math.tanh(sum(w * v for w, v in zip(row, x))) for row in ai.w1]
    return [sum(w * v for w, v in zip(row, hidden)) for row in ai.w2]


def deliberate(game, allowed):
    raw = neural_scores(game.ai, game.r)
    candidates = []
    for index, action in enumerate(game.ai.ACTIONS):
        if action not in allowed:
            continue
        gain, risk = simulate_action(game, action)
        utility = (
            raw[index]
            + game.ai.context_utility(game, action)
            + directive_bonus(game.sovereign.directive, action)
            + gain * 1.8
            - risk * 4.0
        )
        candidates.append((utility, gain, risk, action))
    if not candidates:
        return 'wait', []
    candidates.sort(reverse=True)
    best = candidates[0]
    game.sovereign.forecast_action = best[3]
    game.sovereign.forecast_gain = best[1]
    game.sovereign.forecast_risk = best[2]
    game.sovereign.alternatives = [f'{a}: {u:+.2f}' for u, _, _, a in candidates[1:5]]
    game.sovereign.deliberations += 1
    return best[3], candidates


def update_intelligence(state, game, dt):
    state.next_intelligence -= dt
    if state.next_intelligence > 0:
        return
    report = random.choice(INTELLIGENCE_EVENTS)
    if game.asc.disaster:
        report = f'Agents confirm the {game.asc.disaster.lower()} remains the realm\'s greatest immediate risk.'
    elif game.r.military_power() < g.enemy_power(game.r):
        report = 'Military intelligence warns that enemy strength currently exceeds royal forces.'
    elif game.r.food < game.r.population * D(10):
        report = 'Granary reports show food reserves below the preferred strategic buffer.'
    state.intelligence.append(report)
    state.intelligence = state.intelligence[-40:]
    state.next_intelligence = random.uniform(75, 135)
    game.r.log('Intelligence: ' + report)


class Game(neural_30s.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.sovereign = load_state()
        self.last_sovereign_save = time.monotonic()
        self.r.log('Sovereign Mind planning systems activated.')

    def ai_action(self):
        try:
            self.sovereign.directive = select_directive(self)
            self.sovereign.directive_age = 0.0
            allowed = asc.valid_actions(self)
            previous_worth = g.realm_worth(self.r)
            action, ranking = deliberate(self, allowed)
            self.ai.last_action = action
            self.ai.decisions += 1
            self.ai.action_counts[action] += 1
            self.ai.usage_memory[action] += 1
            self.ai.cooldowns[action] = 2 if action not in ('wait', 'tax_up', 'tax_down') else 1
            self.ai.confidence = 1.0 if len(ranking) < 2 else max(0.0, min(1.0, .5 + (ranking[0][0] - ranking[1][0]) / 6))
            self.ai.reason = f'{self.sovereign.directive} directive; forecast {self.sovereign.forecast_gain:+.2f}; risk {self.sovereign.forecast_risk:.0%}.'
            auto.execute(self.ai, self.r, action)
            self.sovereign.last_predecision_worth = str(previous_worth)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Sovereign deliberation rejected: {exc}'[:160]

    def update(self):
        before = time.monotonic()
        prior_worth = D(self.sovereign.last_predecision_worth or '0')
        super().update()
        now = time.monotonic()
        dt = max(0.0, min(1.0, now - before))
        if not self.paused:
            self.sovereign.directive_age += dt
            update_estates(self.sovereign, self, dt)
            update_intelligence(self.sovereign, self, dt)
            if prior_worth > 0 and self.sovereign.last_predecision_worth != '0':
                current = g.realm_worth(self.r)
                if current >= prior_worth:
                    self.sovereign.successful_forecasts += 1
                else:
                    self.sovereign.failed_forecasts += 1
                self.sovereign.last_predecision_worth = '0'
        if now - self.last_sovereign_save >= 5:
            save_state(self.sovereign)
            self.last_sovereign_save = now

    def header(self):
        super().header()
        h, w = self.s.getmaxyx()
        if h >= 9 and w >= 60:
            self.add(
                6,
                0,
                f' Directive {self.sovereign.directive} | Forecast {self.sovereign.forecast_action} {self.sovereign.forecast_gain:+.2f} | Risk {self.sovereign.forecast_risk:.0%} '[:w - 1],
                curses.A_BOLD,
            )

    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 12 or w < 60:
            return
        estates = estate_values(self.sovereign)
        line = ' | '.join(f'{name} {value:.0f}%' for name, value in estates.items())
        self.add(h - 3, 0, f' Estates: {line} '[:w - 1].ljust(w - 1), curses.A_DIM)
        self.s.refresh()

    def run(self):
        try:
            super().run()
        finally:
            save_state(self.sovereign)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
