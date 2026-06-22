from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

import adaptive_core as adaptive
import game_core as g
import imperial_mind as imperial

D = g.D
STATE_FILE = g.SAVE_DIR / 'grand_strategy_v9.json'

OBJECTIVES = (
    'Secure Food',
    'Build Treasury',
    'Fortify Frontier',
    'Modernize Army',
    'Expand Realm',
    'Pursue Prestige',
)


@dataclass
class GrandState:
    version: int = 9
    last_saved: float = field(default_factory=time.time)
    objective: str = 'Secure Food'
    objective_progress: str = '0'
    objectives_completed: int = 0
    marshal_level: int = 1
    quartermaster_level: int = 1
    strategist_level: int = 1
    war_weariness: str = '0'
    camera_mode: str = 'Cinematic'
    last_explanation: str = 'The strategic council is assessing the realm.'
    last_battle_count: int = 0
    major_events: list[str] = field(default_factory=list)


def load_state():
    try:
        raw = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        allowed = GrandState.__dataclass_fields__
        state = GrandState(**{k: v for k, v in raw.items() if k in allowed})
        state.objective = state.objective if state.objective in OBJECTIVES else 'Secure Food'
        state.objective_progress = str(max(D(0), min(D(100), D(state.objective_progress))))
        state.war_weariness = str(max(D(0), min(D(100), D(state.war_weariness))))
        state.objectives_completed = max(0, int(state.objectives_completed))
        state.marshal_level = max(1, min(1000, int(state.marshal_level)))
        state.quartermaster_level = max(1, min(1000, int(state.quartermaster_level)))
        state.strategist_level = max(1, min(1000, int(state.strategist_level)))
        state.last_battle_count = max(0, int(state.last_battle_count))
        state.major_events = [str(x)[:180] for x in state.major_events[-20:]]
        state.last_explanation = str(state.last_explanation)[:240]
        return state
    except (OSError, ValueError, TypeError, ArithmeticError, json.JSONDecodeError):
        return GrandState()


def save_state(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(STATE_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


def choose_objective(game):
    r = game.r
    food_per_person = r.food / max(D(1), r.population)
    readiness = adaptive.adjusted_readiness(game.adaptive, r)
    if food_per_person < D(12):
        return 'Secure Food'
    if r.gold < r.population * D(20):
        return 'Build Treasury'
    if r.walls + r.castles < max(D(2), r.territory / D(5)):
        return 'Fortify Frontier'
    if readiness < D(115):
        return 'Modernize Army'
    if g.realm_worth(r) >= g.prestige_requirement(r):
        return 'Pursue Prestige'
    return 'Expand Realm'


def objective_progress(game):
    r = game.r
    objective = game.grand.objective
    if objective == 'Secure Food':
        return min(D(100), r.food * D(100) / max(D(1), r.population * D(20)))
    if objective == 'Build Treasury':
        return min(D(100), r.gold * D(100) / max(D(1), r.population * D(40)))
    if objective == 'Fortify Frontier':
        target = max(D(2), r.territory / D(5))
        return min(D(100), (r.walls + r.castles) * D(100) / target)
    if objective == 'Modernize Army':
        return min(D(100), adaptive.adjusted_readiness(game.adaptive, r) * D(100) / D(130))
    if objective == 'Expand Realm':
        return min(D(100), r.territory * D(4))
    if objective == 'Pursue Prestige':
        return min(D(100), g.realm_worth(r) * D(100) / max(D(1), g.prestige_requirement(r)))
    return D(0)


def objective_utility(objective, action):
    groups = {
        'Secure Food': {'farmer', 'farm', 'tax_down', 'wait'},
        'Build Treasury': {'market', 'tax_up', 'woodcutter', 'miner'},
        'Fortify Frontier': {'wall', 'castle', 'builder', 'quarry'},
        'Modernize Army': {'soldier', 'archer', 'knight', 'barracks'},
        'Expand Realm': {'attack', 'soldier', 'archer', 'knight'},
        'Pursue Prestige': {'prestige', 'market', 'wait'},
    }
    return 2.0 if action in groups.get(objective, set()) else 0.0


def commander_bonus(state):
    marshal = D(state.marshal_level).sqrt() * D('.015')
    strategist = D(state.strategist_level).sqrt() * D('.010')
    return min(D('.25'), marshal + strategist)


def logistics_efficiency(state):
    return min(D('.35'), D(state.quartermaster_level).sqrt() * D('.018'))


def update_weariness(state, adaptive_state, dt):
    fatigue = D(adaptive_state.fatigue)
    supply = D(adaptive_state.supply)
    change = fatigue * D('.0008') * D(dt)
    if supply < D(30):
        change += D('.025') * D(dt)
    if fatigue < D(20) and supply > D(70):
        change -= D('.020') * D(dt)
    state.war_weariness = str(max(D(0), min(D(100), D(state.war_weariness) + change)))


def learn_commanders(state, adaptive_state):
    if adaptive_state.battles_observed <= state.last_battle_count:
        return False
    victories = adaptive_state.battles_observed - state.last_battle_count
    state.last_battle_count = adaptive_state.battles_observed
    state.marshal_level += victories
    state.strategist_level += 1
    if D(adaptive_state.supply) >= D(50):
        state.quartermaster_level += 1
    return True


def explanation(game, action, score, risk):
    return (
        f'{action} selected for {game.grand.objective}; score {score:+.2f}; '
        f'risk {risk:.0%}; supply {game.adaptive.supply}%; '
        f'fatigue {game.adaptive.fatigue}%.'
    )
