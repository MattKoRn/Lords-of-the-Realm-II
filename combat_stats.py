#!/usr/bin/env python3
from __future__ import annotations

import curses
import random
from decimal import ROUND_FLOOR

import game_core as g
import whole_numbers

D = g.D

UNIT_STATS = {
    'soldiers': {
        'name': 'Soldier', 'attack': D(8), 'defence': D(7), 'health': D(12),
        'range': D(1), 'speed': D(4), 'morale': D(7),
        'targets': ('knights', 'soldiers', 'archers'),
    },
    'archers': {
        'name': 'Archer', 'attack': D(11), 'defence': D(3), 'health': D(8),
        'range': D(8), 'speed': D(5), 'morale': D(6),
        'targets': ('soldiers', 'archers', 'knights'),
    },
    'knights': {
        'name': 'Knight', 'attack': D(24), 'defence': D(16), 'health': D(28),
        'range': D(1), 'speed': D(9), 'morale': D(10),
        'targets': ('archers', 'soldiers', 'knights'),
    },
}

COUNTERS = {
    ('soldiers', 'knights'): D('1.25'),
    ('archers', 'soldiers'): D('1.30'),
    ('knights', 'archers'): D('1.40'),
    ('knights', 'soldiers'): D('1.12'),
    ('soldiers', 'archers'): D('0.90'),
    ('archers', 'knights'): D('0.72'),
}

LAST_BATTLE = {
    'result': 'No battle fought yet.',
    'rounds': 0,
    'friendly_losses': {'soldiers': D(0), 'archers': D(0), 'knights': D(0)},
    'enemy_losses': {'soldiers': D(0), 'archers': D(0), 'knights': D(0)},
    'enemy_start': {'soldiers': D(0), 'archers': D(0), 'knights': D(0)},
}


def whole(value):
    return max(D(0), D(value).to_integral_value(rounding=ROUND_FLOOR))


def army_from_realm(realm):
    return {unit: whole(getattr(realm, unit)) for unit in UNIT_STATS}


def unit_rating(unit):
    stats = UNIT_STATS[unit]
    return (
        stats['attack'] * D('1.2') + stats['defence'] + stats['health'] * D('.5')
        + stats['range'] * D('.35') + stats['speed'] * D('.30') + stats['morale'] * D('.45')
    )


def army_rating(army, morale=D(1), fortification=D(1)):
    total = sum((army[u] * unit_rating(u) for u in UNIT_STATS), D(0))
    return total * morale * fortification


def military_power(realm):
    morale = D('.65') + realm.happiness / D(180)
    fort = D(1) + realm.walls * D('.035') + realm.castles * D('.10')
    return g.finite(army_rating(army_from_realm(realm), morale, fort))


def enemy_army(realm, variance=True):
    target = g.finite(g.safe_pow(realm.threat, D('1.12')) * D(18), D('1E999999'))
    if variance:
        target *= D(str(random.uniform(.88, 1.12)))
    weights = {'soldiers': D('.52'), 'archers': D('.31'), 'knights': D('.17')}
    army = {}
    for unit, weight in weights.items():
        army[unit] = max(D(0), whole(target * weight / max(D(1), unit_rating(unit))))
    if sum(army.values(), D(0)) < 1:
        army['soldiers'] = D(1)
    return army


def enemy_power(realm):
    return g.finite(army_rating(enemy_army(realm, variance=False)))


def living(army):
    return sum(army.values(), D(0)) > 0


def casualty_count(damage, defender, defending_count, defence_bonus=D(1)):
    if defending_count <= 0 or damage <= 0:
        return D(0)
    stats = UNIT_STATS[defender]
    durability = stats['health'] + stats['defence'] * defence_bonus
    return min(defending_count, whole(damage / max(D(1), durability)))


def attack_damage(attacker, count, target, round_number, morale):
    if count <= 0:
        return D(0)
    stats = UNIT_STATS[attacker]
    counter = COUNTERS.get((attacker, target), D(1))
    opening = D('1.30') if round_number == 1 and stats['range'] >= D(6) else D(1)
    speed = D(1) + stats['speed'] / D(100)
    randomness = D(str(random.uniform(.88, 1.12)))
    return count * stats['attack'] * counter * opening * speed * morale * randomness


def apply_strikes(attackers, defenders, round_number, morale, defence_bonus=D(1)):
    losses = {unit: D(0) for unit in UNIT_STATS}
    remaining = dict(defenders)
    for attacker, count in attackers.items():
        if count <= 0:
            continue
        targets = UNIT_STATS[attacker]['targets']
        target = next((name for name in targets if remaining[name] - losses[name] > 0), None)
        if target is None:
            break
        damage = attack_damage(attacker, count, target, round_number, morale)
        available = max(D(0), remaining[target] - losses[target])
        killed = casualty_count(damage, target, available, defence_bonus)
        losses[target] += killed
    return losses


def subtract_losses(army, losses):
    for unit in UNIT_STATS:
        army[unit] = max(D(0), army[unit] - losses[unit])


def morale_factor(army, starting, base):
    start_total = max(D(1), sum(starting.values(), D(0)))
    current = sum(army.values(), D(0))
    survival = current / start_total
    return max(D('.35'), base * (D('.65') + survival * D('.35')))


def battle(realm):
    friendly = army_from_realm(realm)
    enemy = enemy_army(realm)
    friendly_start = dict(friendly)
    enemy_start = dict(enemy)
    rounds = 0

    if not living(friendly):
        realm.log('The campaign was cancelled because no combat units were available.')
        return

    for round_number in range(1, 9):
        if not living(friendly) or not living(enemy):
            break
        rounds = round_number
        friendly_morale = morale_factor(
            friendly, friendly_start, D('.70') + realm.happiness / D(200)
        )
        enemy_morale = morale_factor(enemy, enemy_start, D('.92'))

        enemy_losses = apply_strikes(friendly, enemy, round_number, friendly_morale)
        friendly_losses = apply_strikes(enemy, friendly, round_number, enemy_morale)

        subtract_losses(enemy, enemy_losses)
        subtract_losses(friendly, friendly_losses)

        if sum(friendly.values(), D(0)) <= sum(friendly_start.values(), D(0)) * D('.15'):
            break
        if sum(enemy.values(), D(0)) <= sum(enemy_start.values(), D(0)) * D('.12'):
            break

    friendly_losses = {u: friendly_start[u] - friendly[u] for u in UNIT_STATS}
    enemy_losses = {u: enemy_start[u] - enemy[u] for u in UNIT_STATS}
    for unit in UNIT_STATS:
        setattr(realm, unit, friendly[unit])

    friendly_score = army_rating(friendly, D('.9'))
    enemy_score = army_rating(enemy, D('.9'))
    won = living(friendly) and (not living(enemy) or friendly_score > enemy_score * D('1.08'))

    if won:
        defeated_rating = army_rating(enemy_start)
        reward = max(D(50), defeated_rating * D('1.8'))
        land = max(D(1), defeated_rating.sqrt() / D(20))
        realm.gold += reward
        realm.food += reward * D('.25')
        realm.territory += land
        realm.renown += max(D(1), defeated_rating.sqrt() / D(3))
        realm.victories += D(1)
        realm.threat = max(D(1), realm.threat * D('.76'))
        result = 'Victory'
    else:
        realm.happiness = max(D(5), realm.happiness - D(6))
        realm.defeats += D(1)
        realm.threat = max(D(1), realm.threat * D('.94'))
        result = 'Defeat'

    LAST_BATTLE['result'] = result
    LAST_BATTLE['rounds'] = rounds
    LAST_BATTLE['friendly_losses'] = friendly_losses
    LAST_BATTLE['enemy_losses'] = enemy_losses
    LAST_BATTLE['enemy_start'] = enemy_start

    friendly_text = ', '.join(
        f"{UNIT_STATS[u]['name']} {g.fmt(friendly_losses[u])}" for u in UNIT_STATS
    )
    enemy_text = ', '.join(
        f"{UNIT_STATS[u]['name']} {g.fmt(enemy_losses[u])}" for u in UNIT_STATS
    )
    realm.log(f'{result} after {rounds} rounds. Losses: {friendly_text}. Enemy losses: {enemy_text}.')
    realm.sanitize()


# Install the stat model globally so neural risk checks, forecasts and campaigns agree.
g.Realm.military_power = military_power
g.enemy_power = enemy_power
g.attack = battle


class Game(whole_numbers.Game):
    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 18 or w < 75 or self.TABS[self.tab] != 'Military':
            return

        start = 7
        end = max(start, h - 6)
        blank = ' ' * max(0, w - 1)
        for row in range(start, end):
            super().add(row, 0, blank)

        if self.sub == 0:
            self.add(start, 2, 'UNIT STATISTICS', curses.A_BOLD)
            self.add(start + 1, 2, 'Unit       Count   Attack Defence Health Range Speed Morale', curses.A_UNDERLINE)
            row = start + 2
            for unit in ('soldiers', 'archers', 'knights'):
                stats = UNIT_STATS[unit]
                self.add(
                    row, 2,
                    f"{stats['name']:<10}{getattr(self.r, unit):>7}"
                    f"{stats['attack']:>8}{stats['defence']:>8}{stats['health']:>7}"
                    f"{stats['range']:>6}{stats['speed']:>6}{stats['morale']:>7}",
                )
                row += 1
            self.add(row + 1, 2, 'Counters: Soldiers > Knights | Archers > Soldiers | Knights > Archers')
            self.add(row + 2, 2, f'Calculated army rating: {self.r.military_power()}')
            self.add(row + 3, 2, f'Estimated enemy rating: {g.enemy_power(self.r)}')
        else:
            report = LAST_BATTLE
            self.add(start, 2, 'LAST BATTLE REPORT', curses.A_BOLD)
            self.add(start + 1, 2, f"Result: {report['result']} | Rounds: {report['rounds']}")
            self.add(start + 3, 2, 'Unit       Your losses   Enemy start   Enemy losses', curses.A_UNDERLINE)
            row = start + 4
            for unit in ('soldiers', 'archers', 'knights'):
                self.add(
                    row, 2,
                    f"{UNIT_STATS[unit]['name']:<10}"
                    f"{report['friendly_losses'][unit]:>12}"
                    f"{report['enemy_start'][unit]:>14}"
                    f"{report['enemy_losses'][unit]:>15}",
                )
                row += 1
            self.add(row + 1, 2, 'Casualties are permanent. Surviving units remain in the army.')
        self.s.refresh()


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
