#!/usr/bin/env python3
from __future__ import annotations

import curses
import autonomous_mode as auto


class Game(auto.Game):
    def draw_popup(self):
        """Render popup in the main buffer to prevent alternating window refreshes."""
        h, w = self.s.getmaxyx()
        if h < 6 or w < 24:
            self.add(max(0, h - 1), 0, 'Offline gains applied. Press D.', curses.A_REVERSE)
            return

        ph = min(8, h - 1)
        pw = min(90, w - 2)
        top = max(0, (h - ph) // 2)
        left = max(0, (w - pw) // 2)
        inner = max(1, pw - 4)

        border = '+' + '-' * max(0, pw - 2) + '+'
        self.add(top, left, border, curses.A_BOLD)
        for row in range(1, ph - 1):
            self.add(top + row, left, '|' + ' ' * max(0, pw - 2) + '|')
        self.add(top + ph - 1, left, border, curses.A_BOLD)
        self.add(top + 1, left + 2, ' OFFLINE PROGRESS ', curses.A_BOLD)

        lines = []
        for raw in self.offline_summary.split('\n'):
            if not raw:
                lines.append('')
            else:
                lines.extend(raw[i:i + inner] for i in range(0, len(raw), inner))

        for index, line in enumerate(lines[:max(0, ph - 4)]):
            self.add(top + 2 + index, left + 2, line)

        self.add(
            top + ph - 2,
            left + 2,
            'Enter/Esc/D/Space dismisses',
            curses.A_REVERSE,
        )


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
