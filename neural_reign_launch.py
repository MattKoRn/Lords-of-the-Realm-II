#!/usr/bin/env python3
from __future__ import annotations

import curses
import math

import game_core as g
import neural_reign as reign


def safe_load_reign():
    state = reign._base_load_reign()
    cleaned = []
    for raw in state.trade_routes:
        if not isinstance(raw, dict):
            continue
        try:
            good = str(raw.get('good', 'Grain'))
            if good not in reign.TRADE_GOODS:
                continue
            yield_value = max(g.D(1), g.D(raw.get('yield', 10)))
            age = max(0.0, min(900.0, float(raw.get('age', 0))))
        except (ValueError, TypeError, ArithmeticError):
            continue
        cleaned.append({'good': good, 'yield': str(yield_value), 'age': age})
    state.trade_routes = cleaned[-12:]
    state.famine_warning = bool(state.famine_warning)
    return state


def safe_load_brain():
    ai = reign._base_load_brain()
    for action in ai.ACTIONS:
        value = ai.outcome_memory.get(action, 0.0)
        ai.outcome_memory[action] = value if isinstance(value, (int, float)) and math.isfinite(value) else 0.0
        ai.usage_memory[action] = max(0, min(10_000_000, int(ai.usage_memory.get(action, 0))))
        ai.cooldowns[action] = max(0, min(100, int(ai.cooldowns.get(action, 0))))
    ai.exploration = max(.005, min(.35, ai.exploration))
    ai.confidence = max(0.0, min(1.0, ai.confidence))
    return ai


reign._base_load_reign = reign.load_reign
reign._base_load_brain = reign.load_brain
reign.load_reign = safe_load_reign
reign.load_brain = safe_load_brain


def main():
    try:
        curses.wrapper(lambda screen: reign.Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
