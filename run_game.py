#!/usr/bin/env python3
"""Hardened launcher for Endless Realm II.

Keeps save compatibility and truly-large Decimal arithmetic isolated from the UI module.
"""
from __future__ import annotations

import json
import math
import time

import main as game


def load_realm_safe():
    if not game.SAVE_FILE.exists():
        return game.Realm(), 0
    try:
        data = json.loads(game.SAVE_FILE.read_text(encoding="utf-8"))
        template = game.Realm()
        converted = {}
        for key in game.Realm.__dataclass_fields__:
            if key not in data:
                continue
            value = data[key]
            if isinstance(getattr(template, key), game.Decimal):
                value = game.D(value)
            converted[key] = value
        realm = game.Realm(**converted)
        offline = max(0.0, time.time() - float(data.get("last_saved", time.time())))
        return realm, offline
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return game.Realm(), 0


def military_power_safe(self):
    base = self.soldiers + self.archers * game.D("2.5") + self.knights * game.D(7)
    fort = game.D(1) + self.walls * game.D("0.08") + self.castles * game.D("0.25")
    return base * fort * (game.D("0.7") + self.happiness / game.D(200))


def features_safe(self, realm):
    def scaled_log(value):
        value = max(game.D(1), game.D(value))
        return float(value.log10() / game.D(20))

    return [
        scaled_log(realm.gold), scaled_log(realm.food), scaled_log(realm.wood),
        scaled_log(realm.stone), scaled_log(realm.iron), scaled_log(realm.population),
        float(realm.happiness / game.D(100)), scaled_log(realm.military_power()),
        scaled_log(realm.threat),
        float(realm.free_people() / max(game.D(1), realm.population)),
    ]


def evaluate_safe(self, realm):
    value = max(game.D(1), realm.population * realm.territory * (realm.renown + 1))
    score = float(value.log10()) + float(realm.happiness / game.D(100))
    self.score = score
    if score > self.best_score:
        self.best_score = score
        self.best_w1 = [row[:] for row in self.w1]
        self.best_w2 = [row[:] for row in self.w2]
    else:
        self.w1 = [[v + game.random.gauss(0, self.mutation) for v in row] for row in self.best_w1]
        self.w2 = [[v + game.random.gauss(0, self.mutation) for v in row] for row in self.best_w2]
        self.generation += 1
        self.mutation = max(0.015, self.mutation * 0.999)


game.load_realm = load_realm_safe
game.Realm.military_power = military_power_safe
game.NeuralGovernor.features = features_safe
game.NeuralGovernor.evaluate = evaluate_safe

if __name__ == "__main__":
    game.main()
