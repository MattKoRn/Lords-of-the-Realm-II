#!/usr/bin/env python3
from __future__ import annotations

import curses
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field

import autonomous_mode as auto
import game_core as g
import kingdom_launch
import kingdom_evolved as evolved

D = g.D
STATE_FILE = g.SAVE_DIR / 'ascendant_state_v4.json'

PROVINCES = [
    ('Greenfields', 'food', D('.08')),
    ('Oakreach', 'wood', D('.08')),
    ('High Quarry', 'stone', D('.08')),
    ('Irondeep', 'iron', D('.08')),
    ('Gold Coast', 'gold', D('.08')),
    ('Marchlands', 'power', D('.10')),
    ('Scholars Vale', 'research', D('.12')),
    ('Crownlands', 'all', D('.05')),
]

ACHIEVEMENTS = [
    ('First Blood', 'victories', D(1)),
    ('Growing Realm', 'population', D(500)),
    ('Fortified', 'walls', D(10)),
    ('Master Builder', 'buildings', D(50)),
    ('Conqueror', 'territory', D(100)),
    ('Legendary Dynasty', 'prestige', D(5)),
    ('Scholar King', 'research', D(12000)),
    ('Millionaire', 'gold', D(1_000_000)),
]

DISASTERS = ['Drought', 'Flood', 'Plague', 'Mine Collapse', 'Great Fire', 'Bandit Uprising']


@dataclass
class AscendantState:
    version: int = 4
    last_saved: float = field(default_factory=time.time)
    provinces: list[str] = field(default_factory=lambda: ['Greenfields'])
    province_progress: str = '0'
    achievements: list[str] = field(default_factory=list)
    disaster: str = ''
    disaster_time: float = 0.0
    disaster_strength: str = '0'
    stability: str = '70'
    legitimacy: str = '10'
    diplomacy_log: list[str] = field(default_factory=list)
    era: int = 1
    last_ai_reason: str = 'Assessing the realm.'

    @property
    def stability_value(self): return D(self.stability)
    @stability_value.setter
    def stability_value(self, value): self.stability = str(max(D(0), min(D(100), D(value))))
    @property
    def legitimacy_value(self): return D(self.legitimacy)
    @legitimacy_value.setter
    def legitimacy_value(self, value): self.legitimacy = str(max(D(0), D(value)))


def load_state():
    try:
        data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        allowed = AscendantState.__dataclass_fields__
        state = AscendantState(**{k: v for k, v in data.items() if k in allowed})
        valid_names = {name for name, _, _ in PROVINCES}
        state.provinces = [name for name in state.provinces if name in valid_names] or ['Greenfields']
        state.achievements = [name for name, _, _ in ACHIEVEMENTS if name in state.achievements]
        state.disaster = state.disaster if state.disaster in DISASTERS else ''
        state.disaster_time = max(0.0, min(600.0, float(state.disaster_time)))
        state.diplomacy_log = [str(x)[:240] for x in state.diplomacy_log[-40:]]
        state.era = max(1, int(state.era))
        state.stability_value = state.stability_value
        state.legitimacy_value = state.legitimacy_value
        return state
    except (OSError, ValueError, TypeError, json.JSONDecodeError, ArithmeticError):
        return AscendantState()


def save_state(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(STATE_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


def province_bonus(state, category):
    total = D(0)
    for name, kind, amount in PROVINCES:
        if name in state.provinces and (kind == category or kind == 'all'):
            total += amount
    return total


def relation_label(attitude):
    if attitude <= -60: return 'Hostile'
    if attitude <= -25: return 'Unfriendly'
    if attitude < 25: return 'Neutral'
    if attitude < 60: return 'Friendly'
    return 'Allied'


def total_buildings(realm):
    return sum((realm.farms, realm.lumberyards, realm.quarries, realm.mines,
                realm.markets, realm.barracks, realm.walls, realm.castles), D(0))


def achievement_value(kind, realm, world):
    return {
        'victories': realm.victories, 'population': realm.population,
        'walls': realm.walls, 'buildings': total_buildings(realm),
        'territory': realm.territory, 'prestige': realm.prestige,
        'research': world.research_value, 'gold': realm.gold,
    }.get(kind, D(0))


def check_achievements(state, realm, world):
    for name, kind, target in ACHIEVEMENTS:
        if name in state.achievements or achievement_value(kind, realm, world) < target:
            continue
        state.achievements.append(name)
        reward = max(D(100), target.sqrt() * D(20))
        realm.gold += reward
        realm.renown += max(D(1), reward.sqrt() / D(10))
        evolved.log_event(world, realm, f'Achievement unlocked: {name}. Reward: {g.fmt(reward)} gold.')


def maybe_claim_province(state, realm, world):
    state.province_progress = str(D(state.province_progress) + max(D('.01'), realm.territory.sqrt() * D('.002')))
    threshold = D(20) * D(len(state.provinces) ** 2)
    if D(state.province_progress) < threshold or len(state.provinces) >= len(PROVINCES):
        return
    choices = [name for name, _, _ in PROVINCES if name not in state.provinces]
    name = random.choice(choices)
    state.provinces.append(name)
    state.province_progress = '0'
    state.legitimacy_value += D(5)
    evolved.log_event(world, realm, f'Province integrated: {name}.')


def start_disaster(state, realm, world):
    if state.disaster or random.random() > 0.012:
        return
    state.disaster = random.choice(DISASTERS)
    state.disaster_time = random.uniform(20, 45)
    state.disaster_strength = str(max(D(1), realm.population.sqrt() * D('.4')))
    evolved.log_event(world, realm, f'Disaster: {state.disaster} has begun.')


def apply_disaster(state, realm, dt):
    if not state.disaster:
        return
    strength = D(state.disaster_strength) * D(dt)
    if state.disaster == 'Drought': realm.food = max(D(0), realm.food - strength * D(2))
    elif state.disaster == 'Flood': realm.wood = max(D(0), realm.wood - strength); realm.food = max(D(0), realm.food - strength)
    elif state.disaster == 'Plague': realm.population = max(D(10), realm.population - strength * D('.02'))
    elif state.disaster == 'Mine Collapse': realm.stone = max(D(0), realm.stone - strength); realm.iron = max(D(0), realm.iron - strength * D('.5'))
    elif state.disaster == 'Great Fire': realm.wood = max(D(0), realm.wood - strength * D(1.5)); realm.gold = max(D(0), realm.gold - strength)
    elif state.disaster == 'Bandit Uprising': realm.gold = max(D(0), realm.gold - strength); realm.happiness = max(D(0), realm.happiness - D('.01') * D(dt))
    state.stability_value -= D('.04') * D(dt)
    state.disaster_time = max(0.0, state.disaster_time - dt)
    if state.disaster_time <= 0:
        state.disaster = ''
        state.disaster_strength = '0'


def valid_actions(game):
    r = game.r
    valid = {'wait', 'tax_down', 'tax_up'}
    for unit in g.RECRUITS:
        if auto.batch_size(r, unit) >= 1:
            valid.add(unit)
    for building, (attr, base) in g.BUILDINGS.items():
        if g.can_pay(r, g.scaled_cost(base, getattr(r, attr))):
            valid.add(building)
    if r.military_power() >= g.enemy_power(r) * D('.65'):
        valid.add('attack')
    if g.realm_worth(r) >= g.prestige_requirement(r):
        valid.add('prestige')
    if r.tax_rate <= D('.02'): valid.discard('tax_down')
    if r.tax_rate >= D('.60'): valid.discard('tax_up')
    return valid


def choose_masked(ai, realm, allowed):
    x = ai.features(realm)
    hidden = [math.tanh(sum(w * v for w, v in zip(row, x))) for row in ai.w1]
    outputs = [sum(w * v for w, v in zip(row, hidden)) + random.uniform(-.015, .015) for row in ai.w2]
    candidates = [i for i, name in enumerate(ai.ACTIONS) if name in allowed]
    if not candidates:
        return 'wait'
    index = max(candidates, key=lambda i: outputs[i])
    action = ai.ACTIONS[index]
    ai.last_action = action
    ai.decisions += 1
    ai.action_counts[action] += 1
    return action


class Game(kingdom_launch.evolved.Game):
    TABS = ['Dashboard', 'Realm', 'Economy', 'Military', 'World', 'Research', 'Rivals', 'Legacy', 'Chronicle', 'Help']
    SUBTABS = {name: ['Overview', 'Details'] for name in TABS}

    def __init__(self, screen):
        super().__init__(screen)
        self.asc = load_state()
        self.last_asc_save = time.monotonic()
        self.r.log('Dynasty Ascendant systems activated.')

    def ai_action(self):
        try:
            allowed = valid_actions(self)
            action = choose_masked(self.ai, self.r, allowed)
            self.asc.last_ai_reason = f'{len(allowed)} viable policies; selected {action}.'
            auto.execute(self.ai, self.r, action)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Neural decision rejected safely: {exc}'[:160]

    def update(self):
        now = time.monotonic(); dt = max(0.0, min(1.0, now - self.last_tick))
        if not self.paused:
            self.r.tick(dt)
            self.apply_world_production(dt)
            for resource in ('food', 'wood', 'stone', 'iron', 'gold'):
                bonus = province_bonus(self.asc, resource)
                if bonus: setattr(self.r, resource, max(D(0), getattr(self.r, resource) + self.r.rates()[resource] * bonus * D(dt)))
            self.advance_world(dt)
            apply_disaster(self.asc, self.r, dt)
            start_disaster(self.asc, self.r, self.world)
            maybe_claim_province(self.asc, self.r, self.world)
            check_achievements(self.asc, self.r, self.world)
            self.asc.stability_value += (self.r.happiness - self.asc.stability_value) * D('.001') * D(dt)
            self.asc.legitimacy_value += (self.r.renown + self.r.prestige * D(20)) * D('.00001') * D(dt)
            self.asc.era = max(1, int(self.r.prestige) + 1)
            if now - self.last_ai_action >= .75: self.ai_action(); self.last_ai_action = now
            if now - self.last_ai_eval >= 12: self.ai.evaluate(self.r); self.last_ai_eval = now
        self.last_tick = now
        if now - self.last_save >= 1: g.save_realm(self.r); self.last_save = now
        if now - self.last_ai_save >= 5: auto.save_ai(self.ai); self.last_ai_save = now
        if now - self.last_world_save >= 5: evolved.save_world(self.world); self.last_world_save = now
        if now - self.last_asc_save >= 5: save_state(self.asc); self.last_asc_save = now

    def handle(self, key):
        if key == -1: return
        if self.popup:
            if key in (10, 13, 27, 32, ord('d'), ord('D')): self.popup = False
            return
        if key in (ord('q'), ord('Q')): self.running = False; return
        if key in (ord('p'), ord('P'), 32): self.paused = not self.paused; return
        if ord('1') <= key <= ord('9'): self.tab, self.sub = key - ord('1'), 0; return
        if key == ord('0'): self.tab, self.sub = 9, 0; return
        if key == curses.KEY_RIGHT: self.tab, self.sub = (self.tab + 1) % len(self.TABS), 0; return
        if key == curses.KEY_LEFT: self.tab, self.sub = (self.tab - 1) % len(self.TABS), 0; return
        if key in (9, ord(']')): self.sub = (self.sub + 1) % 2; return
        if key == ord('['): self.sub = (self.sub - 1) % 2

    def header(self):
        h, w = self.s.getmaxyx()
        if h < 7 or w < 40:
            self.add(0, 0, 'Terminal too small. Resize or press Q.', curses.A_BOLD); return
        title = f' DYNASTY ASCENDANT | Era {self.asc.era} | {self.r.name} '
        self.add(0, 0, title.center(w - 1, '='), curses.A_BOLD)
        x = 0
        for i, tab in enumerate(self.TABS):
            label = f' {i+1 if i < 9 else 0}:{tab} '
            if x + len(label) < w: self.add(1, x, label, curses.A_REVERSE if i == self.tab else curses.A_DIM)
            x += len(label)
        season = evolved.SEASONS[self.world.season]
        alert = f' | ALERT: {self.asc.disaster} {int(self.asc.disaster_time)}s' if self.asc.disaster else ''
        self.add(2, 0, f' {season} / {self.world.weather} | Stability {self.asc.stability_value:.0f}% | Legitimacy {g.fmt(self.asc.legitimacy_value)}{alert} '[:w-1].ljust(w-1), curses.A_REVERSE if self.asc.disaster else curses.A_BOLD)
        self.add(3, 0, f' Objective: {self.world.objective} '[:w-1])
        self.add(4, 0, f' Gold {g.fmt(self.r.gold)} | Food {g.fmt(self.r.food)} | Pop {g.fmt(self.r.population)} | Power {g.fmt(self.r.military_power())} | AI {self.ai.last_action} '[:w-1].ljust(w-1), curses.A_REVERSE)

    def panel(self, y, x, width, title, rows):
        self.add(y, x, f'[{title}]', curses.A_BOLD)
        for i, (name, value) in enumerate(rows):
            self.add(y + i + 1, x, f'{name:<16}{str(value):>{max(1, width-16)}}')

    def draw(self):
        self.s.erase(); self.header(); h, w = self.s.getmaxyx()
        if h < 7 or w < 40: self.s.refresh(); return
        tab, y = self.TABS[self.tab], 6
        if tab == 'Dashboard':
            half = max(30, w // 2 - 2)
            self.panel(y, 2, half, 'KINGDOM', [('Population', g.fmt(self.r.population)), ('Territory', g.fmt(self.r.territory)), ('Happiness', f'{self.r.happiness:.1f}%'), ('Prestige', g.fmt(self.r.prestige)), ('Worth', g.fmt(g.realm_worth(self.r)))])
            self.panel(y, min(w-30, half+3), max(26,w-half-5), 'NEURAL GOVERNOR', [('Action', self.ai.last_action), ('Result', self.ai.last_result[:24]), ('Generation', self.ai.generation), ('Score', f'{self.ai.score:.3f}'), ('Viability', self.asc.last_ai_reason[:24])])
            self.panel(y+8, 2, half, 'WORLD', [('Season', evolved.SEASONS[self.world.season]), ('Weather', self.world.weather), ('Provinces', f'{len(self.asc.provinces)}/{len(PROVINCES)}'), ('Research', g.fmt(self.world.research_value)), ('Disaster', self.asc.disaster or 'None')])
            self.panel(y+8, min(w-30, half+3), max(26,w-half-5), 'LEGACY', [('Era', self.asc.era), ('Achievements', f'{len(self.asc.achievements)}/{len(ACHIEVEMENTS)}'), ('Objectives', self.world.objectives_completed), ('Stability', f'{self.asc.stability_value:.0f}%'), ('Legitimacy', g.fmt(self.asc.legitimacy_value))])
        elif tab == 'Realm':
            rows=[('Population',g.fmt(self.r.population)),('Free people',g.fmt(self.r.free_people())),('Happiness',f'{self.r.happiness:.1f}%'),('Taxes',f'{self.r.tax_rate*100:.0f}%'),('Territory',g.fmt(self.r.territory)),('Renown',g.fmt(self.r.renown)),('Prestige',g.fmt(self.r.prestige))]
            for a,b in rows:self.add(y,3,f'{a:<20}{b}');y+=1
        elif tab == 'Economy':
            mods=evolved.season_modifiers(self.world)
            for name in ('gold','food','wood','stone','iron'):
                bonus=mods[name]+evolved.tech_bonus(self.world,name)+province_bonus(self.asc,name)
                self.add(y,3,f'{name.title():<10}{g.fmt(getattr(self.r,name)):>15}  {g.fmt(self.r.rates()[name]):>12}/s  bonus {bonus*100:+.0f}%');y+=1
            self.add(y+1,3,f'Buildings: {g.fmt(total_buildings(self.r))} | Farmers {g.fmt(self.r.farmers)} | Miners {g.fmt(self.r.miners)}')
        elif tab == 'Military':
            for a,b in [('Soldiers',self.r.soldiers),('Archers',self.r.archers),('Knights',self.r.knights),('Power',self.r.military_power()),('Enemy',g.enemy_power(self.r)),('Victories',self.r.victories),('Defeats',self.r.defeats)]:self.add(y,3,f'{a:<18}{g.fmt(b)}');y+=1
            self.add(y+1,3,f'AI attacks only when estimated power is at least 65% of enemy power.')
        elif tab == 'World':
            self.add(y,3,f'Current disaster: {self.asc.disaster or "None"}'); self.add(y+1,3,f'Stability: {self.asc.stability_value:.1f}%'); y+=3
            for name,kind,amount in PROVINCES:
                mark='✓' if name in self.asc.provinces else '·'; self.add(y,3,f'{mark} {name:<20} {kind:<10} +{amount*100:.0f}%');y+=1
        elif tab == 'Research':
            self.add(y,3,f'Research: {g.fmt(self.world.research_value)} | Technologies {len(self.world.unlocked)}/{len(evolved.TECHS)}');y+=2
            for name,cost,kind,amount in evolved.TECHS:
                mark='✓' if name in self.world.unlocked else '·';self.add(y,3,f'{mark} {name:<23}{cost:>7} RP  {kind} +{amount*100:.0f}%');y+=1
        elif tab == 'Rivals':
            for rival in self.world.rivals:
                attitude=int(rival.get('attitude',0)); self.add(y,3,f"{rival['name']:<22}{relation_label(attitude):<11} Power {g.fmt(D(rival['power'])):>10} Wealth {g.fmt(D(rival['wealth'])):>10}");y+=2
        elif tab == 'Legacy':
            self.add(y,3,f'Era {self.asc.era} | Legitimacy {g.fmt(self.asc.legitimacy_value)} | Achievements {len(self.asc.achievements)}/{len(ACHIEVEMENTS)}');y+=2
            for name,kind,target in ACHIEVEMENTS:
                mark='✓' if name in self.asc.achievements else '·';self.add(y,3,f'{mark} {name:<22} {kind} {g.fmt(target)}');y+=1
        elif tab == 'Chronicle':
            messages=self.world.events if self.sub else self.r.messages
            for message in messages[-max(1,h-8):]:self.add(y,3,'• '+message);y+=1
        else:
            lines=['1-9 / 0 or arrows: view tabs','Tab / [ ]: switch reports','P or Space: pause/resume','Q: save and quit','','Every kingdom action remains neural-controlled. Action masking removes impossible choices without adding player control.']
            for line in lines:self.add(y,3,line);y+=1
        status='PAUSED' if self.paused else f'AI {self.ai.last_action}'
        self.add(h-2,0,f' {status} | Era {self.asc.era} | Province progress {g.fmt(D(self.asc.province_progress))} | autosaving '.ljust(max(0,w-1)),curses.A_REVERSE)
        if self.popup:self.draw_popup()
        self.s.refresh()

    def run(self):
        try:curses.curs_set(0)
        except curses.error:pass
        self.s.nodelay(True);self.s.timeout(int(g.TICK*1000));self.s.keypad(True)
        try:
            while self.running:self.update();self.draw();self.handle(self.s.getch())
        finally:
            g.save_realm(self.r);auto.save_ai(self.ai);evolved.save_world(self.world);save_state(self.asc)


def main():
    try:curses.wrapper(lambda screen:Game(screen).run())
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
