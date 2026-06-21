from __future__ import annotations

import curses
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass, field, fields
from decimal import Decimal, InvalidOperation, Overflow, getcontext
from pathlib import Path
from typing import Dict, List, Tuple

getcontext().prec = 80
SAVE_DIR = Path.home() / '.endless_realm_ii'
SAVE_FILE = SAVE_DIR / 'save.json'
AI_FILE = SAVE_DIR / 'neural_ai.json'
TICK = 0.10
MAX_OFFLINE = 60 * 60 * 24 * 30
MAX_EXPONENT = 999999

SUFFIXES = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oc', 'No', 'Dc']
ONES = ['', 'U', 'D', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'O', 'N']
TENS = ['', 'De', 'Vg', 'Tg', 'Qag', 'Qig', 'Sxg', 'Spg', 'Og', 'Ng']
HUNDS = ['', 'Ce', 'Duc', 'Trc', 'Qac', 'Qic', 'Sxc', 'Spc', 'Oc', 'Noc']


def D(value=0) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def finite(value: Decimal, fallback: Decimal = Decimal(0)) -> Decimal:
    value = D(value)
    return value if value.is_finite() else fallback


def safe_pow(base: Decimal, exponent: Decimal) -> Decimal:
    base, exponent = D(base), D(exponent)
    exponent = max(D(-MAX_EXPONENT), min(D(MAX_EXPONENT), exponent))
    try:
        return finite(base ** exponent, D('1E999999'))
    except (InvalidOperation, Overflow, ValueError):
        return D('1E999999')


def suffix_name(index: int) -> str:
    if index < 0:
        return ''
    if index < len(SUFFIXES):
        return SUFFIXES[index]
    n = index - len(SUFFIXES) + 1
    parts = []
    while n:
        chunk, n = n % 1000, n // 1000
        h, rem = divmod(chunk, 100)
        t, o = divmod(rem, 10)
        parts.append(HUNDS[h] + TENS[t] + ONES[o])
    return ''.join(reversed(parts)) + 'illion'


def fmt(value: Decimal, precision: int = 2) -> str:
    try:
        value = D(value)
    except (InvalidOperation, ValueError, TypeError):
        return '0'
    if value.is_nan():
        return '0'
    if value.is_infinite():
        return '∞' if value > 0 else '-∞'
    sign = '-' if value < 0 else ''
    value = abs(value)
    if value < 1000:
        if value == value.to_integral():
            return f'{sign}{int(value):,}'
        return f'{sign}{value:.{precision}f}'
    exponent = max(1, int(value.adjusted() // 3))
    try:
        scaled = value.scaleb(-3 * exponent)
    except (InvalidOperation, Overflow):
        return f'{sign}1e{value.adjusted()}'
    return f'{sign}{scaled:.{precision}f}{suffix_name(exponent)}'


def decimal_log_feature(value: Decimal) -> float:
    value = max(D(1), finite(value, D(1)))
    try:
        return max(-50.0, min(50.0, float(value.log10() / D(20))))
    except (InvalidOperation, Overflow, ValueError):
        return 50.0


@dataclass
class Realm:
    name: str = "MattKoRn's Realm"
    age: Decimal = D(0)
    gold: Decimal = D(500)
    food: Decimal = D(800)
    wood: Decimal = D(300)
    stone: Decimal = D(200)
    iron: Decimal = D(50)
    population: Decimal = D(120)
    happiness: Decimal = D(65)
    renown: Decimal = D(0)
    territory: Decimal = D(1)
    threat: Decimal = D(1)
    victories: Decimal = D(0)
    defeats: Decimal = D(0)
    prestige: Decimal = D(0)
    farmers: Decimal = D(20)
    woodcutters: Decimal = D(5)
    miners: Decimal = D(3)
    builders: Decimal = D(2)
    soldiers: Decimal = D(10)
    archers: Decimal = D(0)
    knights: Decimal = D(0)
    farms: Decimal = D(1)
    lumberyards: Decimal = D(0)
    quarries: Decimal = D(0)
    mines: Decimal = D(0)
    markets: Decimal = D(0)
    barracks: Decimal = D(0)
    walls: Decimal = D(0)
    castles: Decimal = D(0)
    tax_rate: Decimal = D('0.15')
    auto_ai: bool = False
    last_saved: float = field(default_factory=time.time)
    messages: List[str] = field(default_factory=lambda: ['Your endless reign begins.'])

    def sanitize(self) -> None:
        for f in fields(self):
            current = getattr(self, f.name)
            if not isinstance(current, Decimal):
                continue
            value = finite(current, D(0))
            if f.name == 'happiness':
                value = max(D(0), min(D(100), value))
            elif f.name == 'tax_rate':
                value = max(D(0), min(D(1), value))
            else:
                value = max(D(0), value)
            setattr(self, f.name, value)
        self.population = max(D(10), self.population)
        self.territory = max(D(1), self.territory)
        self.threat = max(D(1), self.threat)
        if not isinstance(self.messages, list):
            self.messages = ['Recovered a damaged chronicle.']
        self.messages = [str(m)[:500] for m in self.messages[-80:]]

    def total_workers(self) -> Decimal:
        return sum((self.farmers, self.woodcutters, self.miners, self.builders,
                    self.soldiers, self.archers, self.knights), D(0))

    def free_people(self) -> Decimal:
        return max(D(0), self.population - self.total_workers())

    def military_power(self) -> Decimal:
        base = self.soldiers + self.archers * D('2.5') + self.knights * D(7)
        fort = D(1) + self.walls * D('0.08') + self.castles * D('0.25')
        return finite(base * fort * (D('0.7') + self.happiness / D(200)))

    def rates(self) -> Dict[str, Decimal]:
        prestige_mult = D(1) + self.prestige * D('0.10')
        return {
            'food': (self.farmers * D('0.45') * (D(1) + self.farms * D('0.12')) - self.population * D('0.08')) * prestige_mult,
            'wood': self.woodcutters * D('0.35') * (D(1) + self.lumberyards * D('0.15')) * prestige_mult,
            'stone': self.miners * D('0.17') * (D(1) + self.quarries * D('0.13')) * prestige_mult,
            'iron': self.miners * D('0.08') * (D(1) + self.mines * D('0.15')) * prestige_mult,
            'gold': self.population * self.tax_rate * D('0.045') * (D(1) + self.markets * D('0.10')) * prestige_mult,
        }

    def tick(self, seconds) -> None:
        dt = max(D(0), min(D(MAX_OFFLINE), D(seconds)))
        rates = self.rates()
        self.age += dt
        for key, rate in rates.items():
            setattr(self, key, max(D(0), finite(getattr(self, key) + rate * dt)))
        if self.food > self.population * D(2):
            self.population += self.population * D('0.00012') * (self.happiness / D(100)) * dt
        if self.food <= 0:
            self.population = max(D(10), self.population * max(D(0), D(1) - D('0.0003') * dt))
            self.happiness = max(D(0), self.happiness - D('0.08') * dt)
        else:
            target = D(70) - self.tax_rate * D(100)
            self.happiness += (target - self.happiness) * D('0.002') * dt
        self.threat += (D('0.00018') + self.territory * D('0.000002')) * dt
        self.sanitize()

    def log(self, text: str) -> None:
        self.messages.append(str(text)[:500])
        self.messages = self.messages[-80:]


class NeuralGovernor:
    ACTIONS = ['farm', 'wood', 'mine', 'soldier', 'archer', 'knight', 'build_farm', 'build_market', 'build_wall', 'attack']

    def __init__(self, data=None):
        self.inputs, self.hidden, self.outputs = 10, 12, len(self.ACTIONS)
        self.generation, self.score, self.best_score = 1, 0.0, -1e99
        self.mutation, self.last_action = 0.14, 'observing'
        self.w1 = [[random.uniform(-1, 1) for _ in range(self.inputs)] for _ in range(self.hidden)]
        self.w2 = [[random.uniform(-1, 1) for _ in range(self.hidden)] for _ in range(self.outputs)]
        self.best_w1 = [row[:] for row in self.w1]
        self.best_w2 = [row[:] for row in self.w2]
        if isinstance(data, dict):
            self._load(data)

    def _valid_matrix(self, matrix, rows, cols):
        return (isinstance(matrix, list) and len(matrix) == rows and
                all(isinstance(r, list) and len(r) == cols and
                    all(isinstance(v, (int, float)) and math.isfinite(v) for v in r) for r in matrix))

    def _load(self, data):
        for name, rows, cols in [('w1', self.hidden, self.inputs), ('w2', self.outputs, self.hidden),
                                 ('best_w1', self.hidden, self.inputs), ('best_w2', self.outputs, self.hidden)]:
            if self._valid_matrix(data.get(name), rows, cols):
                setattr(self, name, data[name])
        try:
            self.generation = max(1, int(data.get('generation', 1)))
        except (TypeError, ValueError):
            self.generation = 1
        for name, default in [('score', 0.0), ('best_score', -1e99), ('mutation', 0.14)]:
            try:
                value = float(data.get(name, default))
                setattr(self, name, value if math.isfinite(value) else default)
            except (TypeError, ValueError):
                setattr(self, name, default)
        self.mutation = max(0.001, min(1.0, self.mutation))
        self.last_action = str(data.get('last_action', 'observing'))[:40]

    def features(self, r: Realm) -> List[float]:
        return [decimal_log_feature(x) for x in (r.gold, r.food, r.wood, r.stone, r.iron, r.population)] + [
            float(r.happiness / D(100)), decimal_log_feature(r.military_power()),
            decimal_log_feature(r.threat), float(r.free_people() / max(D(1), r.population))]

    def choose(self, r: Realm) -> str:
        x = self.features(r)
        h = [math.tanh(sum(w * v for w, v in zip(row, x))) for row in self.w1]
        y = [sum(w * v for w, v in zip(row, h)) + random.uniform(-0.03, 0.03) for row in self.w2]
        self.last_action = self.ACTIONS[max(range(len(y)), key=y.__getitem__)]
        return self.last_action

    def evaluate(self, r: Realm) -> None:
        score = decimal_log_feature(r.population * r.territory * (r.renown + D(1))) * 20 + float(r.happiness / D(100))
        self.score = score
        if score > self.best_score:
            self.best_score = score
            self.best_w1 = [row[:] for row in self.w1]
            self.best_w2 = [row[:] for row in self.w2]
        else:
            self.w1 = [[v + random.gauss(0, self.mutation) for v in row] for row in self.best_w1]
            self.w2 = [[v + random.gauss(0, self.mutation) for v in row] for row in self.best_w2]
            self.generation += 1
            self.mutation = max(0.015, self.mutation * 0.999)

    def serialize(self):
        return self.__dict__


BUILDINGS = {
    'farm': ('farms', {'gold': 100, 'wood': 80, 'stone': 20}),
    'lumberyard': ('lumberyards', {'gold': 130, 'wood': 100, 'stone': 30}),
    'quarry': ('quarries', {'gold': 180, 'wood': 70, 'stone': 60}),
    'mine': ('mines', {'gold': 300, 'wood': 120, 'stone': 120}),
    'market': ('markets', {'gold': 500, 'wood': 180, 'stone': 140}),
    'barracks': ('barracks', {'gold': 700, 'wood': 220, 'stone': 220}),
    'wall': ('walls', {'gold': 1000, 'wood': 300, 'stone': 700}),
    'castle': ('castles', {'gold': 5000, 'wood': 1200, 'stone': 3000, 'iron': 500}),
}

RECRUITS = {
    'farmer': ('farmers', {'gold': 2}), 'woodcutter': ('woodcutters', {'gold': 3}),
    'miner': ('miners', {'gold': 5}), 'builder': ('builders', {'gold': 8}),
    'soldier': ('soldiers', {'gold': 18, 'iron': 1}),
    'archer': ('archers', {'gold': 35, 'wood': 2, 'iron': 1}),
    'knight': ('knights', {'gold': 120, 'iron': 8}),
}


def scaled_cost(base: Dict[str, int], count: Decimal) -> Dict[str, Decimal]:
    scale = safe_pow(D('1.18'), max(D(0), count))
    return {key: finite(D(value) * scale, D('1E999999')) for key, value in base.items()}


def can_pay(r: Realm, costs) -> bool:
    return all(getattr(r, key) >= value for key, value in costs.items())


def pay(r: Realm, costs) -> None:
    for key, value in costs.items():
        setattr(r, key, max(D(0), getattr(r, key) - value))


def build(r: Realm, kind: str) -> bool:
    if kind not in BUILDINGS:
        r.log('Unknown building order ignored.')
        return False
    attr, base = BUILDINGS[kind]
    costs = scaled_cost(base, getattr(r, attr))
    if not can_pay(r, costs):
        r.log(f'Not enough resources for {kind}.')
        return False
    pay(r, costs)
    setattr(r, attr, getattr(r, attr) + D(1))
    r.log(f"Built {kind}. Cost: " + ', '.join(f'{fmt(v)} {k}' for k, v in costs.items()))
    return True


def recruit(r: Realm, unit: str, amount=D(1)) -> bool:
    if unit not in RECRUITS:
        r.log('Unknown recruitment order ignored.')
        return False
    attr, one = RECRUITS[unit]
    amount = max(D(0), min(D(amount), r.free_people())).to_integral_value(rounding='ROUND_FLOOR')
    costs = {key: D(value) * amount for key, value in one.items()}
    if amount < 1 or not can_pay(r, costs):
        r.log(f'Could not assign {unit}; check free population and resources.')
        return False
    pay(r, costs)
    setattr(r, attr, getattr(r, attr) + amount)
    r.log(f'Assigned {fmt(amount)} {unit}(s).')
    return True


def enemy_power(r: Realm) -> Decimal:
    return finite(safe_pow(r.threat, D('1.12')) * D(18), D('1E999999'))


def attack(r: Realm) -> None:
    enemy = enemy_power(r) * (D('0.8') + D(str(random.random())) * D('0.5'))
    power = r.military_power() * (D('0.85') + D(str(random.random())) * D('0.35'))
    if power >= enemy:
        reward = enemy * D(5)
        land = max(D(1), enemy.sqrt() / D(5))
        r.gold += reward
        r.food += reward * D('0.35')
        r.territory += land
        r.renown += enemy.sqrt()
        r.victories += D(1)
        r.threat = max(D(1), r.threat * D('0.72'))
        r.log(f'Victory! Enemy {fmt(enemy)} defeated; gained {fmt(reward)} gold and {fmt(land)} land.')
    else:
        ratio = max(D('0.05'), power / max(D(1), enemy))
        loss_mult = max(D(0), D(1) - ratio * D('0.6'))
        r.soldiers *= loss_mult
        r.archers *= loss_mult
        r.knights *= loss_mult
        r.happiness = max(D(5), r.happiness - D(8))
        r.defeats += D(1)
        r.threat = max(D(1), r.threat * D('0.93'))
        r.log(f'Defeat, but the realm endures. Enemy power was {fmt(enemy)}.')
    r.sanitize()


def realm_worth(r: Realm) -> Decimal:
    return r.gold + r.population * D(100) + r.territory * D(1000) + r.renown * D(500)


def prestige_requirement(r: Realm) -> Decimal:
    return D(1_000_000) * safe_pow(D(10), r.prestige)


def prestige(r: Realm) -> None:
    requirement = prestige_requirement(r)
    if realm_worth(r) < requirement:
        r.log(f'Prestige requires realm worth {fmt(requirement)}.')
        return
    old, name, messages = r.prestige + D(1), r.name, r.messages[-5:]
    fresh = Realm(name=name, prestige=old)
    fresh.log(f'Prestiged to dynasty level {fmt(old)}. Permanent production +{fmt(old * D(10))}%.')
    fresh.messages = messages + fresh.messages
    r.__dict__.update(fresh.__dict__)


def atomic_json_write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)


def realm_to_json(r: Realm):
    return {key: str(value) if isinstance(value, Decimal) else value for key, value in asdict(r).items()}


def save_realm(r: Realm) -> None:
    try:
        r.sanitize()
        r.last_saved = time.time()
        atomic_json_write(SAVE_FILE, realm_to_json(r))
    except (OSError, TypeError, ValueError) as exc:
        r.log(f'Autosave warning: {exc}')


def load_realm() -> Tuple[Realm, float]:
    if not SAVE_FILE.exists():
        return Realm(), 0.0
    try:
        data = json.loads(SAVE_FILE.read_text(encoding='utf-8'))
        template = Realm()
        values = {}
        for f in fields(Realm):
            if f.name not in data:
                continue
            raw = data[f.name]
            if isinstance(getattr(template, f.name), Decimal):
                raw = D(raw)
            values[f.name] = raw
        realm = Realm(**values)
        realm.sanitize()
        offline = max(0.0, min(float(MAX_OFFLINE), time.time() - float(data.get('last_saved', time.time()))))
        return realm, offline
    except (OSError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
        try:
            SAVE_FILE.replace(SAVE_FILE.with_suffix('.corrupt.json'))
        except OSError:
            pass
        return Realm(messages=['A damaged save was quarantined; a fresh realm was created.']), 0.0


def save_ai(ai: NeuralGovernor) -> None:
    try:
        atomic_json_write(AI_FILE, ai.serialize())
    except (OSError, TypeError, ValueError):
        pass


def load_ai() -> NeuralGovernor:
    try:
        return NeuralGovernor(json.loads(AI_FILE.read_text(encoding='utf-8')))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return NeuralGovernor()


class Game:
    TABS = ['Realm', 'Economy', 'Military', 'World', 'Neural AI', 'Chronicle', 'Help']
    SUBTABS = {'Realm': ['Overview', 'Dynasty'], 'Economy': ['Workforce', 'Buildings'],
               'Military': ['Army', 'Campaign'], 'World': ['Expansion', 'Scaling'],
               'Neural AI': ['Governor', 'Learning'], 'Chronicle': ['Recent', 'All'], 'Help': ['Keys', 'About']}

    def __init__(self, stdscr):
        self.s = stdscr
        self.r, self.offline = load_realm()
        self.ai = load_ai()
        self.tab = self.sub = self.sel = 0
        now = time.monotonic()
        self.last_tick = self.last_save = self.last_ai_save = self.last_ai_action = self.last_ai_eval = now
        self.popup = self.offline > 2
        self.offline_summary = self.apply_offline(self.offline) if self.popup else ''
        self.running = True

    def apply_offline(self, seconds):
        capped = min(max(0.0, float(seconds)), MAX_OFFLINE)
        before = {k: getattr(self.r, k) for k in ['gold', 'food', 'wood', 'stone', 'iron', 'population']}
        self.r.tick(capped)
        gains = [f'{k.title()}: {fmt(getattr(self.r, k) - v)}' for k, v in before.items()]
        return f'Away for {int(seconds)} seconds (credited up to 30 days).\n' + '   '.join(gains)

    def ai_action(self):
        try:
            action = self.ai.choose(self.r)
            if action in ('farm', 'wood', 'mine', 'soldier', 'archer', 'knight'):
                unit = {'farm': 'farmer', 'wood': 'woodcutter', 'mine': 'miner'}.get(action, action)
                recruit(self.r, unit, max(D(1), self.r.free_people() // D(20)))
            elif action == 'build_farm': build(self.r, 'farm')
            elif action == 'build_market': build(self.r, 'market')
            elif action == 'build_wall': build(self.r, 'wall')
            elif action == 'attack' and self.r.military_power() > D(5): attack(self.r)
        except (ArithmeticError, ValueError, TypeError) as exc:
            self.r.auto_ai = False
            self.r.log(f'Neural governor paused after an error: {exc}')

    def update(self):
        now = time.monotonic()
        self.r.tick(max(0.0, min(1.0, now - self.last_tick)))
        self.last_tick = now
        if self.r.auto_ai and now - self.last_ai_action >= 0.8:
            self.ai_action(); self.last_ai_action = now
        if now - self.last_ai_eval >= 20:
            self.ai.evaluate(self.r); self.last_ai_eval = now
        if now - self.last_save >= 1:
            save_realm(self.r); self.last_save = now
        if now - self.last_ai_save >= 5:
            save_ai(self.ai); self.last_ai_save = now

    def add(self, y, x, text, attr=0):
        h, w = self.s.getmaxyx()
        if not (0 <= y < h and 0 <= x < w) or w <= 1:
            return
        try:
            self.s.addnstr(y, x, str(text), max(0, w - x - 1), attr)
        except curses.error:
            pass

    def header(self):
        h, w = self.s.getmaxyx()
        if h < 5 or w < 30:
            self.add(0, 0, 'Terminal too small. Resize or press Q.', curses.A_BOLD)
            return
        self.add(0, 0, f' ENDLESS REALM II | {self.r.name} '.center(w - 1, '='), curses.A_BOLD)
        x = 1
        for i, tab in enumerate(self.TABS):
            label = f' {i+1}:{tab} '
            self.add(1, x, label, curses.A_REVERSE if i == self.tab else curses.A_DIM)
            x += len(label) + 1
        x = 2
        for i, name in enumerate(self.SUBTABS[self.TABS[self.tab]]):
            label = f'[{name}]'
            self.add(2, x, label, curses.A_BOLD if i == self.sub else 0)
            x += len(label) + 2
        rates = self.r.rates()
        bar = f" Gold {fmt(self.r.gold)} ({fmt(rates['gold'])}/s) | Food {fmt(self.r.food)} ({fmt(rates['food'])}/s) | Pop {fmt(self.r.population)} | Power {fmt(self.r.military_power())} "
        self.add(3, 0, bar[:max(0, w - 1)].ljust(max(0, w - 1)), curses.A_REVERSE)

    def menu(self, y, items):
        if items:
            self.sel %= len(items)
        for i, (key, label, detail) in enumerate(items):
            self.add(y + i, 3, f'{key:>2}  {label:<24} {detail}', curses.A_REVERSE if i == self.sel else 0)

    def draw(self):
        self.s.erase(); self.header()
        h, w = self.s.getmaxyx()
        if h < 5 or w < 30:
            self.s.refresh(); return
        tab, sub, y = self.TABS[self.tab], self.sub, 5
        if tab == 'Realm' and sub == 0:
            lines = [('Age', f'{fmt(self.r.age)} seconds'), ('Population', fmt(self.r.population)),
                     ('Free people', fmt(self.r.free_people())), ('Happiness', f'{self.r.happiness:.1f}%'),
                     ('Territory', fmt(self.r.territory)), ('Renown', fmt(self.r.renown)), ('Threat', fmt(self.r.threat)),
                     ('Victories / Defeats', f'{fmt(self.r.victories)} / {fmt(self.r.defeats)}')]
            for key, value in lines: self.add(y, 3, f'{key:<22} {value}'); y += 1
        elif tab == 'Realm':
            self.add(y, 3, f'Dynasty level: {fmt(self.r.prestige)}   Permanent production bonus: {fmt(self.r.prestige * D(10))}%')
            self.add(y + 2, 3, f'Next prestige requires realm worth: {fmt(prestige_requirement(self.r))}')
            self.add(y + 4, 3, 'Press P to prestige. Your dynasty continues forever.')
        elif tab == 'Economy' and sub == 0:
            self.menu(y, [('F', 'Assign farmer', fmt(self.r.farmers)), ('W', 'Assign woodcutter', fmt(self.r.woodcutters)),
                          ('M', 'Assign miner', fmt(self.r.miners)), ('B', 'Assign builder', fmt(self.r.builders))])
        elif tab == 'Economy':
            items = []
            for key, kind in zip('FLQMKTWC', BUILDINGS):
                attr, base = BUILDINGS[kind]; costs = scaled_cost(base, getattr(self.r, attr))
                items.append((key, kind.title(), f"Owned {fmt(getattr(self.r, attr))} | " + ', '.join(f'{fmt(v)} {k}' for k, v in costs.items())))
            self.menu(y, items)
        elif tab == 'Military' and sub == 0:
            self.menu(y, [('S', 'Recruit soldier', fmt(self.r.soldiers)), ('A', 'Recruit archer', fmt(self.r.archers)),
                          ('K', 'Recruit knight', fmt(self.r.knights)), ('B', 'Build barracks', fmt(self.r.barracks)),
                          ('W', 'Build wall', fmt(self.r.walls)), ('C', 'Build castle', fmt(self.r.castles))])
        elif tab == 'Military':
            self.add(y, 3, f'Estimated enemy power: {fmt(enemy_power(self.r))}')
            self.add(y + 1, 3, f'Your fortified power:  {fmt(self.r.military_power())}')
            self.add(y + 3, 3, 'Press A to attack. Defeat never ends the game.')
        elif tab == 'World' and sub == 0:
            self.add(y, 3, f'Known territory: {fmt(self.r.territory)}')
            self.add(y + 1, 3, f'World threat:    {fmt(self.r.threat)}')
            self.add(y + 3, 3, 'Difficulty and rewards scale forever.')
        elif tab == 'World':
            for i in range(min(12, max(0, h - y - 3))): self.add(y + i, 3, f'10^{i*3:>3}: {suffix_name(i) or "units"}')
        elif tab == 'Neural AI' and sub == 0:
            self.add(y, 3, f"Autonomous governor: {'ENABLED' if self.r.auto_ai else 'DISABLED'}  (press T to toggle)")
            self.add(y + 2, 3, f'Last decision: {self.ai.last_action}')
        elif tab == 'Neural AI':
            self.add(y, 3, f'Generation: {self.ai.generation}')
            self.add(y + 1, 3, f'Current score: {self.ai.score:.5f}')
            self.add(y + 2, 3, f'Best score: {self.ai.best_score:.5f}')
            self.add(y + 3, 3, f'Mutation rate: {self.ai.mutation:.5f}')
        elif tab == 'Chronicle':
            msgs = self.r.messages[-12:] if sub == 0 else self.r.messages
            for msg in msgs[-max(1, h - 7):]: self.add(y, 3, '• ' + msg); y += 1
        elif tab == 'Help' and sub == 0:
            for line in ['1-7 / Left-Right: tabs', 'Tab / [ ]: sub-tabs', 'Up/Down: select', 'Enter: act',
                         'T: neural governor', 'P: prestige', 'Q: save and quit']:
                self.add(y, 3, line); y += 1
        else:
            self.add(y, 3, 'An original endless medieval realm-management game.')
        self.add(h - 2, 0, ' Autosaves: realm 1s | neural AI 5s | Q quits '.ljust(max(0, w - 1)), curses.A_REVERSE)
        if self.popup: self.draw_popup()
        self.s.refresh()

    def draw_popup(self):
        h, w = self.s.getmaxyx()
        if h < 6 or w < 24:
            self.add(max(0, h - 1), 0, 'Offline gains applied. Press D.', curses.A_REVERSE)
            return
        ph, pw = min(8, h - 1), min(90, w - 2)
        y, x = max(0, (h - ph) // 2), max(0, (w - pw) // 2)
        try:
            win = curses.newwin(ph, pw, y, x); win.box()
            win.addnstr(1, 2, ' OFFLINE PROGRESS ', max(1, pw - 4), curses.A_BOLD)
            lines = []
            width = max(1, pw - 5)
            for raw in self.offline_summary.split('\n'):
                lines.extend(raw[i:i + width] for i in range(0, max(1, len(raw)), width))
            for i, line in enumerate(lines[:max(0, ph - 4)]): win.addnstr(2 + i, 2, line, max(1, pw - 4))
            win.addnstr(ph - 2, 2, 'Enter/Esc/D/Space dismisses', max(1, pw - 4), curses.A_REVERSE)
            win.refresh()
        except curses.error:
            pass

    def selected_action(self):
        tab = self.TABS[self.tab]
        if tab == 'Economy' and self.sub == 0:
            recruit(self.r, ['farmer', 'woodcutter', 'miner', 'builder'][self.sel % 4])
        elif tab == 'Economy' and self.sub == 1:
            build(self.r, list(BUILDINGS)[self.sel % len(BUILDINGS)])
        elif tab == 'Military' and self.sub == 0:
            actions = [lambda: recruit(self.r, 'soldier'), lambda: recruit(self.r, 'archer'), lambda: recruit(self.r, 'knight'),
                       lambda: build(self.r, 'barracks'), lambda: build(self.r, 'wall'), lambda: build(self.r, 'castle')]
            actions[self.sel % len(actions)]()
        elif tab == 'Military' and self.sub == 1:
            attack(self.r)

    def handle(self, key):
        if key == -1:
            return
        if self.popup:
            if key in (10, 13, 27, 32, ord('d'), ord('D')): self.popup = False
            return
        if key in (ord('q'), ord('Q')): self.running = False; return
        if ord('1') <= key <= ord('7'): self.tab, self.sub, self.sel = key - ord('1'), 0, 0; return
        if key == curses.KEY_RIGHT: self.tab, self.sub, self.sel = (self.tab + 1) % len(self.TABS), 0, 0; return
        if key == curses.KEY_LEFT: self.tab, self.sub, self.sel = (self.tab - 1) % len(self.TABS), 0, 0; return
        if key in (9, ord(']')): self.sub, self.sel = (self.sub + 1) % len(self.SUBTABS[self.TABS[self.tab]]), 0; return
        if key == ord('['): self.sub, self.sel = (self.sub - 1) % len(self.SUBTABS[self.TABS[self.tab]]), 0; return
        if key == curses.KEY_UP: self.sel = max(0, self.sel - 1); return
        if key == curses.KEY_DOWN: self.sel += 1; return
        if key in (10, 13): self.selected_action(); return
        if key in (ord('t'), ord('T')):
            self.r.auto_ai = not self.r.auto_ai; self.r.log(f"Neural governor {'enabled' if self.r.auto_ai else 'disabled'}."); return
        if key in (ord('p'), ord('P')): prestige(self.r); return
        ch = chr(key).lower() if 0 <= key < 256 else ''
        tab = self.TABS[self.tab]
        if tab == 'Economy' and self.sub == 0:
            mapping = {'f': 'farmer', 'w': 'woodcutter', 'm': 'miner', 'b': 'builder'}
            if ch in mapping: recruit(self.r, mapping[ch], 10 if chr(key).isupper() else 1)
        elif tab == 'Economy' and self.sub == 1:
            mapping = dict(zip('flqmktwc', BUILDINGS))
            if ch in mapping: build(self.r, mapping[ch])
        elif tab == 'Military' and self.sub == 0:
            if ch in 'sak': recruit(self.r, {'s': 'soldier', 'a': 'archer', 'k': 'knight'}[ch])
            elif ch in {'b', 'w', 'c'}: build(self.r, {'b': 'barracks', 'w': 'wall', 'c': 'castle'}[ch])
        elif tab == 'Military' and self.sub == 1 and ch == 'a': attack(self.r)

    def run(self):
        try: curses.curs_set(0)
        except curses.error: pass
        self.s.nodelay(True); self.s.timeout(int(TICK * 1000)); self.s.keypad(True)
        try:
            while self.running:
                self.update(); self.draw(); self.handle(self.s.getch())
        finally:
            save_realm(self.r); save_ai(self.ai)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
