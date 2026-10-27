import hashlib
import json
from io import BytesIO, StringIO

import ezdxf
import pytest
from PIL import Image, ImageDraw
from svgelements import Close
from svgelements import Path as SVGPath

from adcut import pipeline
from adcut.export import export_dxf, export_report, export_svg
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


def test_report_records_source_settings_geometry_and_warnings():
    source = sample_png()
    result = vectorize_image(source, filename="folder/sample.png", options=options())

    report = json.loads(export_report(result))

    assert report["schema_version"] == 1
    assert report["source"] == {
        "filename": "sample.png",
        "sha256": hashlib.sha256(source).hexdigest(),
        "width_pixels": 200,
        "height_pixels": 100,
    }
    assert report["settings"]["maximum_colors"] == 3
    assert report["settings"]["curve_simplification_pixels"] == 1.5
    assert report["output"]["width"] == 20
    assert report["output"]["closed_path_count"] == result.path_count
    assert report["output"]["regions"][0]["layer"].startswith("REGION_")
    assert report["warnings"] == list(result.warnings)


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


def test_oversized_upload_is_rejected_before_decoding(monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_INPUT_BYTES", 4)

    with pytest.raises(VectorizationError, match="25 MB upload limit"):
        vectorize_image(b"12345", filename="sample.png", options=options())


def test_large_decoded_image_is_rejected(monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_SOURCE_PIXELS", 100)

    with pytest.raises(VectorizationError, match="40-megapixel processing limit"):
        vectorize_image(sample_png(), filename="sample.png", options=options())


def test_region_identifiers_are_stable_when_tracer_order_changes(monkeypatch):
    paths = {
        "red": '<path fill="#ff0000" d="M0 0 L10 0 L10 10 Z"/>',
        "blue": '<path fill="#0000ff" d="M20 0 L30 0 L30 10 Z"/>',
    }

    def result_for(order):
        svg = f'<svg xmlns="http://www.w3.org/2000/svg">{order}</svg>'
        monkeypatch.setattr(pipeline, "_trace_svg", lambda image, settings: svg)
        return vectorize_image(
            sample_png(),
            filename="sample.png",
            options=options(ignore_border_color=False),
        )

    first = result_for(paths["red"] + paths["blue"])
    second = result_for(paths["blue"] + paths["red"])

    assert [(region.identifier, region.color) for region in first.regions] == [
        (1, (0, 0, 255)),
        (2, (255, 0, 0)),
    ]
    assert [(region.identifier, region.color) for region in second.regions] == [
        (1, (0, 0, 255)),
        (2, (255, 0, 0)),
    ]
