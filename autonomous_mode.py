from __future__ import annotations
import curses, json, random, time
import game_core as g

D = g.D
AI_FILE = g.SAVE_DIR / 'neural_ai_autonomous.json'

ACTIONS = [
    'wait', 'farmer', 'woodcutter', 'miner', 'builder',
    'soldier', 'archer', 'knight', 'farm', 'lumberyard',
    'quarry', 'mine', 'market', 'barracks', 'wall', 'castle',
    'tax_down', 'tax_up', 'attack', 'prestige'
]

class NeuralGovernor(g.NeuralGovernor):
    ACTIONS = ACTIONS

    def __init__(self, data=None):
        super().__init__(None)
        self.outputs = len(self.ACTIONS)
        self.w2 = [[random.uniform(-1, 1) for _ in range(self.hidden)] for _ in range(self.outputs)]
        self.best_w2 = [row[:] for row in self.w2]
        self.decisions = 0
        self.last_result = 'Autonomous governor online.'
        self.action_counts = {name: 0 for name in self.ACTIONS}
        if isinstance(data, dict):
            self._load_auto(data)

    def _load_auto(self, data):
        self._load(data)
        if not self._valid_matrix(data.get('w2'), self.outputs, self.hidden):
            self.w2 = [[random.uniform(-1, 1) for _ in range(self.hidden)] for _ in range(self.outputs)]
        if not self._valid_matrix(data.get('best_w2'), self.outputs, self.hidden):
            self.best_w2 = [row[:] for row in self.w2]
        try:
            self.decisions = max(0, int(data.get('decisions', 0)))
        except (TypeError, ValueError):
            self.decisions = 0
        self.last_result = str(data.get('last_result', 'State restored.'))[:160]
        counts = data.get('action_counts', {})
        if isinstance(counts, dict):
            for name in self.ACTIONS:
                try: self.action_counts[name] = max(0, int(counts.get(name, 0)))
                except (TypeError, ValueError): pass

    def choose(self, realm):
        action = super().choose(realm)
        self.decisions += 1
        self.action_counts[action] += 1
        return action


def load_ai():
    try:
        return NeuralGovernor(json.loads(AI_FILE.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return NeuralGovernor()


def save_ai(ai):
    try: g.atomic_json_write(AI_FILE, ai.serialize())
    except (OSError, ValueError, TypeError): pass


def batch_size(realm, unit):
    _, costs = g.RECRUITS[unit]
    amount = realm.free_people()
    for resource, price in costs.items():
        amount = min(amount, getattr(realm, resource) // D(price))
    return max(D(0), min(amount, max(D(1), realm.population // D(40))))


def execute(ai, realm, action):
    if action == 'wait':
        ai.last_result = 'Observed the realm and conserved resources.'
        return
    if action in g.RECRUITS:
        amount = batch_size(realm, action)
        ok = g.recruit(realm, action, amount)
        ai.last_result = f'Assigned {g.fmt(amount)} {action}(s).' if ok else f'Could not assign {action}s.'
        return
    if action in g.BUILDINGS:
        ok = g.build(realm, action)
        ai.last_result = f'Built {action}.' if ok else f'{action.title()} was unaffordable.'
        return
    if action == 'tax_down':
        realm.tax_rate = max(D('0.02'), realm.tax_rate - D('0.02'))
        ai.last_result = f'Taxes lowered to {realm.tax_rate * D(100):.0f}%.'
        realm.log(ai.last_result)
        return
    if action == 'tax_up':
        realm.tax_rate = min(D('0.60'), realm.tax_rate + D('0.02'))
        ai.last_result = f'Taxes raised to {realm.tax_rate * D(100):.0f}%.'
        realm.log(ai.last_result)
        return
    if action == 'attack':
        old = realm.victories
        g.attack(realm)
        ai.last_result = 'Campaign won.' if realm.victories > old else 'Campaign lost; the dynasty survives.'
        return
    old = realm.prestige
    g.prestige(realm)
    ai.last_result = f'Prestiged to {g.fmt(realm.prestige)}.' if realm.prestige > old else 'Prestige threshold not reached.'


class Game(g.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.ai = load_ai()
        self.r.auto_ai = True
        self.paused = False
        self.r.log('Neural-only mode enabled. All manual realm actions are disabled.')

    def ai_action(self):
        try: execute(self.ai, self.r, self.ai.choose(self.r))
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Decision rejected safely: {exc}'[:160]

    def update(self):
        now = time.monotonic()
        if not self.paused:
            self.r.tick(max(0.0, min(1.0, now - self.last_tick)))
            if now - self.last_ai_action >= 0.55:
                self.ai_action(); self.last_ai_action = now
            if now - self.last_ai_eval >= 12:
                self.ai.evaluate(self.r); self.last_ai_eval = now
        self.last_tick = now
        if now - self.last_save >= 1:
            g.save_realm(self.r); self.last_save = now
        if now - self.last_ai_save >= 5:
            save_ai(self.ai); self.last_ai_save = now

    def handle(self, key):
        if key == -1: return
        if self.popup:
            if key in (10, 13, 27, 32, ord('d'), ord('D')): self.popup = False
            return
        if key in (ord('q'), ord('Q')): self.running = False; return
        if key in (ord('p'), ord('P'), 32): self.paused = not self.paused; return
        if ord('1') <= key <= ord('7'):
            self.tab, self.sub, self.sel = key - ord('1'), 0, 0; return
        if key == curses.KEY_RIGHT:
            self.tab, self.sub = (self.tab + 1) % len(self.TABS), 0; return
        if key == curses.KEY_LEFT:
            self.tab, self.sub = (self.tab - 1) % len(self.TABS), 0; return
        if key in (9, ord(']')):
            self.sub = (self.sub + 1) % 2; return
        if key == ord('['): self.sub = (self.sub - 1) % 2

    def selected_action(self):
        return

    def draw(self):
        self.s.erase(); self.header()
        h, w = self.s.getmaxyx()
        if h < 5 or w < 30:
            self.s.refresh(); return
        tab, y = self.TABS[self.tab], 5
        if tab == 'Realm':
            rows = [('Simulation', 'PAUSED' if self.paused else 'RUNNING'), ('Population', g.fmt(self.r.population)),
                    ('Happiness', f'{self.r.happiness:.1f}%'), ('Taxes', f'{self.r.tax_rate * D(100):.0f}%'),
                    ('Territory', g.fmt(self.r.territory)), ('Prestige', g.fmt(self.r.prestige)),
                    ('Realm worth', g.fmt(g.realm_worth(self.r)))]
            for name, value in rows: self.add(y, 3, f'{name:<18}{value}'); y += 1
        elif tab == 'Economy':
            if self.sub == 0:
                rates = self.r.rates()
                for name in ('gold', 'food', 'wood', 'stone', 'iron'):
                    self.add(y, 3, f'{name.title():<10}{g.fmt(getattr(self.r, name)):>14}  {g.fmt(rates[name]):>12}/s'); y += 1
            else:
                for name, (attr, _) in g.BUILDINGS.items():
                    self.add(y, 3, f'{name.title():<16}{g.fmt(getattr(self.r, attr))}'); y += 1
        elif tab == 'Military':
            rows = [('Soldiers', self.r.soldiers), ('Archers', self.r.archers), ('Knights', self.r.knights),
                    ('Power', self.r.military_power()), ('Enemy', g.enemy_power(self.r)),
                    ('Victories', self.r.victories), ('Defeats', self.r.defeats)]
            for name, value in rows: self.add(y, 3, f'{name:<16}{g.fmt(value)}'); y += 1
        elif tab == 'World':
            self.add(y, 3, f'Territory: {g.fmt(self.r.territory)}')
            self.add(y + 1, 3, f'Threat: {g.fmt(self.r.threat)}')
            self.add(y + 3, 3, 'Expansion, combat and prestige continue forever under neural control.')
        elif tab == 'Neural AI':
            rows = [('Last action', self.ai.last_action), ('Result', self.ai.last_result),
                    ('Decisions', f'{self.ai.decisions:,}'), ('Generation', f'{self.ai.generation:,}'),
                    ('Score', f'{self.ai.score:.5f}'), ('Best score', f'{self.ai.best_score:.5f}'),
                    ('Mutation', f'{self.ai.mutation:.5f}')]
            for name, value in rows: self.add(y, 3, f'{name:<16}{value}'); y += 1
        elif tab == 'Chronicle':
            for message in self.r.messages[-max(1, h - 7):]:
                self.add(y, 3, '• ' + message); y += 1
        else:
            lines = ['1-7 / Left-Right: view tabs', 'Tab / [ ]: view sub-tabs',
                     'P or Space: pause/resume', 'Q: save and quit', '',
                     'No manual economy, construction, tax, prestige or combat actions exist.']
            for line in lines: self.add(y, 3, line); y += 1
        state = 'PAUSED' if self.paused else 'AI: ' + self.ai.last_action
        self.add(h - 2, 0, f' {state} | autosave 1s | neural save 5s | Q quits '.ljust(max(0, w - 1)), curses.A_REVERSE)
        if self.popup: self.draw_popup()
        self.s.refresh()

    def run(self):
        try: curses.curs_set(0)
        except curses.error: pass
        self.s.nodelay(True); self.s.timeout(int(g.TICK * 1000)); self.s.keypad(True)
        try:
            while self.running:
                self.update(); self.draw(); self.handle(self.s.getch())
        finally:
            g.save_realm(self.r); save_ai(self.ai)


def main():
    try: curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt: pass

if __name__ == '__main__': main()
