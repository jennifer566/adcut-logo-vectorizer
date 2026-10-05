"""Export explicit CAD geometry without approximating circles with short lines."""

import math
from dataclasses import dataclass
from io import StringIO

import ezdxf


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    radius: float


def export_circles(circles: list[Circle], *, units: int, version: str = "R2000") -> str:
    """Export caller-supplied geometry. Coordinates must already use the requested units.

    R2000 is a development default, not a confirmed Adcut requirement.
    This function does not infer scale or trace input images.
    """
    if units not in (1, 4):
        raise ValueError("Select inches (1) or millimeters (4) explicitly.")
    if not circles:
        raise ValueError("At least one circle is required.")
    doc = ezdxf.new(version)
    doc.units = units
    space = doc.modelspace()
    for circle in circles:
        if not all(math.isfinite(v) for v in (circle.x, circle.y, circle.radius)):
            raise ValueError("Circle geometry must be finite.")
        if circle.radius <= 0:
            raise ValueError("Circle radius must be positive.")
        space.add_circle((circle.x, circle.y), circle.radius)
    output = StringIO()
    doc.write(output)
    return output.getvalue()
