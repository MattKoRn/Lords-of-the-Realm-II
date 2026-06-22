#!/usr/bin/env python3
from __future__ import annotations

import curses
import time

import decimal_fix  # Applies Decimal-safe estate updates.
import sovereign_launch


ACTION_VIEWS = {
    'wait': ('Command', 0, 'Observing neural deliberation'),
    'farmer': ('Economy', 0, 'Following workforce allocation'),
    'woodcutter': ('Economy', 0, 'Following workforce allocation'),
    'miner': ('Economy', 0, 'Following workforce allocation'),
    'builder': ('Economy', 1, 'Following construction labour'),
    'soldier': ('Military', 0, 'Following army recruitment'),
    'archer': ('Military', 0, 'Following army recruitment'),
    'knight': ('Military', 0, 'Following army recruitment'),
    'farm': ('Economy', 1, 'Following farm construction'),
    'lumberyard': ('Economy', 1, 'Following lumberyard construction'),
    'quarry': ('Economy', 1, 'Following quarry construction'),
    'mine': ('Economy', 1, 'Following mine construction'),
    'market': ('Economy', 1, 'Following market construction'),
    'barracks': ('Military', 1, 'Following barracks construction'),
    'wall': ('Military', 1, 'Following defensive construction'),
    'castle': ('Military', 1, 'Following castle construction'),
    'tax_down': ('Realm', 1, 'Following tax policy'),
    'tax_up': ('Realm', 1, 'Following tax policy'),
    'attack': ('Military', 1, 'Following the campaign'),
    'prestige': ('Legacy', 0, 'Following dynasty prestige'),
}


class Game(sovereign_launch.Game):
    def __init__(self, screen):
        super().__init__(screen)
        self.camera_enabled = True
        self.camera_started = time.monotonic()
        self.camera_phase = -1
        self.camera_caption = 'Auto camera awaiting the next neural decision.'
        self.camera_plan = []

    def tab_index(self, name):
        try:
            return self.TABS.index(name)
        except ValueError:
            return 0

    def build_camera_plan(self, action):
        tab_name, subtab, caption = ACTION_VIEWS.get(
            action,
            ('Command', 0, 'Following neural activity'),
        )
        return [
            (0.0, 'Command', 0, 'Neural decision and forecast'),
            (3.0, tab_name, 0, caption),
            (11.0, tab_name, subtab, caption + ' — details'),
            (20.0, 'Neural', 0, 'Reviewing neural confidence and memory'),
            (27.0, 'Command', 0, 'Preparing the next deliberation'),
        ]

    def apply_camera(self, force=False):
        if not self.camera_enabled or not self.camera_plan:
            return
        elapsed = time.monotonic() - self.camera_started
        phase = 0
        for index, item in enumerate(self.camera_plan):
            if elapsed >= item[0]:
                phase = index
            else:
                break
        if force or phase != self.camera_phase:
            _, tab_name, subtab, caption = self.camera_plan[phase]
            self.tab = self.tab_index(tab_name)
            self.sub = subtab
            self.camera_caption = caption
            self.camera_phase = phase

    def ai_action(self):
        super().ai_action()
        self.camera_plan = self.build_camera_plan(self.ai.last_action)
        self.camera_started = time.monotonic()
        self.camera_phase = -1
        self.apply_camera(force=True)

    def update(self):
        super().update()
        self.apply_camera()

    def handle(self, key):
        if key in (ord('c'), ord('C')) and not self.popup:
            self.camera_enabled = not self.camera_enabled
            if self.camera_enabled:
                self.camera_caption = 'Auto camera enabled.'
                self.apply_camera(force=True)
            else:
                self.camera_caption = 'Auto camera disabled; manual viewing active.'
            return
        super().handle(key)

    def draw(self):
        super().draw()
        h, w = self.s.getmaxyx()
        if h < 14 or w < 60:
            return
        mode = 'ON' if self.camera_enabled else 'OFF'
        text = f' AUTO CAMERA {mode} [C] | {self.camera_caption} '
        self.add(h - 5, 0, text[:w - 1].ljust(w - 1), curses.A_REVERSE if self.camera_enabled else curses.A_DIM)
        self.s.refresh()


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
