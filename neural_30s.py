#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import autonomous_mode as auto
import dynasty_ascendant as asc
import game_core as g
import kingdom_evolved as evolved
import neural_reign_launch  # Applies hardened save loaders.
import neural_reign as reign

D = g.D
NEURAL_DECISION_INTERVAL = 30.0


class Game(reign.Game):
    """Neural Reign with one consequential neural decision every 30 seconds."""

    def update(self):
        now = time.monotonic()
        dt = max(0.0, min(1.0, now - self.last_tick))

        if not self.paused:
            self.r.tick(dt)
            self.apply_world_production(dt)

            for resource in ('food', 'wood', 'stone', 'iron', 'gold'):
                bonus = (
                    asc.province_bonus(self.asc, resource)
                    + reign.wonder_bonus(self.reign, resource)
                    + reign.doctrine_bonus(self.reign, resource)
                )
                if bonus:
                    value = getattr(self.r, resource)
                    rate = self.r.rates()[resource]
                    setattr(self.r, resource, max(D(0), value + rate * bonus * D(dt)))

            self.advance_world(dt)
            asc.apply_disaster(self.asc, self.r, dt)
            asc.start_disaster(self.asc, self.r, self.world)
            asc.maybe_claim_province(self.asc, self.r, self.world)
            asc.check_achievements(self.asc, self.r, self.world)
            reign.update_wonders(self.reign, self.r, self.world)
            reign.update_trade(self.reign, self.r, self.world, dt)

            self.reign.doctrine_time -= dt
            if self.reign.doctrine_time <= 0:
                reign.choose_doctrine(self.reign, self)

            self.reign.golden_age = max(0.0, self.reign.golden_age - dt)
            if self.r.happiness > 85 and self.asc.stability_value > 80 and not self.asc.disaster:
                self.reign.golden_age = max(self.reign.golden_age, 30.0)
            if self.reign.golden_age > 0:
                self.r.gold += self.r.rates()['gold'] * D('.15') * D(dt)
                self.r.food += max(D(0), self.r.rates()['food']) * D('.15') * D(dt)

            self.reign.famine_warning = self.r.food < self.r.population * D(5)
            self.asc.stability_value += (
                self.r.happiness - self.asc.stability_value
            ) * D('.001') * D(dt)
            self.asc.legitimacy_value += (
                self.r.renown + self.r.prestige * D(20)
            ) * D('.00001') * D(dt)
            self.asc.era = max(1, int(self.r.prestige) + 1)

            if now - self.last_ai_action >= NEURAL_DECISION_INTERVAL:
                self.ai_action()
                self.last_ai_action = now

            if now - self.last_ai_eval >= 30.0:
                self.ai.evaluate(self.r)
                self.last_ai_eval = now

        self.last_tick = now

        if now - self.last_save >= 1:
            g.save_realm(self.r)
            self.last_save = now
        if now - self.last_ai_save >= 5:
            reign.save_brain(self.ai)
            self.last_ai_save = now
        if now - self.last_world_save >= 5:
            evolved.save_world(self.world)
            self.last_world_save = now
        if now - self.last_asc_save >= 5:
            asc.save_state(self.asc)
            self.last_asc_save = now
        if now - self.last_reign_save >= 5:
            reign.save_reign(self.reign)
            self.last_reign_save = now

    def header(self):
        super().header()
        h, w = self.s.getmaxyx()
        if h >= 8 and w >= 50:
            remaining = max(0.0, NEURAL_DECISION_INTERVAL - (time.monotonic() - self.last_ai_action))
            self.add(
                5,
                0,
                f' Next neural decision in {remaining:04.1f}s | cadence: 30.0s '[:w - 1],
                curses.A_DIM,
            )


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
