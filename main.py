#!/usr/bin/env python3
"""Endless Realm II - a text strategy game inspired by classic medieval realm management."""
from __future__ import annotations

import curses
import json
import math
import os
import random
import time
from dataclasses import dataclass, asdict, field
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Dict, List

getcontext().prec = 80
SAVE_DIR = Path.home() / ".endless_realm_ii"
SAVE_FILE = SAVE_DIR / "save.json"
AI_FILE = SAVE_DIR / "neural_ai.json"
TICK = 0.10

SUFFIXES = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"]
ONES = ["", "U", "D", "T", "Qa", "Qi", "Sx", "Sp", "O", "N"]
TENS = ["", "De", "Vg", "Tg", "Qag", "Qig", "Sxg", "Spg", "Og", "Ng"]
HUNDS = ["", "Ce", "Duc", "Trc", "Qac", "Qic", "Sxc", "Spc", "Oc", "Noc"]


def D(value=0) -> Decimal:
    return Decimal(str(value))


def suffix_name(index: int) -> str:
    if index < len(SUFFIXES):
        return SUFFIXES[index]
    n = index - len(SUFFIXES) + 1
    parts = []
    while n:
        chunk = n % 1000
        n //= 1000
        h, rem = divmod(chunk, 100)
        t, o = divmod(rem, 10)
        parts.append(HUNDS[h] + TENS[t] + ONES[o])
    return "".join(reversed(parts)) + "illion"


def fmt(value: Decimal, precision: int = 2) -> str:
    value = D(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value < 1000:
        if value == value.to_integral():
            return f"{sign}{int(value):,}"
        return f"{sign}{value:.{precision}f}"
    exponent = int(value.log10() // 3)
    scaled = value / (D(1000) ** exponent)
    return f"{sign}{scaled:.{precision}f}{suffix_name(exponent)}"


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


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
    peasants: Decimal = D(90)
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
    tax_rate: Decimal = D("0.15")
    auto_ai: bool = False
    last_saved: float = field(default_factory=time.time)
    messages: List[str] = field(default_factory=lambda: ["Your endless reign begins."])

    def total_workers(self):
        return self.farmers + self.woodcutters + self.miners + self.builders + self.soldiers + self.archers + self.knights

    def free_people(self):
        return max(D(0), self.population - self.total_workers())

    def military_power(self):
        base = self.soldiers * 1 + self.archers * 2.5 + self.knights * 7
        fort = 1 + self.walls * D("0.08") + self.castles * D("0.25")
        return base * fort * (D("0.7") + self.happiness / 200)

    def rates(self):
        prestige_mult = D(1) + self.prestige * D("0.10")
        food = (self.farmers * D("0.45") * (1 + self.farms * D("0.12")) - self.population * D("0.08")) * prestige_mult
        wood = self.woodcutters * D("0.35") * (1 + self.lumberyards * D("0.15")) * prestige_mult
        stone = self.miners * D("0.17") * (1 + self.quarries * D("0.13")) * prestige_mult
        iron = self.miners * D("0.08") * (1 + self.mines * D("0.15")) * prestige_mult
        gold = self.population * self.tax_rate * D("0.045") * (1 + self.markets * D("0.10")) * prestige_mult
        return {"food": food, "wood": wood, "stone": stone, "iron": iron, "gold": gold}

    def tick(self, seconds: float):
        dt = D(seconds)
        self.age += dt
        for k, rate in self.rates().items():
            setattr(self, k, max(D(0), getattr(self, k) + rate * dt))
        if self.food > self.population * 2:
            growth = self.population * D("0.00012") * (self.happiness / 100) * dt
            self.population += growth
        if self.food <= 0:
            self.population = max(D(10), self.population * (D(1) - D("0.0003") * dt))
            self.happiness = max(D(0), self.happiness - D("0.08") * dt)
        else:
            target = D(70) - self.tax_rate * 100
            self.happiness += (target - self.happiness) * D("0.002") * dt
        self.threat += (D("0.00018") + self.territory * D("0.000002")) * dt

    def log(self, text: str):
        self.messages.append(text)
        self.messages = self.messages[-80:]


class NeuralGovernor:
    """Tiny evolutionary neural policy: 10 inputs, hidden layer, action outputs."""
    ACTIONS = ["farm", "wood", "mine", "soldier", "archer", "knight", "build_farm", "build_market", "build_wall", "attack"]

    def __init__(self, data=None):
        self.inputs = 10
        self.hidden = 12
        self.outputs = len(self.ACTIONS)
        self.generation = 1
        self.score = 0.0
        self.best_score = -1e99
        self.mutation = 0.14
        self.last_action = "observing"
        if data:
            self.__dict__.update(data)
        else:
            self.w1 = [[random.uniform(-1, 1) for _ in range(self.inputs)] for _ in range(self.hidden)]
            self.w2 = [[random.uniform(-1, 1) for _ in range(self.hidden)] for _ in range(self.outputs)]
            self.best_w1 = [r[:] for r in self.w1]
            self.best_w2 = [r[:] for r in self.w2]

    @staticmethod
    def sigmoid(x):
        return 1 / (1 + math.exp(-clamp(x, -40, 40)))

    def features(self, r: Realm):
        safe = lambda x: math.log10(float(max(D(1), x))) / 20
        return [safe(r.gold), safe(r.food), safe(r.wood), safe(r.stone), safe(r.iron), safe(r.population), float(r.happiness / 100), safe(r.military_power()), safe(r.threat), float(r.free_people() / max(D(1), r.population))]

    def choose(self, r: Realm):
        x = self.features(r)
        h = [math.tanh(sum(w * v for w, v in zip(row, x))) for row in self.w1]
        y = [sum(w * v for w, v in zip(row, h)) + random.uniform(-0.03, 0.03) for row in self.w2]
        action = self.ACTIONS[max(range(len(y)), key=y.__getitem__)]
        self.last_action = action
        return action

    def evaluate(self, r: Realm):
        score = float(math.log10(float(max(D(1), r.population * r.territory * (r.renown + 1))))) + float(r.happiness) / 100
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
    "farm": ("farms", {"gold": 100, "wood": 80, "stone": 20}),
    "lumberyard": ("lumberyards", {"gold": 130, "wood": 100, "stone": 30}),
    "quarry": ("quarries", {"gold": 180, "wood": 70, "stone": 60}),
    "mine": ("mines", {"gold": 300, "wood": 120, "stone": 120}),
    "market": ("markets", {"gold": 500, "wood": 180, "stone": 140}),
    "barracks": ("barracks", {"gold": 700, "wood": 220, "stone": 220}),
    "wall": ("walls", {"gold": 1000, "wood": 300, "stone": 700}),
    "castle": ("castles", {"gold": 5000, "wood": 1200, "stone": 3000, "iron": 500}),
}


def scaled_cost(base: Dict[str, int], count: Decimal):
    scale = D("1.18") ** count
    return {k: D(v) * scale for k, v in base.items()}


def can_pay(r: Realm, costs):
    return all(getattr(r, k) >= v for k, v in costs.items())


def pay(r: Realm, costs):
    for k, v in costs.items():
        setattr(r, k, getattr(r, k) - v)


def build(r: Realm, kind: str):
    attr, base = BUILDINGS[kind]
    costs = scaled_cost(base, getattr(r, attr))
    if can_pay(r, costs):
        pay(r, costs)
        setattr(r, attr, getattr(r, attr) + 1)
        r.log(f"Built {kind}. Cost: " + ", ".join(f"{fmt(v)} {k}" for k, v in costs.items()))
        return True
    r.log(f"Not enough resources for {kind}.")
    return False


def recruit(r: Realm, unit: str, amount=D(1)):
    data = {"farmer": ("farmers", {"gold": 2}), "woodcutter": ("woodcutters", {"gold": 3}), "miner": ("miners", {"gold": 5}),
            "builder": ("builders", {"gold": 8}), "soldier": ("soldiers", {"gold": 18, "iron": 1}),
            "archer": ("archers", {"gold": 35, "wood": 2, "iron": 1}), "knight": ("knights", {"gold": 120, "iron": 8})}
    attr, one = data[unit]
    amount = min(D(amount), r.free_people())
    costs = {k: D(v) * amount for k, v in one.items()}
    if amount >= 1 and can_pay(r, costs):
        pay(r, costs)
        setattr(r, attr, getattr(r, attr) + amount)
        r.log(f"Assigned {fmt(amount)} {unit}(s).")
        return True
    r.log(f"Could not assign {unit}; check free population and resources.")
    return False


def attack(r: Realm):
    enemy = (r.threat ** D("1.12")) * D(18) * (D("0.8") + D(str(random.random())) * D("0.5"))
    power = r.military_power() * (D("0.85") + D(str(random.random())) * D("0.35"))
    if power >= enemy:
        reward = enemy * D(5)
        land = max(D(1), enemy.sqrt() / 5)
        r.gold += reward
        r.food += reward * D("0.35")
        r.territory += land
        r.renown += enemy.sqrt()
        r.victories += 1
        r.threat = max(D(1), r.threat * D("0.72"))
        r.log(f"Victory! Enemy {fmt(enemy)} defeated; gained {fmt(reward)} gold and {fmt(land)} land.")
    else:
        ratio = max(D("0.05"), power / max(D(1), enemy))
        loss = D(1) - ratio * D("0.6")
        r.soldiers *= loss
        r.archers *= loss
        r.knights *= loss
        r.happiness = max(D(5), r.happiness - 8)
        r.defeats += 1
        r.threat *= D("0.93")
        r.log(f"Defeat, but the realm endures. Enemy power was {fmt(enemy)}.")


def prestige(r: Realm):
    requirement = D(1_000_000) * (D(10) ** r.prestige)
    worth = r.gold + r.population * 100 + r.territory * 1000 + r.renown * 500
    if worth < requirement:
        r.log(f"Prestige requires realm worth {fmt(requirement)}.")
        return
    old = r.prestige + 1
    name = r.name
    messages = r.messages[-5:]
    fresh = Realm(name=name, prestige=old)
    fresh.log(f"Prestiged to dynasty level {fmt(old)}. Permanent production +{fmt(old * 10)}%.")
    fresh.messages = messages + fresh.messages
    r.__dict__.update(fresh.__dict__)


def realm_to_json(r: Realm):
    out = {}
    for k, v in asdict(r).items():
        out[k] = str(v) if isinstance(v, Decimal) else v
    return out


def save_realm(r: Realm):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    r.last_saved = time.time()
    tmp = SAVE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(realm_to_json(r), indent=2), encoding="utf-8")
    os.replace(tmp, SAVE_FILE)


def load_realm():
    if not SAVE_FILE.exists():
        return Realm(), 0
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        decimal_fields = {k for k, v in Realm.__dataclass_fields__.items() if v.type is Decimal}
        for k in decimal_fields:
            if k in data:
                data[k] = D(data[k])
        r = Realm(**{k: v for k, v in data.items() if k in Realm.__dataclass_fields__})
        offline = max(0, time.time() - float(data.get("last_saved", time.time())))
        return r, offline
    except Exception:
        return Realm(), 0


def save_ai(ai: NeuralGovernor):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = AI_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(ai.serialize()), encoding="utf-8")
    os.replace(tmp, AI_FILE)


def load_ai():
    try:
        return NeuralGovernor(json.loads(AI_FILE.read_text(encoding="utf-8")))
    except Exception:
        return NeuralGovernor()


class Game:
    TABS = ["Realm", "Economy", "Military", "World", "Neural AI", "Chronicle", "Help"]
    SUBTABS = {
        "Realm": ["Overview", "Dynasty"], "Economy": ["Workforce", "Buildings"],
        "Military": ["Army", "Campaign"], "World": ["Expansion", "Scaling"],
        "Neural AI": ["Governor", "Learning"], "Chronicle": ["Recent", "All"], "Help": ["Keys", "About"]}

    def __init__(self, stdscr):
        self.s = stdscr
        self.r, self.offline = load_realm()
        self.ai = load_ai()
        self.tab = 0
        self.sub = 0
        self.sel = 0
        self.last_tick = time.monotonic()
        self.last_save = time.monotonic()
        self.last_ai_save = time.monotonic()
        self.last_ai_action = time.monotonic()
        self.last_ai_eval = time.monotonic()
        self.popup = self.offline > 2
        self.offline_summary = self.apply_offline(self.offline) if self.popup else ""
        self.running = True

    def apply_offline(self, seconds):
        capped = min(seconds, 60 * 60 * 24 * 30)
        before = {k: getattr(self.r, k) for k in ["gold", "food", "wood", "stone", "iron", "population"]}
        self.r.tick(capped)
        gains = [f"{k.title()}: +{fmt(getattr(self.r, k) - v)}" for k, v in before.items()]
        return f"Away for {int(seconds)} seconds (credited up to 30 days).\n" + "   ".join(gains)

    def ai_action(self):
        a = self.ai.choose(self.r)
        if a in ("farm", "wood", "mine", "soldier", "archer", "knight"):
            unit = {"farm": "farmer", "wood": "woodcutter", "mine": "miner"}.get(a, a)
            recruit(self.r, unit, max(D(1), self.r.free_people() // 20))
        elif a == "build_farm": build(self.r, "farm")
        elif a == "build_market": build(self.r, "market")
        elif a == "build_wall": build(self.r, "wall")
        elif a == "attack" and self.r.military_power() > 5: attack(self.r)

    def update(self):
        now = time.monotonic()
        dt = min(1.0, now - self.last_tick)
        self.last_tick = now
        self.r.tick(dt)
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
        if 0 <= y < h and x < w:
            try: self.s.addnstr(y, x, str(text), max(0, w - x - 1), attr)
            except curses.error: pass

    def header(self):
        h, w = self.s.getmaxyx()
        title = f" ENDLESS REALM II | {self.r.name} "
        self.add(0, 0, title.center(w - 1, "="), curses.A_BOLD)
        x = 1
        for i, t in enumerate(self.TABS):
            label = f" {i+1}:{t} "
            self.add(1, x, label, curses.A_REVERSE if i == self.tab else curses.A_DIM)
            x += len(label) + 1
        subnames = self.SUBTABS[self.TABS[self.tab]]
        x = 2
        for i, name in enumerate(subnames):
            label = f"[{name}]"
            self.add(2, x, label, curses.A_BOLD if i == self.sub else 0)
            x += len(label) + 2
        rates = self.r.rates()
        bar = f" Gold {fmt(self.r.gold)} ({fmt(rates['gold'])}/s) | Food {fmt(self.r.food)} ({fmt(rates['food'])}/s) | Pop {fmt(self.r.population)} | Power {fmt(self.r.military_power())} "
        self.add(3, 0, bar[:w-1].ljust(w-1), curses.A_REVERSE)

    def menu(self, y, items):
        for i, (key, label, detail) in enumerate(items):
            attr = curses.A_REVERSE if i == self.sel else 0
            self.add(y+i, 3, f"{key:>2}  {label:<24} {detail}", attr)

    def draw(self):
        self.s.erase(); self.header()
        tab = self.TABS[self.tab]; sub = self.sub
        y = 5
        if tab == "Realm" and sub == 0:
            lines = [("Age", f"{fmt(self.r.age)} seconds"), ("Population", fmt(self.r.population)), ("Free people", fmt(self.r.free_people())),
                     ("Happiness", f"{self.r.happiness:.1f}%"), ("Territory", fmt(self.r.territory)), ("Renown", fmt(self.r.renown)),
                     ("Threat", fmt(self.r.threat)), ("Victories / Defeats", f"{fmt(self.r.victories)} / {fmt(self.r.defeats)}")]
            for k,v in lines: self.add(y, 3, f"{k:<22} {v}"); y += 1
        elif tab == "Realm":
            req = D(1_000_000) * (D(10) ** self.r.prestige)
            self.add(y,3,f"Dynasty level: {fmt(self.r.prestige)}   Permanent production bonus: {fmt(self.r.prestige*10)}%")
            self.add(y+2,3,f"Next prestige requires realm worth: {fmt(req)}")
            self.add(y+4,3,"Press P to prestige. Your dynasty continues forever; there is no final level.")
        elif tab == "Economy" and sub == 0:
            items=[("F","Assign farmer",fmt(self.r.farmers)),("W","Assign woodcutter",fmt(self.r.woodcutters)),("M","Assign miner",fmt(self.r.miners)),("B","Assign builder",fmt(self.r.builders))]
            self.menu(y,items); self.add(y+6,3,"Use highlighted action with Enter, or press its letter. Shift/uppercase assigns 10 when possible.")
        elif tab == "Economy":
            items=[]
            for key, kind in zip("FLQMKTWC", BUILDINGS):
                attr, base=BUILDINGS[kind]; c=scaled_cost(base,getattr(self.r,attr)); items.append((key,kind.title(),f"Owned {fmt(getattr(self.r,attr))} | "+", ".join(f"{fmt(v)} {k}" for k,v in c.items())))
            self.menu(y,items)
        elif tab == "Military" and sub == 0:
            items=[("S","Recruit soldier",fmt(self.r.soldiers)),("A","Recruit archer",fmt(self.r.archers)),("K","Recruit knight",fmt(self.r.knights)),("B","Build barracks",fmt(self.r.barracks)),("W","Build wall",fmt(self.r.walls)),("C","Build castle",fmt(self.r.castles))]
            self.menu(y,items)
        elif tab == "Military":
            enemy=(self.r.threat**D("1.12"))*18
            self.add(y,3,f"Estimated enemy power: {fmt(enemy)}")
            self.add(y+1,3,f"Your fortified power:  {fmt(self.r.military_power())}")
            self.add(y+3,3,"Press A to launch a campaign. Defeat never ends the game; your realm survives and rebuilds.")
        elif tab == "World" and sub == 0:
            self.add(y,3,f"Known territory: {fmt(self.r.territory)}")
            self.add(y+1,3,f"World threat:    {fmt(self.r.threat)}")
            self.add(y+3,3,"World difficulty and rewards scale forever with territory and threat.")
        elif tab == "World":
            for i in range(12): self.add(y+i,3,f"10^{i*3:>3}: {suffix_name(i) or 'units'}")
            self.add(y+13,3,"Suffix generation continues algorithmically beyond this list.")
        elif tab == "Neural AI" and sub == 0:
            status="ENABLED" if self.r.auto_ai else "DISABLED"
            self.add(y,3,f"Autonomous governor: {status}  (press T to toggle)")
            self.add(y+2,3,f"Last decision: {self.ai.last_action}")
            self.add(y+3,3,"The governor observes resources, population, morale, power, threat, and free workers.")
        elif tab == "Neural AI":
            self.add(y,3,f"Generation: {self.ai.generation}")
            self.add(y+1,3,f"Current score: {self.ai.score:.5f}")
            self.add(y+2,3,f"Best score: {self.ai.best_score:.5f}")
            self.add(y+3,3,f"Mutation rate: {self.ai.mutation:.5f}")
            self.add(y+5,3,"A compact neural policy mutates from its best weights and is saved silently every 5 seconds.")
        elif tab == "Chronicle":
            msgs=self.r.messages[-12:] if sub==0 else self.r.messages
            start=max(0,len(msgs)-max(1,self.s.getmaxyx()[0]-7))
            for msg in msgs[start:]: self.add(y,3,"• "+msg); y+=1
        elif tab == "Help" and sub == 0:
            keys=["1-7 / Left-Right: switch tabs", "Tab / [ ]: switch sub-tabs", "Up/Down: select action", "Enter: perform selected action", "Letters shown: direct action", "T: toggle neural governor", "P: prestige", "Q: save and quit"]
            for line in keys: self.add(y,3,line); y+=1
        else:
            self.add(y,3,"An original, endless text strategy game inspired by medieval realm-management classics.")
            self.add(y+2,3,"Designed for persistent progression, automated play, and absurdly large numbers.")
        h,w=self.s.getmaxyx(); self.add(h-2,0," Autosaves: realm every 1s | neural AI every 5s | Q quits ".ljust(w-1),curses.A_REVERSE)
        if self.popup: self.draw_popup()
        self.s.refresh()

    def draw_popup(self):
        h,w=self.s.getmaxyx(); ph=8; pw=min(w-4,90); y=max(1,(h-ph)//2); x=max(1,(w-pw)//2)
        try:
            win=curses.newwin(ph,pw,y,x); win.box(); win.addnstr(1,2," OFFLINE PROGRESS ",pw-4,curses.A_BOLD)
            lines=[]
            for raw in self.offline_summary.split("\n"):
                while len(raw)>pw-5: lines.append(raw[:pw-5]); raw=raw[pw-5:]
                lines.append(raw)
            for i,line in enumerate(lines[:4]): win.addnstr(3+i,2,line,pw-4)
            win.addnstr(ph-2,2,"Press Enter, Escape, D, or Space to dismiss",pw-4,curses.A_REVERSE); win.refresh()
        except curses.error: pass

    def selected_action(self):
        tab=self.TABS[self.tab]
        if tab=="Economy" and self.sub==0:
            recruit(self.r,["farmer","woodcutter","miner","builder"][self.sel%4])
        elif tab=="Economy" and self.sub==1:
            build(self.r,list(BUILDINGS)[self.sel%len(BUILDINGS)])
        elif tab=="Military" and self.sub==0:
            actions=[lambda:recruit(self.r,"soldier"),lambda:recruit(self.r,"archer"),lambda:recruit(self.r,"knight"),lambda:build(self.r,"barracks"),lambda:build(self.r,"wall"),lambda:build(self.r,"castle")]
            actions[self.sel%len(actions)]()
        elif tab=="Military" and self.sub==1: attack(self.r)

    def handle(self,key):
        if self.popup:
            if key in (10,13,27,32,ord('d'),ord('D')): self.popup=False
            return
        if key in (ord('q'),ord('Q')): self.running=False; return
        if ord('1')<=key<=ord('7'): self.tab=key-ord('1'); self.sub=0; self.sel=0; return
        if key in (curses.KEY_RIGHT,): self.tab=(self.tab+1)%len(self.TABS); self.sub=0; self.sel=0; return
        if key in (curses.KEY_LEFT,): self.tab=(self.tab-1)%len(self.TABS); self.sub=0; self.sel=0; return
        if key in (9,ord(']')): self.sub=(self.sub+1)%len(self.SUBTABS[self.TABS[self.tab]]); self.sel=0; return
        if key==ord('['): self.sub=(self.sub-1)%len(self.SUBTABS[self.TABS[self.tab]]); self.sel=0; return
        if key==curses.KEY_UP: self.sel=max(0,self.sel-1); return
        if key==curses.KEY_DOWN: self.sel+=1; return
        if key in (10,13): self.selected_action(); return
        if key in (ord('t'),ord('T')): self.r.auto_ai=not self.r.auto_ai; self.r.log(f"Neural governor {'enabled' if self.r.auto_ai else 'disabled'}."); return
        if key in (ord('p'),ord('P')): prestige(self.r); return
        tab=self.TABS[self.tab]; ch=chr(key).lower() if 0<=key<256 else ''
        if tab=="Economy" and self.sub==0:
            m={'f':'farmer','w':'woodcutter','m':'miner','b':'builder'}
            if ch in m: recruit(self.r,m[ch],10 if chr(key).isupper() else 1)
        elif tab=="Economy" and self.sub==1:
            m=dict(zip("flqmktwc",BUILDINGS))
            if ch in m: build(self.r,m[ch])
        elif tab=="Military" and self.sub==0:
            if ch in 'sak': recruit(self.r,{'s':'soldier','a':'archer','k':'knight'}[ch])
            elif ch in {'b','w','c'}: build(self.r,{'b':'barracks','w':'wall','c':'castle'}[ch])
        elif tab=="Military" and self.sub==1 and ch=='a': attack(self.r)

    def run(self):
        curses.curs_set(0); self.s.nodelay(True); self.s.timeout(int(TICK*1000)); self.s.keypad(True)
        while self.running:
            self.update(); self.draw(); self.handle(self.s.getch())
        save_realm(self.r); save_ai(self.ai)


def main():
    try: curses.wrapper(lambda s: Game(s).run())
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
