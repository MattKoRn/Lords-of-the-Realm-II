#!/usr/bin/env python3
from __future__ import annotations

import curses
import json
import math
import time
from dataclasses import asdict, dataclass, field

import autonomous_mode as auto
import combat_stats
import dynasty_ascendant as asc
import flicker_free
import game_core as g
import kingdom_evolved as evolved
import neural_30s
import neural_reign as reign
import sovereign_mind as mind

D = g.D
STATE_FILE = g.SAVE_DIR / 'imperial_mind_v7.json'
POLICY_INTERVAL = 180.0
POLICIES = {
    'Balanced Realm': {'gold': D(0), 'food': D(0), 'research': D(0), 'power': D(0)},
    'Emergency Rations': {'gold': D('-.05'), 'food': D('.18'), 'research': D('-.05'), 'power': D(0)},
    'Public Works': {'gold': D('-.06'), 'food': D('.05'), 'research': D('.08'), 'power': D(0)},
    'War Economy': {'gold': D('-.08'), 'food': D('-.05'), 'research': D(0), 'power': D('.16')},
    'Open Markets': {'gold': D('.15'), 'food': D('-.03'), 'research': D('.03'), 'power': D(0)},
    'Royal Academy': {'gold': D('-.08'), 'food': D(0), 'research': D('.20'), 'power': D('-.03')},
}


@dataclass
class ImperialState:
    version: int = 7
    last_saved: float = field(default_factory=time.time)
    policy: str = 'Balanced Realm'
    policy_time: float = 0.0
    decisions: list[dict] = field(default_factory=list)
    battle_readiness: str = '0'
    recommended_unit: str = 'soldier'
    expected_loss: str = '0'
    camera_event: str = 'Watching the realm.'
    camera_event_time: float = 0.0
    policy_changes: int = 0
    crises_managed: int = 0


def load_state():
    try:
        raw = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        allowed = ImperialState.__dataclass_fields__
        state = ImperialState(**{k: v for k, v in raw.items() if k in allowed})
        if state.policy not in POLICIES:
            state.policy = 'Balanced Realm'
        state.policy_time = max(0.0, min(POLICY_INTERVAL, float(state.policy_time)))
        state.camera_event_time = max(0.0, min(120.0, float(state.camera_event_time)))
        state.decisions = [x for x in state.decisions[-12:] if isinstance(x, dict)]
        state.policy_changes = max(0, int(state.policy_changes))
        state.crises_managed = max(0, int(state.crises_managed))
        state.battle_readiness = str(max(D(0), D(state.battle_readiness)))
        state.expected_loss = str(max(D(0), min(D(100), D(state.expected_loss))))
        if state.recommended_unit not in ('soldier', 'archer', 'knight'):
            state.recommended_unit = 'soldier'
        return state
    except (OSError, ValueError, TypeError, ArithmeticError, json.JSONDecodeError):
        return ImperialState()


def save_state(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(STATE_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


def enemy_composition(realm):
    army = combat_stats.enemy_army(realm, variance=False)
    total = max(D(1), sum(army.values(), D(0)))
    return {unit: army[unit] / total for unit in army}


def recommended_counter(realm):
    composition = enemy_composition(realm)
    dominant = max(composition, key=composition.get)
    return {'soldiers': 'soldier', 'archers': 'knight', 'knights': 'soldier'}[dominant]


def battle_readiness(realm):
    own = realm.military_power()
    enemy = max(D(1), g.enemy_power(realm))
    return max(D(0), own * D(100) / enemy)


def estimated_loss_percent(realm):
    readiness = battle_readiness(realm)
    if readiness >= D(180):
        return D(12)
    if readiness >= D(130):
        return D(24)
    if readiness >= D(100):
        return D(38)
    if readiness >= D(80):
        return D(55)
    return D(75)


def select_policy(game):
    r = game.r
    food_buffer = r.food / max(D(1), r.population)
    readiness = battle_readiness(r)
    if game.asc.disaster or food_buffer < D(8):
        return 'Emergency Rations'
    if readiness < D(85) or r.threat > r.territory * D(2):
        return 'War Economy'
    if len(game.world.unlocked) < len(evolved.TECHS) and game.world.research_value < D(25000):
        return 'Royal Academy'
    if r.gold < r.population * D(12):
        return 'Open Markets'
    if r.builders < max(D(2), r.population / D(100)):
        return 'Public Works'
    return 'Balanced Realm'


def policy_bonus(state, category):
    return POLICIES.get(state.policy, POLICIES['Balanced Realm']).get(category, D(0))


def improved_actions(game):
    allowed = asc.valid_actions(game)
    readiness = battle_readiness(game.r)
    expected_loss = estimated_loss_percent(game.r)
    if readiness < D(90) or expected_loss > D(55) or game.asc.disaster:
        allowed.discard('attack')
    return allowed


def composition_utility(game, action):
    recommended = game.imperial.recommended_unit
    utility = 0.0
    if action == recommended:
        utility += 2.4
    if action == 'barracks' and game.r.barracks < max(D(1), game.r.population / D(300)):
        utility += 1.2
    readiness = battle_readiness(game.r)
    if action == 'attack':
        if readiness >= D(150): utility += 3.0
        elif readiness >= D(110): utility += 1.0
        else: utility -= 5.0
    if game.imperial.policy == 'Emergency Rations' and action in ('farmer', 'farm', 'tax_down'):
        utility += 1.8
    elif game.imperial.policy == 'War Economy' and action in ('soldier', 'archer', 'knight', 'wall', 'castle'):
        utility += 1.6
    elif game.imperial.policy == 'Open Markets' and action in ('market', 'tax_up'):
        utility += 1.5
    elif game.imperial.policy == 'Royal Academy' and action in ('builder', 'market', 'mine'):
        utility += 1.4
    return utility


def choose_imperial_action(game, allowed):
    raw = mind.neural_scores(game.ai, game.r)
    scored = []
    for index, action in enumerate(game.ai.ACTIONS):
        if action not in allowed:
            continue
        gain, risk = mind.simulate_action(game, action)
        score = (
            raw[index]
            + game.ai.context_utility(game, action)
            + mind.directive_bonus(game.sovereign.directive, action)
            + composition_utility(game, action)
            + gain * 2.0
            - risk * 4.5
        )
        scored.append((score, gain, risk, action))
    if not scored:
        return 'wait', []
    scored.sort(reverse=True)
    return scored[0][3], scored


def record_decision(state, game, action, ranking):
    score = ranking[0][0] if ranking else 0.0
    state.decisions.append({
        'action': action,
        'policy': state.policy,
        'directive': game.sovereign.directive,
        'score': round(float(score), 3),
        'readiness': str(battle_readiness(game.r)),
    })
    state.decisions = state.decisions[-12:]


class Game(flicker_free.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.imperial = load_state()
        self.last_imperial_save = time.monotonic()
        self.last_real_battle_result = combat_stats.LAST_BATTLE['result']
        self.r.log('Imperial Mind strategic systems activated.')

    def ai_action(self):
        try:
            self.sovereign.directive = mind.select_directive(self)
            self.sovereign.directive_age = 0.0
            self.imperial.recommended_unit = recommended_counter(self.r)
            self.imperial.battle_readiness = str(battle_readiness(self.r))
            self.imperial.expected_loss = str(estimated_loss_percent(self.r))
            allowed = improved_actions(self)
            action, ranking = choose_imperial_action(self, allowed)

            self.ai.last_action = action
            self.ai.decisions += 1
            self.ai.action_counts[action] += 1
            self.ai.usage_memory[action] += 1
            self.ai.cooldowns[action] = 2 if action not in ('wait', 'tax_up', 'tax_down') else 1
            margin = ranking[0][0] - ranking[1][0] if len(ranking) > 1 else 3.0
            self.ai.confidence = max(0.0, min(1.0, .5 + margin / 6))
            self.ai.reason = (
                f'{self.imperial.policy}; counter {self.imperial.recommended_unit}; '
                f'readiness {self.imperial.battle_readiness}%.'
            )
            record_decision(self.imperial, self, action, ranking)
            self.forecast_baseline = g.realm_worth(self.r)
            self.forecast_age = 0.0
            self.forecast_pending = True
            auto.execute(self.ai, self.r, action)

            if self.camera_enabled:
                self.camera_plan = self.build_camera_plan(action)
                if action == 'attack':
                    self.camera_plan = [
                        (0.0, 'Command', 0, 'Campaign authorised by the neural governor'),
                        (4.0, 'Military', 0, 'Reviewing army composition'),
                        (10.0, 'Military', 1, 'Following the battle report'),
                        (22.0, 'Neural', 0, 'Reviewing campaign consequences'),
                        (27.0, 'Command', 0, 'Preparing the next deliberation'),
                    ]
                self.camera_started = time.monotonic()
                self.camera_phase = -1
                self.apply_camera(force=True)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Imperial decision rejected: {exc}'[:160]

    def apply_policy_effects(self, dt):
        rates = self.r.rates()
        for resource in ('gold', 'food'):
            bonus = policy_bonus(self.imperial, resource)
            if bonus:
                value = getattr(self.r, resource) + rates[resource] * bonus * D(dt)
                setattr(self.r, resource, max(D(0), value))
        research = policy_bonus(self.imperial, 'research')
        if research:
            base = self.r.builders * D('.03') + self.r.markets * D('.02') + D('.01')
            self.world.research_value += max(D(0), base * research * D(dt))
        power = policy_bonus(self.imperial, 'power')
        if power:
            self.r.renown += self.r.military_power() * power * D(dt) * D('.00005')

    def update(self):
        now = time.monotonic()
        previous = self.last_tick
        super().update()
        dt = max(0.0, min(1.0, now - previous))
        if not self.paused:
            self.imperial.policy_time += dt
            if self.imperial.policy_time >= POLICY_INTERVAL:
                old = self.imperial.policy
                self.imperial.policy = select_policy(self)
                self.imperial.policy_time = 0.0
                if self.imperial.policy != old:
                    self.imperial.policy_changes += 1
                    self.r.log(f'Imperial policy changed: {self.imperial.policy}.')
            self.apply_policy_effects(dt)
            self.imperial.recommended_unit = recommended_counter(self.r)
            self.imperial.battle_readiness = str(battle_readiness(self.r))
            self.imperial.expected_loss = str(estimated_loss_percent(self.r))

            result = combat_stats.LAST_BATTLE['result']
            if result != self.last_real_battle_result and result != 'No battle fought yet.':
                self.last_real_battle_result = result
                self.imperial.camera_event = f'Battle concluded: {result}'
                self.imperial.camera_event_time = 20.0
            self.imperial.camera_event_time = max(0.0, self.imperial.camera_event_time - dt)

        if now - self.last_imperial_save >= 5:
            save_state(self.imperial)
            self.last_imperial_save = now

    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 20 or w < 80:
            return

        tab = self.TABS[self.tab]
        if tab == 'Neural':
            start = 15
            self.add(start, 3, 'IMPERIAL STRATEGY', curses.A_BOLD)
            self.add(start + 1, 3, f'Policy: {self.imperial.policy}')
            self.add(start + 2, 3, f'Recommended recruit: {self.imperial.recommended_unit}')
            self.add(start + 3, 3, f'Battle readiness: {self.imperial.battle_readiness}%')
            self.add(start + 4, 3, f'Expected casualties: {self.imperial.expected_loss}%')
            if self.imperial.decisions:
                latest = self.imperial.decisions[-1]
                self.add(start + 6, 3, f"Last strategic choice: {latest['action']} under {latest['policy']}")
        elif tab == 'Military' and self.sub == 0:
            composition = enemy_composition(self.r)
            row = 15
            self.add(row, 2, 'ENEMY COMPOSITION', curses.A_BOLD)
            self.add(row + 1, 2, f"Soldiers {composition['soldiers'] * D(100)}% | Archers {composition['archers'] * D(100)}% | Knights {composition['knights'] * D(100)}%")
            self.add(row + 2, 2, f'Neural counter recommendation: {self.imperial.recommended_unit}')
            self.add(row + 3, 2, f'Estimated friendly casualties if attacking: {self.imperial.expected_loss}%')

        status = (
            f' Policy {self.imperial.policy} | Counter {self.imperial.recommended_unit} | '
            f'Readiness {self.imperial.battle_readiness}% | Loss {self.imperial.expected_loss}% '
        )
        self.add(h - 6, 0, status[:w - 1].ljust(w - 1), curses.A_BOLD)
        self.s.refresh()

    def save_all(self):
        super().save_all()
        save_state(self.imperial)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
