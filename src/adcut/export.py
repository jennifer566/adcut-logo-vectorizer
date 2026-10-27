"""Export SVG paths as physical SVG and native DXF curve entities."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from io import StringIO
from xml.etree import ElementTree

import ezdxf
from ezdxf.path import Path as DXFPath
from ezdxf.path import render_splines_and_polylines
from svgelements import Arc, Close, CubicBezier, Line, Move, QuadraticBezier
from svgelements import Path as SVGPath

from adcut.pipeline import PathLoop, VectorizationResult


@dataclass(frozen=True)
class Circle:
    x: float
    y: float
    radius: float


def export_circles(circles: list[Circle], *, units: int, version: str = "R2000") -> str:
    """Export caller-supplied circles as native DXF CIRCLE entities."""
    if units not in (1, 4):
        raise ValueError("Select inches (1) or millimeters (4) explicitly.")
    if not circles:
        raise ValueError("At least one circle is required.")
    doc = ezdxf.new(version)
    doc.units = units
    space = doc.modelspace()
    for circle in circles:
        if not all(math.isfinite(value) for value in (circle.x, circle.y, circle.radius)):
            raise ValueError("Circle geometry must be finite.")
        if circle.radius <= 0:
            raise ValueError("Circle radius must be positive.")
        space.add_circle((circle.x, circle.y), circle.radius)
    output = StringIO()
    doc.write(output)
    return output.getvalue()


def _point(value, *, scale: float, source_height: int) -> tuple[float, float]:
    return float(value.x) * scale, (source_height - float(value.y)) * scale


def _to_dxf_paths(loop: PathLoop, result: VectorizationResult) -> list[DXFPath]:
    source = SVGPath(loop.svg_path)
    scale = result.output_width / result.source_width
    paths: list[DXFPath] = []
    current: DXFPath | None = None

    def ensure_path(start) -> DXFPath:
        nonlocal current
        if current is None:
            current = DXFPath(_point(start, scale=scale, source_height=result.source_height))
        return current

    for segment in source:
        if isinstance(segment, Move):
            if current is not None and len(current):
                paths.append(current)
            current = DXFPath(_point(segment.end, scale=scale, source_height=result.source_height))
        elif isinstance(segment, Close):
            if current is not None:
                current.close()
        elif isinstance(segment, CubicBezier):
            path = ensure_path(segment.start)
            path.curve4_to(
                _point(segment.end, scale=scale, source_height=result.source_height),
                _point(segment.control1, scale=scale, source_height=result.source_height),
                _point(segment.control2, scale=scale, source_height=result.source_height),
            )
        elif isinstance(segment, QuadraticBezier):
            path = ensure_path(segment.start)
            path.curve3_to(
                _point(segment.end, scale=scale, source_height=result.source_height),
                _point(segment.control, scale=scale, source_height=result.source_height),
            )
        elif isinstance(segment, Arc):
            path = ensure_path(segment.start)
            for curve in segment.as_cubic_curves():
                path.curve4_to(
                    _point(curve.end, scale=scale, source_height=result.source_height),
                    _point(curve.control1, scale=scale, source_height=result.source_height),
                    _point(curve.control2, scale=scale, source_height=result.source_height),
                )
        elif isinstance(segment, Line):
            path = ensure_path(segment.start)
            path.line_to(_point(segment.end, scale=scale, source_height=result.source_height))

    if current is not None and len(current):
        paths.append(current)
    return paths


def export_dxf(result: VectorizationResult, *, version: str = "R2000") -> bytes:
    """Export traced Bezier paths as native DXF SPLINE and POLYLINE entities."""
    if not result.regions:
        raise ValueError("At least one traced region is required.")
    if version == "R12":
        raise ValueError("Native spline export requires DXF R2000 or newer.")
    doc = ezdxf.new(version)
    doc.units = 4 if result.units == "mm" else 1
    space = doc.modelspace()
    for region in result.regions:
        if region.layer_name not in doc.layers:
            doc.layers.add(region.layer_name, color=7)
        for loop in region.loops:
            entities = render_splines_and_polylines(
                space,
                _to_dxf_paths(loop, result),
                dxfattribs={"layer": region.layer_name},
            )
            for entity in entities:
                entity.rgb = region.color
    output = StringIO()
    doc.write(output)
    return output.getvalue().encode("utf-8")


def export_svg(result: VectorizationResult) -> bytes:
    """Export traced paths without flattening their SVG curve commands."""
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
    scale = result.output_width / result.source_width
    drawing = ElementTree.SubElement(
        root, f"{{{namespace}}}g", {"transform": f"scale({scale:.12g})"}
    )
    for region in result.regions:
        red, green, blue = region.color
        group = ElementTree.SubElement(
            drawing,
            f"{{{namespace}}}g",
            {
                "id": region.layer_name,
                "fill": "none",
                "stroke": f"#{red:02x}{green:02x}{blue:02x}",
                "stroke-width": f"{0.2 / scale:.12g}",
            },
        )
        for loop in region.loops:
            ElementTree.SubElement(group, f"{{{namespace}}}path", {"d": loop.svg_path})
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def export_report(result: VectorizationResult) -> bytes:
    """Export the source identity, settings, geometry summary, and warnings as JSON."""
    report = {
        "schema_version": 1,
        "source": {
            "filename": result.source_filename,
            "sha256": result.source_sha256,
            "width_pixels": result.source_width,
            "height_pixels": result.source_height,
        },
        "settings": {
            "output_width": result.options.output_width,
            "units": result.options.units,
            "maximum_colors": result.options.color_count,
            "curve_simplification_pixels": result.options.simplification,
            "minimum_area_pixels": result.options.minimum_area,
            "ignore_dominant_border_color": result.options.ignore_border_color,
        },
        "output": {
            "width": result.output_width,
            "height": result.output_height,
            "units": result.units,
            "region_count": len(result.regions),
            "closed_path_count": result.path_count,
            "curve_segment_count": result.curve_segment_count,
            "line_segment_count": result.line_segment_count,
            "regions": [
                {
                    "identifier": region.identifier,
                    "layer": region.layer_name,
                    "color": "#" + "".join(f"{channel:02X}" for channel in region.color),
                    "closed_path_count": len(region.loops),
                    "curve_segment_count": sum(loop.curve_segments for loop in region.loops),
                    "line_segment_count": sum(loop.line_segments for loop in region.loops),
                }
                for region in result.regions
            ],
        },
        "warnings": list(result.warnings),
    }
    return (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
