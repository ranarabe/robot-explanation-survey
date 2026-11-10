"""Object info: the physical description of each element.

Object attributes (size, colour, mass...) are kept here, NOT as facts.
Rules read them when they need numbers (e.g. comparing volumes).

Dimension convention (bounding box, metres):
    width  -> along x
    depth  -> along y
    height -> along z (vertical, the stacking direction)
"""

import math
from dataclasses import asdict, dataclass


# Volume formula for each shape, from its bounding box (width, depth, height).
# For round shapes, width is the diameter.
VOLUME_FORMULAS = {
    'cube':      lambda w, d, h: w * d * h,   # w*d*h tolerates small detection noise
    'cuboid':    lambda w, d, h: w * d * h,
    'cylinder':  lambda w, d, h: math.pi * (w / 2) ** 2 * h,
    'ball':      lambda w, d, h: (4 / 3) * math.pi * (w / 2) ** 3,
    'ellipsoid': lambda w, d, h: (4 / 3) * math.pi * (w / 2) * (d / 2) * (h / 2),
    'cone':      lambda w, d, h: (1 / 3) * math.pi * (w / 2) ** 2 * h,
    'pyramid':   lambda w, d, h: (1 / 3) * w * d * h,
}


def make_element_id(shape: str, color: str, number: int) -> str:
    """Unique, readable id used in every fact, e.g. 'cube_red_37'."""
    return f'{shape}_{color or "unknown"}_{number}'


@dataclass
class Element:
    element_id: str          # unique name used in facts, e.g. 'cube_red_37'
    shape: str
    color: str
    width: float
    depth: float
    height: float
    mass: float | None = None
    detection_id: int | None = None   # original id from the camera detector

    def __post_init__(self):
        if self.shape not in VOLUME_FORMULAS:
            raise ValueError(f'Unknown shape: {self.shape}')

    @property
    def volume(self) -> float:
        return VOLUME_FORMULAS[self.shape](self.width, self.depth, self.height)

    @property
    def base_area(self) -> float:
        """Area of the bottom face (bounding box)."""
        return self.width * self.depth

    def describe(self) -> str:
        """Human name, e.g. 'red cube (cube_red_37)'."""
        return f'{self.color} {self.shape} ({self.element_id})'

    def to_dict(self) -> dict:
        data = asdict(self)
        data['volume'] = round(self.volume, 9)   # saved for readability only
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Element':
        data = {key: value for key, value in data.items() if key != 'volume'}
        return cls(**data)
