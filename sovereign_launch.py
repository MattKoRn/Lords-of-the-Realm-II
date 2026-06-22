#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import autonomous_mode as auto
import dynasty_ascendant as asc
import game_core as g
import sovereign_mind as mind


class Game(mind.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.forecast_pending = False
        self.forecast_age = 0.0
        self.forecast_baseline = g.D(0)
        self.meta_tick = time.monotonic()
        self.sovereign.last_predecision_worth = '0'

    def ai_action(self):
        try:
            self.sovereign.directive = mind.select_directive(self)
            self.sovereign.directive_age = 0.0
            allowed = asc.valid_actions(self)
            action, ranking = mind.deliberate(self, allowed)

            self.ai.last_action = action
            self.ai.decisions += 1
            self.ai.action_counts[action] += 1
            self.ai.usage_memory[action] += 1
            self.ai.cooldowns[action] = 2 if action not in ('wait', 'tax_up', 'tax_down') else 1
            self.ai.confidence = (
                1.0 if len(ranking) < 2
                else max(0.0, min(1.0, 0.5 + (ranking[0][0] - ranking[1][0]) / 6))
            )
            self.ai.reason = (
                f'{self.sovereign.directive} directive; '
                f'forecast {self.sovereign.forecast_gain:+.2f}; '
                f'risk {self.sovereign.forecast_risk:.0%}.'
            )

            self.forecast_baseline = g.realm_worth(self.r)
            self.forecast_age = 0.0
            self.forecast_pending = True
            self.sovereign.last_predecision_worth = '0'
            auto.execute(self.ai, self.r, action)
        except (ArithmeticError, ValueError, TypeError, KeyError) as exc:
            self.ai.last_result = f'Sovereign deliberation rejected: {exc}'[:160]

    def update(self):
        now = time.monotonic()
        dt = max(0.0, min(1.0, now - self.meta_tick))
        self.meta_tick = now
        super().update()

        self.sovereign.last_predecision_worth = '0'
        if not self.paused and self.forecast_pending:
            self.forecast_age += dt
            if self.forecast_age >= mind.LOOKAHEAD_SECONDS:
                current = g.realm_worth(self.r)
                if current >= self.forecast_baseline:
                    self.sovereign.successful_forecasts += 1
                else:
                    self.sovereign.failed_forecasts += 1
                self.forecast_pending = False
                self.forecast_age = 0.0

    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 13 or w < 60:
            return

        forecast_wait = max(0.0, mind.LOOKAHEAD_SECONDS - self.forecast_age) if self.forecast_pending else 0.0
        strategy = (
            f' Directive {self.sovereign.directive} | '
            f'Forecast {self.sovereign.forecast_action} {self.sovereign.forecast_gain:+.2f} | '
            f'Risk {self.sovereign.forecast_risk:.0%} | Review {forecast_wait:.0f}s '
        )
        self.add(h - 4, 0, strategy[:w - 1].ljust(w - 1), curses.A_BOLD)

        estates = mind.estate_values(self.sovereign)
        estate_line = ' | '.join(f'{name} {value:.0f}%' for name, value in estates.items())
        self.add(h - 3, 0, f' Estates: {estate_line} '[:w - 1].ljust(w - 1), curses.A_DIM)
        self.s.refresh()


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
