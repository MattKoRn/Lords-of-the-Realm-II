#!/usr/bin/env python3
from __future__ import annotations

import curses
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import color_ui


DECIMAL_PATTERN = re.compile(r'(?<![A-Za-z0-9_])([+-]?\d[\d,]*)\.(\d+)([%A-Za-z]*)')


def whole_number_text(value):
    """Round every visible decimal number while preserving suffixes and signs."""
    text = str(value)

    def replace(match):
        integer_part = match.group(1).replace(',', '')
        fraction = match.group(2)
        suffix = match.group(3)
        try:
            number = Decimal(f'{integer_part}.{fraction}')
            rounded = number.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            formatted = f'{int(rounded):,}'
            if match.group(1).startswith('+') and not formatted.startswith('-'):
                formatted = '+' + formatted
            return formatted + suffix
        except (InvalidOperation, ValueError, OverflowError):
            return match.group(0)

    return DECIMAL_PATTERN.sub(replace, text)


class Game(color_ui.Game):
    """Colored UI that renders all visible numeric values as whole numbers."""

    def add(self, y, x, text, attr=0):
        super().add(y, x, whole_number_text(text), attr)


def main():
    try:
        curses.wrapper(lambda screen: Game(screen).run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
