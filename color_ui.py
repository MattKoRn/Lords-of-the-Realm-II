#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import auto_camera
import game_core as g
import kingdom_evolved as evolved


class Game(auto_camera.Game):
    """Flicker-free colored UI with non-overlapping header and content rows."""

    PAIR_TITLE = 1
    PAIR_TAB = 2
    PAIR_ACTIVE = 3
    PAIR_RESOURCE = 4
    PAIR_GOOD = 5
    PAIR_WARNING = 6
    PAIR_NEURAL = 7
    PAIR_CAMERA = 8
    PAIR_MUTED = 9

    def __init__(self, screen):
        super().__init__(screen)
        self.colors_enabled = False
        self.setup_colors()

    def setup_colors(self):
        if not curses.has_colors():
            return
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(self.PAIR_TITLE, curses.COLOR_YELLOW, -1)
            curses.init_pair(self.PAIR_TAB, curses.COLOR_CYAN, -1)
            curses.init_pair(self.PAIR_ACTIVE, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(self.PAIR_RESOURCE, curses.COLOR_GREEN, -1)
            curses.init_pair(self.PAIR_GOOD, curses.COLOR_GREEN, -1)
            curses.init_pair(self.PAIR_WARNING, curses.COLOR_RED, -1)
            curses.init_pair(self.PAIR_NEURAL, curses.COLOR_MAGENTA, -1)
            curses.init_pair(self.PAIR_CAMERA, curses.COLOR_BLACK, curses.COLOR_YELLOW)
            curses.init_pair(self.PAIR_MUTED, curses.COLOR_BLUE, -1)
            self.colors_enabled = True
        except curses.error:
            self.colors_enabled = False

    def pair(self, number):
        return curses.color_pair(number) if self.colors_enabled else 0

    def add(self, y, x, text, attr=0):
        """Apply semantic colors while preserving bold/reverse attributes."""
        value = str(text)
        color = 0
        lowered = value.lower()
        if 'alert:' in lowered or 'famine risk' in lowered or 'disaster:' in lowered:
            color = self.pair(self.PAIR_WARNING)
        elif 'neural' in lowered or 'forecast' in lowered or 'confidence' in lowered:
            color = self.pair(self.PAIR_NEURAL)
        elif any(word in lowered for word in ('gold ', 'food ', 'population', 'power ')):
            color = self.pair(self.PAIR_RESOURCE)
        elif any(word in lowered for word in ('completed', 'unlocked', 'golden age', 'allied')):
            color = self.pair(self.PAIR_GOOD)
        super().add(y, x, value, attr | color)

    def header(self):
        """Reserve rows 0-5 only; tab content begins safely at row 6."""
        h, w = self.s.getmaxyx()
        if h < 8 or w < 50:
            self.add(0, 0, 'Terminal too small. Resize or press Q.', curses.A_BOLD | self.pair(self.PAIR_WARNING))
            return

        title = f' SOVEREIGN MIND | Era {self.asc.era} | {self.reign.doctrine} | {self.r.name} '
        self.add(0, 0, title.center(w - 1, '='), curses.A_BOLD | self.pair(self.PAIR_TITLE))

        labels = [
            '1:Command', '2:Realm', '3:Economy', '4:Military', '5:World',
            '6:Research', '7:Diplomacy', '8:Neural', '9:Legacy',
            '0:Chronicle', '-:Help',
        ]
        x = 0
        for index, label in enumerate(labels):
            text = f' {label} '
            if x + len(text) < w:
                style = self.pair(self.PAIR_ACTIVE) | curses.A_BOLD if index == self.tab else self.pair(self.PAIR_TAB)
                super().add(1, x, text, style)
            x += len(text)

        alerts = []
        if self.asc.disaster:
            alerts.append(f'{self.asc.disaster} {int(self.asc.disaster_time)}s')
        if self.reign.famine_warning:
            alerts.append('FAMINE RISK')
        if self.reign.golden_age > 0:
            alerts.append(f'GOLDEN AGE {int(self.reign.golden_age)}s')
        banner = ' | '.join(alerts) or 'Realm stable'
        banner_style = self.pair(self.PAIR_WARNING) | curses.A_BOLD if alerts else self.pair(self.PAIR_GOOD) | curses.A_BOLD
        super().add(2, 0, f' {evolved.SEASONS[self.world.season]} / {self.world.weather} | {banner} '[:w - 1].ljust(w - 1), banner_style)

        super().add(3, 0, f' Objective: {self.world.objective} '[:w - 1].ljust(w - 1), self.pair(self.PAIR_TITLE))
        resources = (
            f' Gold {g.fmt(self.r.gold)} | Food {g.fmt(self.r.food)} | '
            f'Pop {g.fmt(self.r.population)} | Power {g.fmt(self.r.military_power())} | '
            f'Confidence {self.ai.confidence:.0%} '
        )
        super().add(4, 0, resources[:w - 1].ljust(w - 1), self.pair(self.PAIR_RESOURCE) | curses.A_BOLD)

        remaining = max(0.0, 30.0 - (time.monotonic() - self.last_ai_action))
        camera = 'ON' if self.camera_enabled else 'OFF'
        status = f' Next neural decision {remaining:04.1f}s | Auto camera {camera} [C] | {self.camera_caption} '
        super().add(5, 0, status[:w - 1].ljust(w - 1), self.pair(self.PAIR_CAMERA) if self.camera_enabled else self.pair(self.PAIR_MUTED))

    def draw(self):
        """Use the inherited reports, then repaint reserved status bands cleanly."""
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 14 or w < 60:
            return

        # Clear full rows before repainting so old longer text cannot bleed through.
        blank = ' ' * max(0, w - 1)
        super().add(h - 5, 0, blank)
        super().add(h - 4, 0, blank)
        super().add(h - 3, 0, blank)

        camera = 'ON' if self.camera_enabled else 'OFF'
        super().add(
            h - 5, 0,
            f' AUTO CAMERA {camera} [C] | {self.camera_caption} '[:w - 1].ljust(w - 1),
            self.pair(self.PAIR_CAMERA) if self.camera_enabled else self.pair(self.PAIR_MUTED),
        )

        forecast_wait = max(0.0, 30.0 - self.forecast_age) if self.forecast_pending else 0.0
        super().add(
            h - 4, 0,
            (
                f' Directive {self.sovereign.directive} | Forecast {self.sovereign.forecast_action} '
                f'{self.sovereign.forecast_gain:+.2f} | Risk {self.sovereign.forecast_risk:.0%} | '
                f'Review {forecast_wait:.0f}s '
            )[:w - 1].ljust(w - 1),
            self.pair(self.PAIR_NEURAL) | curses.A_BOLD,
        )

        estates = self.sovereign
        estate_text = (
            f' Estates: Peasants {g.D(estates.peasants_influence):.0f}% | '
            f'Burghers {g.D(estates.burghers_influence):.0f}% | '
            f'Nobles {g.D(estates.nobles_influence):.0f}% | '
            f'Clergy {g.D(estates.clergy_influence):.0f}% '
        )
        super().add(h - 3, 0, estate_text[:w - 1].ljust(w - 1), self.pair(self.PAIR_TAB))
        self.s.refresh()


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
