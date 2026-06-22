#!/usr/bin/env python3
from __future__ import annotations

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

D = g.D
BRAIN_FILE = g.SAVE_DIR / 'neural_brain_v5.json'
REIGN_FILE = g.SAVE_DIR / 'neural_reign_v5.json'

WONDERS = [
    ('Grand Granary', 'population', D(800), 'food', D('.12')),
    ('Royal Mint', 'gold', D(250000), 'gold', D('.12')),
    ('Stone Citadel', 'walls', D(25), 'power', D('.15')),
    ('Great Library', 'research', D(25000), 'research', D('.18')),
    ('Hall of Kings', 'prestige', D(8), 'all', D('.08')),
]

TRADE_GOODS = ['Grain', 'Timber', 'Stone', 'Iron', 'Textiles', 'Spices']
DOCTRINES = ['Stewardship', 'Expansion', 'Fortification', 'Prosperity', 'Scholarship', 'Conquest']


@dataclass
class ReignState:
    version: int = 5
    last_saved: float = field(default_factory=time.time)
    wonders: list[str] = field(default_factory=list)
    trade_routes: list[dict] = field(default_factory=list)
    doctrine: str = 'Stewardship'
    doctrine_time: float = 0.0
    council: dict = field(default_factory=lambda: {'Steward': 1, 'Marshal': 1, 'Spymaster': 1, 'Chancellor': 1, 'Scholar': 1})
    decrees: list[str] = field(default_factory=list)
    decree_time: float = 0.0
    golden_age: float = 0.0
    famine_warning: bool = False
    last_summary: str = 'The neural court convenes.'


def load_reign():
    try:
        raw = json.loads(REIGN_FILE.read_text(encoding='utf-8'))
        allowed = ReignState.__dataclass_fields__
        state = ReignState(**{k: v for k, v in raw.items() if k in allowed})
        valid_wonders = {name for name, *_ in WONDERS}
        state.wonders = [name for name in state.wonders if name in valid_wonders]
        state.trade_routes = [r for r in state.trade_routes[-12:] if isinstance(r, dict)]
        state.doctrine = state.doctrine if state.doctrine in DOCTRINES else 'Stewardship'
        state.doctrine_time = max(0.0, min(600.0, float(state.doctrine_time)))
        state.decree_time = max(0.0, min(600.0, float(state.decree_time)))
        state.golden_age = max(0.0, min(3600.0, float(state.golden_age)))
        state.decrees = [str(x)[:80] for x in state.decrees[-6:]]
        if not isinstance(state.council, dict): state.council = ReignState().council
        for role in ReignState().council:
            try: state.council[role] = max(1, min(1000, int(state.council.get(role, 1))))
            except (TypeError, ValueError): state.council[role] = 1
        state.last_summary = str(state.last_summary)[:240]
        return state
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ReignState()


def save_reign(state):
    try:
        state.last_saved = time.time()
        g.atomic_json_write(REIGN_FILE, asdict(state))
    except (OSError, ValueError, TypeError):
        pass


class CognitiveGovernor(auto.NeuralGovernor):
    def __init__(self, data=None):
        super().__init__(None)
        self.outcome_memory = {a: 0.0 for a in self.ACTIONS}
        self.usage_memory = {a: 0 for a in self.ACTIONS}
        self.cooldowns = {a: 0 for a in self.ACTIONS}
        self.exploration = 0.08
        self.confidence = 0.0
        self.last_worth = '0'
        self.last_happiness = '0'
        self.last_power = '0'
        self.strategy = 'balanced'
        self.reason = 'Initial neural assessment.'
        if isinstance(data, dict): self._load_brain(data)

    def _load_brain(self, data):
        self._load_auto(data)
        for field_name, default in [('outcome_memory', {}), ('usage_memory', {}), ('cooldowns', {})]:
            source = data.get(field_name, default)
            if isinstance(source, dict):
                target = getattr(self, field_name)
                for action in self.ACTIONS:
                    try:
                        value = source.get(action, target[action])
                        target[action] = float(value) if field_name == 'outcome_memory' else max(0, int(value))
                    except (TypeError, ValueError): pass
        try: self.exploration = max(.005, min(.35, float(data.get('exploration', .08))))
        except (TypeError, ValueError): self.exploration = .08
        try: self.confidence = max(0., min(1., float(data.get('confidence', 0.))))
        except (TypeError, ValueError): self.confidence = 0.
        self.last_worth = str(data.get('last_worth', '0'))
        self.last_happiness = str(data.get('last_happiness', '0'))
        self.last_power = str(data.get('last_power', '0'))
        self.strategy = str(data.get('strategy', 'balanced'))[:30]
        self.reason = str(data.get('reason', 'State restored.'))[:180]

    def save_payload(self): return self.__dict__

    def observe_outcome(self, realm):
        current_worth = g.realm_worth(realm)
        current_happiness = realm.happiness
        current_power = realm.military_power()
        try:
            old_worth, old_happiness, old_power = D(self.last_worth), D(self.last_happiness), D(self.last_power)
            reward = 0.0
            if old_worth > 0: reward += float((current_worth - old_worth) / max(D(1), old_worth)) * 8
            reward += float((current_happiness - old_happiness) / D(100))
            if old_power > 0: reward += float((current_power - old_power) / max(D(1), old_power)) * 2
            reward = max(-2.0, min(2.0, reward))
            old = self.outcome_memory.get(self.last_action, 0.0)
            self.outcome_memory[self.last_action] = old * .88 + reward * .12
        except (ArithmeticError, ValueError): pass
        self.last_worth, self.last_happiness, self.last_power = str(current_worth), str(current_happiness), str(current_power)
        for action in self.cooldowns:
            self.cooldowns[action] = max(0, self.cooldowns[action] - 1)

    def context_utility(self, game, action):
        r, state = game.r, game.asc
        food_days = r.food / max(D(1), r.population * D('.08'))
        military_ratio = r.military_power() / max(D(1), g.enemy_power(r))
        utility = 0.0
        if food_days < 45:
            if action in ('farmer', 'farm'): utility += 3.0
            if action in ('soldier', 'archer', 'knight', 'attack'): utility -= 2.5
        if state.disaster:
            if action in ('wait', 'farmer', 'builder', 'wall'): utility += 1.2
            if action == 'attack': utility -= 3.0
        if r.happiness < 35:
            if action == 'tax_down': utility += 3.0
            if action == 'tax_up': utility -= 4.0
        elif r.happiness > 75 and r.gold < r.population * D(20):
            if action == 'tax_up': utility += 1.3
        if military_ratio < D('.8'):
            if action in ('soldier', 'archer', 'knight', 'barracks', 'wall', 'castle'): utility += 1.5
            if action == 'attack': utility -= 3.0
        elif military_ratio > D('1.35') and action == 'attack': utility += 2.5
        if g.realm_worth(r) >= g.prestige_requirement(r) and action == 'prestige': utility += 5.0
        if r.free_people() < r.population * D('.03') and action in g.RECRUITS: utility -= 2.0
        utility += self.outcome_memory.get(action, 0.0) * 2.2
        utility -= min(1.5, self.usage_memory.get(action, 0) * .015)
        if self.cooldowns.get(action, 0) > 0: utility -= 2.5
        return utility

    def choose_cognitive(self, game, allowed):
        self.observe_outcome(game.r)
        x = self.features(game.r)
        hidden = [math.tanh(sum(w * v for w, v in zip(row, x))) for row in self.w1]
        raw = [sum(w * v for w, v in zip(row, hidden)) for row in self.w2]
        candidates = [i for i, action in enumerate(self.ACTIONS) if action in allowed]
        if not candidates: return 'wait'
        scored = [(raw[i] + self.context_utility(game, self.ACTIONS[i]), i) for i in candidates]
        scored.sort(reverse=True)
        if random.random() < self.exploration:
            top = scored[:min(4, len(scored))]
            _, index = random.choice(top)
        else:
            _, index = scored[0]
        action = self.ACTIONS[index]
        margin = scored[0][0] - scored[1][0] if len(scored) > 1 else 3.0
        self.confidence = max(0.0, min(1.0, .5 + margin / 6))
        self.exploration = max(.008, self.exploration * .9995)
        self.last_action = action
        self.decisions += 1
        self.action_counts[action] += 1
        self.usage_memory[action] += 1
        self.cooldowns[action] = 2 if action not in ('wait', 'tax_up', 'tax_down') else 1
        self.reason = f'{len(candidates)} viable; utility {scored[0][0]:+.2f}; confidence {self.confidence:.0%}.'
        return action


def load_brain():
    try: return CognitiveGovernor(json.loads(BRAIN_FILE.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError, json.JSONDecodeError): return CognitiveGovernor()


def save_brain(ai):
    try: g.atomic_json_write(BRAIN_FILE, ai.save_payload())
    except (OSError, ValueError, TypeError): pass


def wonder_value(kind, realm, world):
    return {'population': realm.population, 'gold': realm.gold, 'walls': realm.walls,
            'research': world.research_value, 'prestige': realm.prestige}.get(kind, D(0))


def wonder_bonus(state, category):
    total = D(0)
    for name, _, _, kind, amount in WONDERS:
        if name in state.wonders and (kind == category or kind == 'all'): total += amount
    return total


def update_wonders(state, realm, world):
    for name, requirement, target, _, _ in WONDERS:
        if name in state.wonders or wonder_value(requirement, realm, world) < target: continue
        state.wonders.append(name)
        evolved.log_event(world, realm, f'Wonder completed: {name}.')


def update_trade(state, realm, world, seconds):
    if len(state.trade_routes) < min(6, 1 + int(realm.markets // D(5))) and random.random() < .003 * seconds:
        good = random.choice(TRADE_GOODS)
        yield_value = max(D(10), realm.population.sqrt() * D(random.randint(2, 7)))
        state.trade_routes.append({'good': good, 'yield': str(yield_value), 'age': 0.0})
        evolved.log_event(world, realm, f'New trade route established for {good}.')
    for route in state.trade_routes:
        route['age'] = float(route.get('age', 0)) + seconds
        income = D(route.get('yield', '10')) * D(seconds) * D('.02')
        realm.gold += income
        if route.get('good') == 'Grain': realm.food += income
        elif route.get('good') == 'Timber': realm.wood += income * D('.5')
        elif route.get('good') == 'Stone': realm.stone += income * D('.35')
        elif route.get('good') == 'Iron': realm.iron += income * D('.2')
    state.trade_routes = [r for r in state.trade_routes if float(r.get('age', 0)) < 900]


def choose_doctrine(state, game):
    r = game.r
    ratios = {
        'Stewardship': float(r.happiness / D(100)),
        'Expansion': float(g.decimal_log_feature(r.territory + 1)),
        'Fortification': float(g.decimal_log_feature(r.walls + r.castles + 1)),
        'Prosperity': float(g.decimal_log_feature(r.gold + 1)),
        'Scholarship': float(g.decimal_log_feature(game.world.research_value + 1)),
        'Conquest': float(g.decimal_log_feature(r.military_power() + 1)),
    }
    state.doctrine = max(ratios, key=ratios.get)
    state.doctrine_time = 120
    state.last_summary = f'Council adopted {state.doctrine} doctrine.'


def doctrine_bonus(state, category):
    mapping = {'Stewardship': 'happiness', 'Expansion': 'all', 'Fortification': 'power',
               'Prosperity': 'gold', 'Scholarship': 'research', 'Conquest': 'power'}
    return D('.08') if mapping.get(state.doctrine) == category else D(0)


class Game(asc.Game):
    TABS = ['Command', 'Realm', 'Economy', 'Military', 'World', 'Research', 'Diplomacy', 'Neural', 'Legacy', 'Chronicle', 'Help']
    SUBTABS = {name: ['Overview', 'Details'] for name in TABS}

    def __init__(self, screen):
        super().__init__(screen)
        self.ai = load_brain()
        self.reign = load_reign()
        self.last_reign_save = time.monotonic()
        self.r.log('Neural Reign intelligence activated.')

    def ai_action(self):
        try:
            allowed = asc.valid_actions(self)
            action = self.ai.choose_cognitive(self, allowed)
            self.asc.last_ai_reason = self.ai.reason
            auto.execute(self.ai, self.r, action)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Cognitive decision rejected: {exc}'[:160]

    def update(self):
        now = time.monotonic(); dt = max(0.0, min(1.0, now - self.last_tick))
        if not self.paused:
            self.r.tick(dt); self.apply_world_production(dt)
            for resource in ('food', 'wood', 'stone', 'iron', 'gold'):
                bonus = asc.province_bonus(self.asc, resource) + wonder_bonus(self.reign, resource) + doctrine_bonus(self.reign, resource)
                if bonus: setattr(self.r, resource, max(D(0), getattr(self.r, resource) + self.r.rates()[resource] * bonus * D(dt)))
            self.advance_world(dt)
            asc.apply_disaster(self.asc, self.r, dt); asc.start_disaster(self.asc, self.r, self.world)
            asc.maybe_claim_province(self.asc, self.r, self.world); asc.check_achievements(self.asc, self.r, self.world)
            update_wonders(self.reign, self.r, self.world); update_trade(self.reign, self.r, self.world, dt)
            self.reign.doctrine_time -= dt
            if self.reign.doctrine_time <= 0: choose_doctrine(self.reign, self)
            self.reign.golden_age = max(0.0, self.reign.golden_age - dt)
            if self.r.happiness > 85 and self.asc.stability_value > 80 and not self.asc.disaster:
                self.reign.golden_age = max(self.reign.golden_age, 30.0)
            if self.reign.golden_age > 0:
                self.r.gold += self.r.rates()['gold'] * D('.15') * D(dt)
                self.r.food += max(D(0), self.r.rates()['food']) * D('.15') * D(dt)
            self.reign.famine_warning = self.r.food < self.r.population * D(5)
            self.asc.stability_value += (self.r.happiness - self.asc.stability_value) * D('.001') * D(dt)
            self.asc.legitimacy_value += (self.r.renown + self.r.prestige * D(20)) * D('.00001') * D(dt)
            self.asc.era = max(1, int(self.r.prestige) + 1)
            if now - self.last_ai_action >= .8: self.ai_action(); self.last_ai_action = now
            if now - self.last_ai_eval >= 12: self.ai.evaluate(self.r); self.last_ai_eval = now
        self.last_tick = now
        if now - self.last_save >= 1: g.save_realm(self.r); self.last_save = now
        if now - self.last_ai_save >= 5: save_brain(self.ai); self.last_ai_save = now
        if now - self.last_world_save >= 5: evolved.save_world(self.world); self.last_world_save = now
        if now - self.last_asc_save >= 5: asc.save_state(self.asc); self.last_asc_save = now
        if now - self.last_reign_save >= 5: save_reign(self.reign); self.last_reign_save = now

    def handle(self, key):
        if key == -1: return
        if self.popup:
            if key in (10,13,27,32,ord('d'),ord('D')): self.popup=False
            return
        if key in (ord('q'),ord('Q')): self.running=False; return
        if key in (ord('p'),ord('P'),32): self.paused=not self.paused; return
        if ord('1') <= key <= ord('9'): self.tab,self.sub=key-ord('1'),0; return
        if key == ord('0'): self.tab,self.sub=9,0; return
        if key == ord('-'): self.tab,self.sub=10,0; return
        if key == curses.KEY_RIGHT: self.tab,self.sub=(self.tab+1)%len(self.TABS),0; return
        if key == curses.KEY_LEFT: self.tab,self.sub=(self.tab-1)%len(self.TABS),0; return
        if key in (9,ord(']')): self.sub=(self.sub+1)%2; return
        if key == ord('['): self.sub=(self.sub-1)%2

    def header(self):
        h,w=self.s.getmaxyx()
        if h<8 or w<50: self.add(0,0,'Terminal too small. Resize or press Q.',curses.A_BOLD); return
        title=f' NEURAL REIGN | Era {self.asc.era} | {self.reign.doctrine} Doctrine | {self.r.name} '
        self.add(0,0,title.center(w-1,'='),curses.A_BOLD)
        labels=['1:Command','2:Realm','3:Economy','4:Military','5:World','6:Research','7:Diplomacy','8:Neural','9:Legacy','0:Chronicle','-:Help']
        x=0
        for i,label in enumerate(labels):
            text=f' {label} '
            if x+len(text)<w:self.add(1,x,text,curses.A_REVERSE if i==self.tab else curses.A_DIM)
            x+=len(text)
        alert=[]
        if self.asc.disaster: alert.append(f'{self.asc.disaster} {int(self.asc.disaster_time)}s')
        if self.reign.famine_warning: alert.append('FAMINE RISK')
        if self.reign.golden_age>0: alert.append(f'GOLDEN AGE {int(self.reign.golden_age)}s')
        banner=' | '.join(alert) or 'Realm stable'
        self.add(2,0,f' {evolved.SEASONS[self.world.season]} / {self.world.weather} | {banner} '[:w-1].ljust(w-1),curses.A_REVERSE if alert else curses.A_BOLD)
        self.add(3,0,f' Objective: {self.world.objective} '[:w-1])
        self.add(4,0,f' Gold {g.fmt(self.r.gold)} | Food {g.fmt(self.r.food)} | Pop {g.fmt(self.r.population)} | Power {g.fmt(self.r.military_power())} | Confidence {self.ai.confidence:.0%} '[:w-1].ljust(w-1),curses.A_REVERSE)

    def panel(self,y,x,width,title,rows):
        self.add(y,x,f'[{title}]',curses.A_BOLD)
        for i,(name,value) in enumerate(rows): self.add(y+i+1,x,f'{name:<15}{str(value):>{max(1,width-15)}}')

    def draw(self):
        self.s.erase(); self.header(); h,w=self.s.getmaxyx()
        if h<8 or w<50:self.s.refresh();return
        tab,y=self.TABS[self.tab],6
        if tab=='Command':
            half=max(32,w//2-2)
            self.panel(y,2,half,'NEURAL COMMAND',[('Action',self.ai.last_action),('Result',self.ai.last_result[:26]),('Reason',self.ai.reason[:26]),('Confidence',f'{self.ai.confidence:.0%}'),('Exploration',f'{self.ai.exploration:.3f}')])
            self.panel(y,min(w-31,half+3),max(28,w-half-5),'REALM STATUS',[('Doctrine',self.reign.doctrine),('Stability',f'{self.asc.stability_value:.0f}%'),('Legitimacy',g.fmt(self.asc.legitimacy_value)),('Golden Age',f'{int(self.reign.golden_age)}s'),('Trade Routes',len(self.reign.trade_routes))])
            self.panel(y+8,2,half,'PROGRESS',[('Era',self.asc.era),('Provinces',f'{len(self.asc.provinces)}/{len(asc.PROVINCES)}'),('Wonders',f'{len(self.reign.wonders)}/{len(WONDERS)}'),('Research',g.fmt(self.world.research_value)),('Achievements',f'{len(self.asc.achievements)}/{len(asc.ACHIEVEMENTS)}')])
            top=sorted(self.ai.outcome_memory.items(),key=lambda x:x[1],reverse=True)[:5]
            self.panel(y+8,min(w-31,half+3),max(28,w-half-5),'LEARNED OUTCOMES',[(a,f'{v:+.3f}') for a,v in top])
        elif tab=='Realm':
            for a,b in [('Population',self.r.population),('Free people',self.r.free_people()),('Happiness',self.r.happiness),('Territory',self.r.territory),('Renown',self.r.renown),('Prestige',self.r.prestige),('Worth',g.realm_worth(self.r))]:self.add(y,3,f'{a:<20}{g.fmt(b)}');y+=1
        elif tab=='Economy':
            for name in ('gold','food','wood','stone','iron'):
                bonus=asc.province_bonus(self.asc,name)+wonder_bonus(self.reign,name)+doctrine_bonus(self.reign,name)
                self.add(y,3,f'{name.title():<10}{g.fmt(getattr(self.r,name)):>15} {g.fmt(self.r.rates()[name]):>12}/s bonus {bonus*100:+.0f}%');y+=1
            self.add(y+1,3,f'Trade routes: {len(self.reign.trade_routes)} | Markets: {g.fmt(self.r.markets)} | Doctrine: {self.reign.doctrine}')
        elif tab=='Military':
            for a,b in [('Soldiers',self.r.soldiers),('Archers',self.r.archers),('Knights',self.r.knights),('Power',self.r.military_power()),('Enemy',g.enemy_power(self.r)),('Victories',self.r.victories),('Defeats',self.r.defeats)]:self.add(y,3,f'{a:<18}{g.fmt(b)}');y+=1
        elif tab=='World':
            self.add(y,3,f'Disaster: {self.asc.disaster or "None"}');self.add(y+1,3,f'Golden Age: {int(self.reign.golden_age)}s');y+=3
            for name,kind,amount in asc.PROVINCES:
                mark='✓' if name in self.asc.provinces else '·';self.add(y,3,f'{mark} {name:<20}{kind:<10}+{amount*100:.0f}%');y+=1
        elif tab=='Research':
            self.add(y,3,f'Research {g.fmt(self.world.research_value)} | Technologies {len(self.world.unlocked)}/{len(evolved.TECHS)}');y+=2
            for name,cost,kind,amount in evolved.TECHS:
                mark='✓' if name in self.world.unlocked else '·';self.add(y,3,f'{mark} {name:<23}{cost:>7} RP {kind} +{amount*100:.0f}%');y+=1
        elif tab=='Diplomacy':
            for rival in self.world.rivals:
                attitude=int(rival.get('attitude',0));self.add(y,3,f"{rival['name']:<22}{asc.relation_label(attitude):<11} Power {g.fmt(D(rival['power'])):>10} Wealth {g.fmt(D(rival['wealth'])):>10}");y+=2
            self.add(y,3,f'Active trade routes: {len(self.reign.trade_routes)}')
        elif tab=='Neural':
            rows=[('Generation',self.ai.generation),('Decisions',self.ai.decisions),('Score',f'{self.ai.score:.4f}'),('Best',f'{self.ai.best_score:.4f}'),('Confidence',f'{self.ai.confidence:.0%}'),('Exploration',f'{self.ai.exploration:.4f}'),('Strategy',self.ai.strategy),('Reason',self.ai.reason)]
            for a,b in rows:self.add(y,3,f'{a:<18}{b}');y+=1
            self.add(y+1,3,'Outcome memory: '+', '.join(f'{a} {v:+.2f}' for a,v in sorted(self.ai.outcome_memory.items(),key=lambda x:x[1],reverse=True)[:6]))
        elif tab=='Legacy':
            self.add(y,3,f'Wonders {len(self.reign.wonders)}/{len(WONDERS)} | Achievements {len(self.asc.achievements)}/{len(asc.ACHIEVEMENTS)}');y+=2
            for name,kind,target,bonus_kind,amount in WONDERS:
                mark='✓' if name in self.reign.wonders else '·';self.add(y,3,f'{mark} {name:<20}{kind} {g.fmt(target):>9}  {bonus_kind} +{amount*100:.0f}%');y+=1
        elif tab=='Chronicle':
            messages=self.world.events if self.sub else self.r.messages
            for message in messages[-max(1,h-8):]:self.add(y,3,'• '+message);y+=1
        else:
            for line in ['1-9, 0, - or arrows: view reports','Tab / [ ]: switch report pages','P or Space: pause/resume','Q: save and quit','','All decisions remain neural-controlled. Neural utility shaping, outcome memory and action masking guide the autonomous governor.']:self.add(y,3,line);y+=1
        status='PAUSED' if self.paused else f'AI {self.ai.last_action} ({self.ai.confidence:.0%})'
        self.add(h-2,0,f' {status} | {self.reign.doctrine} doctrine | wonders {len(self.reign.wonders)} | autosaving '.ljust(max(0,w-1)),curses.A_REVERSE)
        if self.popup:self.draw_popup()
        self.s.refresh()

    def run(self):
        try:curses.curs_set(0)
        except curses.error:pass
        self.s.nodelay(True);self.s.timeout(int(g.TICK*1000));self.s.keypad(True)
        try:
            while self.running:self.update();self.draw();self.handle(self.s.getch())
        finally:
            g.save_realm(self.r);save_brain(self.ai);evolved.save_world(self.world);asc.save_state(self.asc);save_reign(self.reign)


def main():
    try:curses.wrapper(lambda screen:Game(screen).run())
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
