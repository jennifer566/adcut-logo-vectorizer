"""Export explicit CAD geometry without approximating circles with short lines."""

import math
from dataclasses import dataclass
from io import StringIO
from xml.etree import ElementTree

import ezdxf

from adcut.pipeline import VectorizationResult


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


def export_dxf(result: VectorizationResult, *, version: str = "R2000") -> bytes:
    """Export traced region loops as closed DXF polylines."""
    if not result.regions:
        raise ValueError("At least one traced region is required.")
    units = 4 if result.units == "mm" else 1
    doc = ezdxf.new(version)
    doc.units = units
    space = doc.modelspace()
    for region in result.regions:
        if region.layer_name not in doc.layers:
            doc.layers.add(region.layer_name, color=7)
        for loop in region.loops:
            entity = space.add_lwpolyline(
                loop.points,
                close=True,
                dxfattribs={"layer": region.layer_name},
            )
            entity.rgb = region.color
    output = StringIO()
    doc.write(output)
    return output.getvalue().encode("utf-8")


def export_svg(result: VectorizationResult) -> bytes:
    """Export traced region loops as closed SVG paths in physical units."""
    if not result.regions:
        raise ValueError("At least one traced region is required.")
    namespace = "http://www.w3.org/2000/svg"
    ElementTree.register_namespace("", namespace)
    root = ElementTree.Element(
        f"{{{namespace}}}svg",
        {
            "width": f"{result.output_width:.6g}{result.units}",
            "height": f"{result.output_height:.6g}{result.units}",
            "viewBox": f"0 0 {result.output_width:.6g} {result.output_height:.6g}",
        },
    )
    for region in result.regions:
        red, green, blue = region.color
        group = ElementTree.SubElement(
            root,
            f"{{{namespace}}}g",
            {"id": region.layer_name, "stroke": f"#{red:02x}{green:02x}{blue:02x}"},
        )
        for loop in region.loops:
            points = " ".join(
                f"{'M' if index == 0 else 'L'} {x:.6g} {result.output_height - y:.6g}"
                for index, (x, y) in enumerate(loop.points)
            )
            ElementTree.SubElement(
                group,
                f"{{{namespace}}}path",
                {"d": f"{points} Z", "fill": "none", "stroke-width": "0.2"},
            )
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
