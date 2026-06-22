#!/usr/bin/env python3
from __future__ import annotations

import curses

import combat_launch
import game_core as g


class BufferedWindow:
    """Delegate window operations but defer refreshes until curses.doupdate()."""

    def __init__(self, window):
        object.__setattr__(self, '_window', window)

    def __getattr__(self, name):
        return getattr(self._window, name)

    def __setattr__(self, name, value):
        setattr(self._window, name, value)

    def refresh(self, *args, **kwargs):
        return self._window.noutrefresh(*args, **kwargs)


class Game(combat_launch.Game):
    def __init__(self, screen):
        buffered = BufferedWindow(screen)
        super().__init__(buffered)
        try:
            screen.leaveok(True)
            screen.idlok(True)
            screen.scrollok(False)
        except curses.error:
            pass

    def run(self):
        try:
            curses.curs_set(0)
        except curses.error:
            pass

        self.s.nodelay(True)
        self.s.timeout(int(g.TICK * 1000))
        self.s.keypad(True)

        try:
            while self.running:
                self.update()
                self.draw()
                curses.doupdate()
                self.handle(self.s.getch())
        finally:
            self.save_all()

    def save_all(self):
        """Use the inherited cleanup path without starting another draw loop."""
        try:
            import autonomous_mode as auto
            import dynasty_ascendant as asc
            import kingdom_evolved as evolved
            import neural_reign as reign
            import sovereign_mind as mind

            g.save_realm(self.r)
            reign.save_brain(self.ai)
            evolved.save_world(self.world)
            asc.save_state(self.asc)
            reign.save_reign(self.reign)
            mind.save_state(self.sovereign)
        except (AttributeError, OSError, TypeError, ValueError):
            pass


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
