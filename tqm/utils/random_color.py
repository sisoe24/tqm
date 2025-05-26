
from __future__ import annotations

from random import randint
from collections import OrderedDict
from dataclasses import field, dataclass

from PySide2.QtGui import QColor


@dataclass
class RandomColor:
    """

    The class generates a unique random color each time the `generate` method is
    called. The class stores limited number of colors in the `colors` dictionary.

    Attributes:
        min_value (int): The minimum value for each color channel (red, green, blue).
        max_value (int): The maximum value for each color channel (red, green, blue).
        alpha (int): The alpha value for the color.
        max_colors (int): The maximum number of colors to generate. (Defaults 500)

    Methods:
        generate(): Generates a random color and adds it to the colors dictionary.

    Examples:
        >>> color = RandomColor().generate()
        >>> color
        <PySide2.QtGui.QColor object at 0x000001F7E9E2D9D0>
        >>> color.name()
        '#f7d2a0'

    """

    min_value: int = 20
    max_value: int = 255
    alpha: int = 255
    max_colors: int = 500

    colors: OrderedDict[str, QColor] = field(default_factory=OrderedDict[str, QColor], init=False)
    exclude_colors: list[str] = field(default_factory=list[str])

    def generate(self) -> QColor:

        while True:
            r, g, b = (randint(self.min_value, self.max_value) for _ in range(3))

            color = QColor(r, g, b, self.alpha)

            if color.name() in self.exclude_colors:
                continue

            if color.name() not in self.colors:

                if len(self.colors) >= self.max_colors:
                    self.colors.popitem(last=False)

                self.colors[color.name()] = color
                return color
