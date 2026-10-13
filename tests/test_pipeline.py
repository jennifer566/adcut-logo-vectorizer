from io import BytesIO, StringIO

import ezdxf
import pytest
from PIL import Image, ImageDraw
from svgelements import Close
from svgelements import Path as SVGPath

from adcut.export import export_dxf, export_svg
from adcut.pipeline import VectorizationError, VectorizationOptions, vectorize_image


def sample_png() -> bytes:
    image = Image.new("RGB", (200, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 90, 90), fill=(75, 156, 211))
    draw.ellipse((110, 10, 190, 90), fill=(19, 41, 75))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def options(**overrides) -> VectorizationOptions:
    values = {"output_width": 20.0, "units": "in", "color_count": 3}
    values.update(overrides)
    return VectorizationOptions(**values)


def test_vectorization_creates_scaled_closed_regions():
    result = vectorize_image(sample_png(), filename="sample.png", options=options())
    assert result.source_width == 200
    assert result.output_width == 20
    assert result.output_height == 10
    assert len(result.regions) == 2
    assert result.path_count == 2
    assert result.curve_segment_count > 0
    assert all(loop.is_closed for region in result.regions for loop in region.loops)
    assert b"<svg" in result.preview_svg[:200]


def test_dxf_contains_native_splines_and_explicit_units():
    result = vectorize_image(sample_png(), filename="sample.png", options=options())
    document = ezdxf.read(StringIO(export_dxf(result).decode("utf-8")))
    entities = list(document.modelspace())
    assert document.units == 1
    assert entities
    assert all(entity.dxftype() in {"SPLINE", "POLYLINE"} for entity in entities)
    assert any(entity.dxftype() == "SPLINE" for entity in entities)
    assert not any(entity.dxftype() == "LWPOLYLINE" for entity in entities)
    assert all(entity.dxf.layer.startswith("REGION_") for entity in entities)
    assert not document.audit().has_errors


def test_svg_uses_physical_dimensions_and_closed_paths():
    result = vectorize_image(sample_png(), filename="sample.png", options=options(units="mm"))
    svg = export_svg(result).decode("utf-8")
    assert 'width="20mm"' in svg
    assert 'height="10mm"' in svg
    assert svg.count("<path") == 2
    assert all(
        any(isinstance(segment, Close) for segment in SVGPath(loop.svg_path))
        for region in result.regions
        for loop in region.loops
    )


def test_r12_is_rejected_because_it_cannot_preserve_native_splines():
    result = vectorize_image(sample_png(), filename="sample.png", options=options())
    with pytest.raises(ValueError, match="R2000"):
        export_dxf(result, version="R12")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"output_width": 0}, "positive"),
        ({"units": "px"}, "millimeters or inches"),
        ({"color_count": 1}, "between 2 and 12"),
    ],
)
def test_invalid_options_are_rejected(overrides, message):
    with pytest.raises(VectorizationError, match=message):
        vectorize_image(sample_png(), filename="sample.png", options=options(**overrides))


def test_unreadable_image_is_rejected():
    with pytest.raises(VectorizationError, match="not a readable image"):
        vectorize_image(b"not an image", filename="bad.png", options=options())
