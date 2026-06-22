#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import grand_strategy
import grand_strategy_core as grand
import game_core as g

D = g.D
OBJECTIVE_REWARD_COOLDOWN = 30.0


class Game(grand_strategy.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.objective_reward_cooldown = 0.0
        self.objective_clock = time.monotonic()

    def complete_objective(self):
        if self.objective_reward_cooldown > 0 or D(self.grand.objective_progress) < D(100):
            return
        completed = self.grand.objective
        self.grand.objectives_completed += 1
        self.r.gold += D(250) * D(self.grand.objectives_completed)
        self.r.renown += D(5)
        self.grand.major_events.append(f'Objective completed: {completed}.')
        self.grand.major_events = self.grand.major_events[-20:]
        self.r.log(f'Grand objective completed: {completed}.')
        self.objective_reward_cooldown = OBJECTIVE_REWARD_COOLDOWN
        self.grand.objective_progress = '0'
        self.grand.objective = grand.choose_objective(self)
        if self.camera_enabled:
            self.focus_camera('Command', 0, f'Objective completed: {completed}', 9.0)

    def update(self):
        now = time.monotonic()
        elapsed = max(0.0, min(1.0, now - self.objective_clock))
        self.objective_clock = now
        if not self.paused:
            self.objective_reward_cooldown = max(0.0, self.objective_reward_cooldown - elapsed)
        super().update()


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
