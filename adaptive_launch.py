#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import adaptive_core as core
import adaptive_empire
import imperial_mind as imperial


def correct_counter(realm):
    composition = imperial.enemy_composition(realm)
    dominant = max(composition, key=composition.get)
    return {
        'soldiers': 'archer',
        'archers': 'knight',
        'knights': 'soldier',
    }[dominant]


imperial.recommended_counter = correct_counter


class Game(adaptive_empire.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.adaptive_clock = time.monotonic()

    def update(self):
        now = time.monotonic()
        elapsed = max(0.0, min(1.0, now - self.adaptive_clock))
        self.adaptive_clock = now
        super().update()
        if not self.paused and elapsed > 0:
            core.logistics_tick(self.adaptive, self.r, elapsed)
            self.adaptive.formation = core.choose_formation(self.adaptive, self.r)
            self.imperial.battle_readiness = str(core.adjusted_readiness(self.adaptive, self.r))


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
