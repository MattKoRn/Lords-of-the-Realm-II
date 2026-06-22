#!/usr/bin/env python3
from __future__ import annotations

import curses
import json
import random
import time
from dataclasses import asdict, dataclass, field

import autonomous_mode as auto
import game_core as g
import popup_fix

D = g.D
META_FILE = g.SAVE_DIR / 'world_state_v3.json'
SEASONS = ['Spring', 'Summer', 'Autumn', 'Winter']
WEATHER = {
    'Spring': ['Clear', 'Rain', 'Mild Winds'],
    'Summer': ['Clear', 'Heatwave', 'Storm'],
    'Autumn': ['Clear', 'Heavy Rain', 'Early Frost'],
    'Winter': ['Clear', 'Snow', 'Blizzard'],
}
TECHS = [
    ('Crop Rotation', 25, 'food', D('0.08')),
    ('Iron Ploughs', 70, 'food', D('0.12')),
    ('Guild Charters', 150, 'gold', D('0.10')),
    ('Masonry', 300, 'stone', D('0.14')),
    ('Deep Mining', 600, 'iron', D('0.18')),
    ('Longbow Doctrine', 1200, 'power', D('0.15')),
    ('Royal Roads', 2500, 'all', D('0.08')),
    ('Universities', 5000, 'research', D('0.25')),
    ('Imperial Logistics', 12000, 'all', D('0.12')),
]
RIVAL_NAMES = ['House Ashford', 'The Iron March', 'Kingdom of Vale', 'Blackthorn League']


@dataclass
class Rival:
    name: str
    power: str = '20'
    wealth: str = '500'
    attitude: int = 0
    victories: int = 0


@dataclass
class WorldState:
    version: int = 3
    last_saved: float = field(default_factory=time.time)
    season: int = 0
    season_time: float = 0.0
    weather: str = 'Clear'
    research: str = '0'
    unlocked: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=lambda: ['The wider world begins to stir.'])
    rivals: list[dict] = field(default_factory=lambda: [asdict(Rival(name=n, power=str(20 + i * 12), wealth=str(500 + i * 300), attitude=random.randint(-20, 20))) for i, n in enumerate(RIVAL_NAMES)])
    objective: str = 'Grow the population to 250'
    objective_target: str = '250'
    objective_type: str = 'population'
    objectives_completed: int = 0
    next_event: float = 18.0
    next_rival: float = 28.0

    @property
    def research_value(self): return D(self.research)
    @research_value.setter
    def research_value(self, value): self.research = str(max(D(0), D(value)))


def load_world():
    try:
        data = json.loads(META_FILE.read_text(encoding='utf-8'))
        allowed = WorldState.__dataclass_fields__
        state = WorldState(**{k: v for k, v in data.items() if k in allowed})
        if not isinstance(state.events, list): state.events = []
        if not isinstance(state.unlocked, list): state.unlocked = []
        if not isinstance(state.rivals, list): state.rivals = WorldState().rivals
        return state
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return WorldState()


def save_world(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(META_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


def tech_bonus(state, category):
    bonus = D(0)
    for name, _, kind, amount in TECHS:
        if name in state.unlocked and (kind == category or kind == 'all'):
            bonus += amount
    return bonus


def season_modifiers(state):
    season = SEASONS[state.season]
    food, wood, stone, iron, gold = D(0), D(0), D(0), D(0), D(0)
    if season == 'Spring': food += D('.18')
    elif season == 'Summer': food += D('.10'); gold += D('.05')
    elif season == 'Autumn': food += D('.05'); wood += D('.12')
    else: food -= D('.18'); stone += D('.08')
    if state.weather == 'Rain': food += D('.08')
    elif state.weather == 'Heatwave': food -= D('.12')
    elif state.weather == 'Storm': wood -= D('.10'); gold -= D('.05')
    elif state.weather == 'Heavy Rain': food -= D('.06')
    elif state.weather == 'Early Frost': food -= D('.10')
    elif state.weather == 'Snow': food -= D('.08')
    elif state.weather == 'Blizzard': food -= D('.18'); wood -= D('.12')
    return {'food': food, 'wood': wood, 'stone': stone, 'iron': iron, 'gold': gold}


def log_event(state, realm, text):
    state.events.append(text)
    state.events = state.events[-60:]
    realm.log(text)


def choose_objective(state, realm):
    choices = [
        ('population', realm.population * D('1.5'), 'Grow the population to {value}'),
        ('territory', realm.territory + max(D(5), realm.territory * D('.25')), 'Expand territory to {value}'),
        ('power', realm.military_power() * D('1.6') + D(10), 'Reach military power {value}'),
        ('gold', realm.gold * D(2) + D(1000), 'Accumulate {value} gold'),
        ('victories', realm.victories + D(3), 'Win {value} total campaigns'),
    ]
    kind, target, text = random.choice(choices)
    state.objective_type = kind
    state.objective_target = str(target)
    state.objective = text.format(value=g.fmt(target))


def check_objective(state, realm):
    values = {'population': realm.population, 'territory': realm.territory, 'power': realm.military_power(), 'gold': realm.gold, 'victories': realm.victories}
    if values.get(state.objective_type, D(0)) < D(state.objective_target): return
    reward = max(D(500), g.realm_worth(realm) * D('.02'))
    realm.gold += reward
    realm.renown += max(D(1), reward.sqrt() / D(20))
    state.objectives_completed += 1
    log_event(state, realm, f'Objective completed: {state.objective}. Reward: {g.fmt(reward)} gold.')
    choose_objective(state, realm)


def unlock_techs(state, realm):
    changed = False
    for name, cost, _, _ in TECHS:
        if name not in state.unlocked and state.research_value >= D(cost):
            state.unlocked.append(name)
            changed = True
            log_event(state, realm, f'Research breakthrough: {name}.')
    return changed


def random_event(state, realm):
    roll = random.randrange(8)
    scale = max(D(1), realm.population.sqrt())
    if roll == 0:
        gain = scale * D(12); realm.food += gain; text = f'An exceptional harvest produced {g.fmt(gain)} food.'
    elif roll == 1:
        gain = scale * D(8); realm.gold += gain; text = f'A merchant caravan paid {g.fmt(gain)} gold in tariffs.'
    elif roll == 2:
        loss = min(realm.food * D('.08'), scale * D(10)); realm.food -= loss; text = f'Crop blight destroyed {g.fmt(loss)} food.'
    elif roll == 3:
        realm.happiness = min(D(100), realm.happiness + D(6)); text = 'A royal festival lifted public morale.'
    elif roll == 4:
        realm.happiness = max(D(0), realm.happiness - D(5)); text = 'Court scandal damaged public confidence.'
    elif roll == 5:
        gain = scale * D(3); realm.iron += gain; text = f'A new ore seam yielded {g.fmt(gain)} iron.'
    elif roll == 6:
        volunteers = min(realm.free_people(), max(D(1), realm.population // D(80))); realm.soldiers += volunteers; text = f'{g.fmt(volunteers)} volunteers joined the army.'
    else:
        realm.renown += scale; text = 'A travelling chronicler spread tales of the dynasty.'
    realm.sanitize(); log_event(state, realm, text)


def evolve_rivals(state, realm):
    if not state.rivals: state.rivals = WorldState().rivals
    rival = random.choice(state.rivals)
    power, wealth = D(rival.get('power', '20')), D(rival.get('wealth', '500'))
    power *= D(str(random.uniform(1.02, 1.10))); wealth *= D(str(random.uniform(1.03, 1.12)))
    rival['power'], rival['wealth'] = str(power), str(wealth)
    rival['attitude'] = max(-100, min(100, int(rival.get('attitude', 0)) + random.randint(-6, 6)))
    if rival['attitude'] >= 35:
        gift = min(wealth * D('.02'), max(D(50), realm.population)); realm.gold += gift; rival['wealth'] = str(max(D(0), wealth - gift)); text = f"{rival['name']} sent a gift of {g.fmt(gift)} gold."
    elif rival['attitude'] <= -35 and power > realm.military_power() * D('.7'):
        loss = min(realm.gold * D('.04'), power); realm.gold -= loss; realm.threat += power / D(100); text = f"Raiders from {rival['name']} stole {g.fmt(loss)} gold."
    else:
        trade = min(wealth * D('.01'), max(D(20), realm.population / D(2))); realm.gold += trade; realm.food += trade; text = f"Trade with {rival['name']} yielded {g.fmt(trade)} gold and food."
    log_event(state, realm, text)


class Game(popup_fix.Game):
    TABS = ['Realm', 'Economy', 'Military', 'World', 'Research', 'Rivals', 'Chronicle', 'Help']
    SUBTABS = {name: ['Overview', 'Details'] for name in TABS}

    def __init__(self, screen):
        super().__init__(screen)
        self.world = load_world()
        elapsed = max(0.0, min(g.MAX_OFFLINE, time.time() - self.world.last_saved))
        self.advance_world(elapsed, offline=True)
        self.last_world_save = time.monotonic()

    def advance_world(self, seconds, offline=False):
        seconds = max(0.0, float(seconds))
        self.world.season_time += seconds
        while self.world.season_time >= 120:
            self.world.season_time -= 120
            self.world.season = (self.world.season + 1) % len(SEASONS)
            self.world.weather = random.choice(WEATHER[SEASONS[self.world.season]])
            log_event(self.world, self.r, f"{SEASONS[self.world.season]} begins with {self.world.weather.lower()} weather.")
        research_rate = (self.r.builders * D('.03') + self.r.markets * D('.02') + D('.01')) * (D(1) + tech_bonus(self.world, 'research'))
        self.world.research_value += research_rate * D(seconds)
        if not offline:
            self.world.next_event -= seconds; self.world.next_rival -= seconds
            if self.world.next_event <= 0:
                random_event(self.world, self.r); self.world.next_event = random.uniform(18, 32)
            if self.world.next_rival <= 0:
                evolve_rivals(self.world, self.r); self.world.next_rival = random.uniform(28, 48)
        unlock_techs(self.world, self.r)
        check_objective(self.world, self.r)

    def apply_world_production(self, dt):
        base = self.r.rates(); seasonal = season_modifiers(self.world)
        for name in ('food', 'wood', 'stone', 'iron', 'gold'):
            bonus = seasonal[name] + tech_bonus(self.world, name) + tech_bonus(self.world, 'all')
            if bonus:
                self.r.__dict__[name] = max(D(0), self.r.__dict__[name] + base[name] * bonus * D(dt))
        power_bonus = tech_bonus(self.world, 'power')
        if power_bonus and self.r.free_people() > 0:
            self.r.renown += self.r.military_power() * power_bonus * D(dt) * D('.0001')

    def update(self):
        now = time.monotonic(); dt = max(0.0, min(1.0, now - self.last_tick))
        if not self.paused:
            self.r.tick(dt); self.apply_world_production(dt); self.advance_world(dt)
            if now - self.last_ai_action >= .7: self.ai_action(); self.last_ai_action = now
            if now - self.last_ai_eval >= 12: self.ai.evaluate(self.r); self.last_ai_eval = now
        self.last_tick = now
        if now - self.last_save >= 1: g.save_realm(self.r); self.last_save = now
        if now - self.last_ai_save >= 5: auto.save_ai(self.ai); self.last_ai_save = now
        if now - self.last_world_save >= 5: save_world(self.world); self.last_world_save = now

    def handle(self, key):
        if key == -1: return
        if self.popup:
            if key in (10, 13, 27, 32, ord('d'), ord('D')): self.popup = False
            return
        if key in (ord('q'), ord('Q')): self.running = False; return
        if key in (ord('p'), ord('P'), 32): self.paused = not self.paused; return
        if ord('1') <= key <= ord('8'): self.tab, self.sub = key - ord('1'), 0; return
        if key == curses.KEY_RIGHT: self.tab, self.sub = (self.tab + 1) % len(self.TABS), 0; return
        if key == curses.KEY_LEFT: self.tab, self.sub = (self.tab - 1) % len(self.TABS), 0; return
        if key in (9, ord(']')): self.sub = (self.sub + 1) % 2; return
        if key == ord('['): self.sub = (self.sub - 1) % 2

    def header(self):
        h, w = self.s.getmaxyx()
        if h < 5 or w < 30: self.add(0, 0, 'Terminal too small. Resize or press Q.', curses.A_BOLD); return
        self.add(0, 0, f' ENDLESS REALM II: KINGDOM EVOLVED | {self.r.name} '.center(w - 1, '='), curses.A_BOLD)
        x = 1
        for i, tab in enumerate(self.TABS):
            label = f' {i+1}:{tab} '; self.add(1, x, label, curses.A_REVERSE if i == self.tab else curses.A_DIM); x += len(label)
        self.add(2, 1, f" {SEASONS[self.world.season]} | {self.world.weather} | Objective: {self.world.objective} ", curses.A_BOLD)
        rates = self.r.rates()
        self.add(3, 0, f" Gold {g.fmt(self.r.gold)} ({g.fmt(rates['gold'])}/s) | Food {g.fmt(self.r.food)} | Pop {g.fmt(self.r.population)} | Power {g.fmt(self.r.military_power())} "[:w-1].ljust(w-1), curses.A_REVERSE)

    def draw(self):
        self.s.erase(); self.header(); h, w = self.s.getmaxyx()
        if h < 5 or w < 30: self.s.refresh(); return
        tab, y = self.TABS[self.tab], 5
        if tab == 'Realm':
            rows=[('Simulation','PAUSED' if self.paused else 'RUNNING'),('Population',g.fmt(self.r.population)),('Happiness',f'{self.r.happiness:.1f}%'),('Taxes',f'{self.r.tax_rate*100:.0f}%'),('Territory',g.fmt(self.r.territory)),('Prestige',g.fmt(self.r.prestige)),('Objectives',str(self.world.objectives_completed))]
            for a,b in rows:self.add(y,3,f'{a:<18}{b}');y+=1
        elif tab == 'Economy':
            mods=season_modifiers(self.world)
            for n in ('gold','food','wood','stone','iron'):
                total=mods[n]+tech_bonus(self.world,n)+tech_bonus(self.world,'all'); self.add(y,3,f'{n.title():<10}{g.fmt(getattr(self.r,n)):>14}  modifier {total*100:+.0f}%');y+=1
        elif tab == 'Military':
            for a,b in [('Soldiers',self.r.soldiers),('Archers',self.r.archers),('Knights',self.r.knights),('Power',self.r.military_power()),('Enemy',g.enemy_power(self.r)),('Victories',self.r.victories),('Defeats',self.r.defeats)]:self.add(y,3,f'{a:<16}{g.fmt(b)}');y+=1
        elif tab == 'World':
            self.add(y,3,f'Season: {SEASONS[self.world.season]} ({int(self.world.season_time)}/120s)'); self.add(y+1,3,f'Weather: {self.world.weather}'); self.add(y+3,3,f'Territory: {g.fmt(self.r.territory)}'); self.add(y+4,3,f'Threat: {g.fmt(self.r.threat)}'); self.add(y+6,3,f'Current objective: {self.world.objective}')
        elif tab == 'Research':
            self.add(y,3,f'Research points: {g.fmt(self.world.research_value)}'); self.add(y+1,3,f'Unlocked: {len(self.world.unlocked)}/{len(TECHS)}'); y+=3
            for name,cost,kind,amount in TECHS:
                mark='✓' if name in self.world.unlocked else '·'; self.add(y,3,f'{mark} {name:<22} {cost:>6} RP   {kind} +{amount*100:.0f}%'); y+=1
        elif tab == 'Rivals':
            for rival in self.world.rivals:
                self.add(y,3,f"{rival['name']:<22} Power {g.fmt(D(rival['power'])):>10} Wealth {g.fmt(D(rival['wealth'])):>10} Attitude {int(rival.get('attitude',0)):>4}"); y+=2
        elif tab == 'Chronicle':
            messages=self.world.events if self.sub else self.r.messages
            for message in messages[-max(1,h-7):]:self.add(y,3,'• '+message);y+=1
        else:
            for line in ['1-8 / Left-Right: view tabs','Tab / [ ]: view details','P or Space: pause/resume','Q: save and quit','','All realm actions remain neural-controlled. Seasons, research, rivals, events and objectives are autonomous.']:self.add(y,3,line);y+=1
        state='PAUSED' if self.paused else 'AI: '+self.ai.last_action
        self.add(h-2,0,f' {state} | {SEASONS[self.world.season]} / {self.world.weather} | autosaving '.ljust(max(0,w-1)),curses.A_REVERSE)
        if self.popup:self.draw_popup()
        self.s.refresh()

    def run(self):
        try:curses.curs_set(0)
        except curses.error:pass
        self.s.nodelay(True);self.s.timeout(int(g.TICK*1000));self.s.keypad(True)
        try:
            while self.running:self.update();self.draw();self.handle(self.s.getch())
        finally:g.save_realm(self.r);auto.save_ai(self.ai);save_world(self.world)


def main():
    try:curses.wrapper(lambda screen:Game(screen).run())
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
