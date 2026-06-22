from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

import combat_stats
import game_core as g
import imperial_mind as imperial

D = g.D
STATE_FILE = g.SAVE_DIR / 'adaptive_empire_v8.json'

FORMATIONS = {
    'Balanced Line': (D(1), D(1)),
    'Shield Wall': (D('.88'), D('1.22')),
    'Arrow Screen': (D('1.12'), D('.92')),
    'Cavalry Hammer': (D('1.20'), D('.84')),
    'Orderly Retreat': (D('.72'), D('1.08')),
}


@dataclass
class AdaptiveState:
    version: int = 8
    last_saved: float = field(default_factory=time.time)
    soldier_experience: str = '0'
    archer_experience: str = '0'
    knight_experience: str = '0'
    fatigue: str = '0'
    supply: str = '100'
    formation: str = 'Balanced Line'
    battles_observed: int = 0
    units_lost: str = '0'
    units_defeated: str = '0'
    last_lesson: str = 'No battle lesson recorded.'
    last_battle_signature: str = ''


def load_state():
    try:
        raw = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        allowed = AdaptiveState.__dataclass_fields__
        state = AdaptiveState(**{k: v for k, v in raw.items() if k in allowed})
        for name in ('soldier_experience', 'archer_experience', 'knight_experience', 'units_lost', 'units_defeated'):
            setattr(state, name, str(max(D(0), D(getattr(state, name)))))
        state.fatigue = str(max(D(0), min(D(100), D(state.fatigue))))
        state.supply = str(max(D(0), min(D(100), D(state.supply))))
        state.formation = state.formation if state.formation in FORMATIONS else 'Balanced Line'
        state.battles_observed = max(0, int(state.battles_observed))
        state.last_lesson = str(state.last_lesson)[:240]
        state.last_battle_signature = str(state.last_battle_signature)[:120]
        return state
    except (OSError, ValueError, TypeError, ArithmeticError, json.JSONDecodeError):
        return AdaptiveState()


def save_state(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(STATE_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


def xp(state, unit):
    return D(getattr(state, unit.rstrip('s') + '_experience'))


def veteran_bonus(state, unit):
    value = xp(state, unit)
    return min(D('.35'), value.sqrt() / D(250)) if value > 0 else D(0)


def average_veterancy(state, realm):
    counts = {u: getattr(realm, u) for u in combat_stats.UNIT_STATS}
    total = sum(counts.values(), D(0))
    if total <= 0:
        return D(0)
    weighted = sum((counts[u] * veteran_bonus(state, u) for u in counts), D(0))
    return weighted * D(100) / total


def choose_formation(state, realm):
    enemy = imperial.enemy_composition(realm)
    readiness = imperial.battle_readiness(realm)
    if D(state.fatigue) >= D(70) or D(state.supply) <= D(25) or readiness < D(75):
        return 'Orderly Retreat'
    if enemy['knights'] >= D('.30'):
        return 'Shield Wall'
    if enemy['soldiers'] >= D('.50') and realm.archers > 0:
        return 'Arrow Screen'
    if enemy['archers'] >= D('.35') and realm.knights > 0:
        return 'Cavalry Hammer'
    return 'Balanced Line'


def logistics_tick(state, realm, dt):
    dt = D(dt)
    troops = realm.soldiers + realm.archers + realm.knights
    food_cost = troops * D('.004') * dt
    iron_cost = (realm.soldiers + realm.knights * D(3)) * D('.00035') * dt
    if realm.food >= food_cost and realm.iron >= iron_cost:
        realm.food -= food_cost
        realm.iron -= iron_cost
        state.supply = str(min(D(100), D(state.supply) + D('.10') * dt))
    else:
        state.supply = str(max(D(0), D(state.supply) - D('.35') * dt))
    recovery = D('.10') if D(state.supply) >= D(50) else D('.03')
    state.fatigue = str(max(D(0), D(state.fatigue) - recovery * dt))


def adjusted_readiness(state, realm):
    base = imperial.battle_readiness(realm)
    veteran = average_veterancy(state, realm)
    fatigue = D(state.fatigue)
    supply = D(state.supply)
    defence = FORMATIONS[state.formation][1]
    modifier = D(1) + veteran / D(100) - fatigue / D(180) + (supply - D(50)) / D(500)
    return max(D(0), base * modifier * defence)


def learn_from_last_battle(state, realm):
    report = combat_stats.LAST_BATTLE
    signature = '|'.join([
        str(report['result']), str(report['rounds']),
        *(str(report['friendly_losses'][u]) for u in combat_stats.UNIT_STATS),
        *(str(report['enemy_losses'][u]) for u in combat_stats.UNIT_STATS),
    ])
    if report['result'] == 'No battle fought yet.' or signature == state.last_battle_signature:
        return False
    state.last_battle_signature = signature
    state.battles_observed += 1
    friendly_losses = sum(report['friendly_losses'].values(), D(0))
    enemy_losses = sum(report['enemy_losses'].values(), D(0))
    state.units_lost = str(D(state.units_lost) + friendly_losses)
    state.units_defeated = str(D(state.units_defeated) + enemy_losses)
    for unit in combat_stats.UNIT_STATS:
        survivors = getattr(realm, unit)
        gain = survivors * D('.08') + report['enemy_losses'][unit] * D('.04')
        attr = unit.rstrip('s') + '_experience'
        setattr(state, attr, str(D(getattr(state, attr)) + gain))
    total_before = sum((getattr(realm, u) + report['friendly_losses'][u] for u in combat_stats.UNIT_STATS), D(0))
    loss_rate = friendly_losses * D(100) / max(D(1), total_before)
    state.fatigue = str(min(D(100), D(state.fatigue) + D(20) + loss_rate * D('.45')))
    state.supply = str(max(D(0), D(state.supply) - D(18)))
    state.last_lesson = f"{report['result']}: lost {friendly_losses}, defeated {enemy_losses}."
    return True
