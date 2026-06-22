#!/usr/bin/env python3
from __future__ import annotations

import copy
import curses

import combat_stats
import game_core as g


_ACTIVE_REALM_ID = None
_BASE_BATTLE = combat_stats.battle


def guarded_battle(realm):
    """Keep neural look-ahead battles from replacing the real battle report."""
    simulated = _ACTIVE_REALM_ID is not None and id(realm) != _ACTIVE_REALM_ID
    previous = copy.deepcopy(combat_stats.LAST_BATTLE) if simulated else None
    _BASE_BATTLE(realm)
    if simulated:
        combat_stats.LAST_BATTLE.clear()
        combat_stats.LAST_BATTLE.update(previous)


g.attack = guarded_battle


class Game(combat_stats.Game):
    def __init__(self, screen):
        global _ACTIVE_REALM_ID
        super().__init__(screen)
        _ACTIVE_REALM_ID = id(self.r)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
