#!/usr/bin/env python3
from __future__ import annotations

import curses
import kingdom_evolved as evolved
import game_core as core


def exact_tech_bonus(state, category):
    bonus = core.D(0)
    for name, _, kind, amount in evolved.TECHS:
        if name in state.unlocked and kind == category:
            bonus += amount
    return bonus


def safe_load_world():
    state = evolved._original_load_world()
    cleaned = []
    for index, raw in enumerate(state.rivals[:8] if isinstance(state.rivals, list) else []):
        if not isinstance(raw, dict):
            continue
        try:
            power = max(core.D(1), core.D(raw.get('power', 20)))
            wealth = max(core.D(0), core.D(raw.get('wealth', 500)))
            attitude = max(-100, min(100, int(raw.get('attitude', 0))))
            victories = max(0, int(raw.get('victories', 0)))
        except (ValueError, TypeError, ArithmeticError):
            continue
        cleaned.append({
            'name': str(raw.get('name', f'Rival Realm {index + 1}'))[:40],
            'power': str(power),
            'wealth': str(wealth),
            'attitude': attitude,
            'victories': victories,
        })
    if not cleaned:
        cleaned = evolved.WorldState().rivals
    state.rivals = cleaned
    state.season = max(0, min(len(evolved.SEASONS) - 1, int(state.season)))
    state.season_time = max(0.0, min(119.999, float(state.season_time)))
    state.weather = str(state.weather)[:40]
    state.events = [str(item)[:300] for item in state.events[-60:]]
    state.unlocked = [name for name, *_ in evolved.TECHS if name in state.unlocked]
    return state


evolved._original_load_world = evolved.load_world
evolved.load_world = safe_load_world
evolved.tech_bonus = exact_tech_bonus


def main():
    try:
        curses.wrapper(lambda screen: evolved.Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
