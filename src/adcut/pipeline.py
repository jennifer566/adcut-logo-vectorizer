"""Input decoding and SVG-first curve vectorization."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import vtracer
from PIL import Image, ImageOps, UnidentifiedImageError
from svgelements import Arc, Close, CubicBezier, Line, QuadraticBezier
from svgelements import Path as SVGPath

MAX_INPUT_BYTES = 25 * 1024 * 1024
MAX_SOURCE_PIXELS = 40_000_000


class VectorizationError(ValueError):
    """Raised when an input cannot produce usable vector geometry."""


@dataclass(frozen=True)
class VectorizationOptions:
    output_width: float
    units: str
    color_count: int = 4
    simplification: float = 1.5
    minimum_area: float = 12.0
    ignore_border_color: bool = True

    def validate(self) -> None:
        if not math.isfinite(self.output_width) or self.output_width <= 0:
            raise VectorizationError("Output width must be a positive number.")
        if self.units not in {"mm", "in"}:
            raise VectorizationError("Units must be millimeters or inches.")
        if not 2 <= self.color_count <= 12:
            raise VectorizationError("Color count must be between 2 and 12.")
        if not 0 <= self.simplification <= 10:
            raise VectorizationError("Simplification must be between 0 and 10 pixels.")
        if self.minimum_area < 1:
            raise VectorizationError("Minimum area must be at least one pixel.")


@dataclass(frozen=True)
class PathLoop:
    svg_path: str
    is_closed: bool
    curve_segments: int
    line_segments: int


@dataclass(frozen=True)
class ColorRegion:
    identifier: int
    color: tuple[int, int, int]
    loops: tuple[PathLoop, ...]

    @property
    def layer_name(self) -> str:
        red, green, blue = self.color
        return f"REGION_{self.identifier:02d}_{red:02X}{green:02X}{blue:02X}"


@dataclass(frozen=True)
class VectorizationResult:
    source_width: int
    source_height: int
    output_width: float
    output_height: float
    units: str
    regions: tuple[ColorRegion, ...]
    preview_svg: bytes
    warnings: tuple[str, ...]

    @property
    def path_count(self) -> int:
        return sum(len(region.loops) for region in self.regions)

    @property
    def curve_segment_count(self) -> int:
        return sum(loop.curve_segments for region in self.regions for loop in region.loops)

    @property
    def line_segment_count(self) -> int:
        return sum(loop.line_segments for region in self.regions for loop in region.loops)


def _decode_pdf(data: bytes) -> Image.Image:
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(data)
        if len(document) == 0:
            raise VectorizationError("The PDF does not contain any pages.")
        return document[0].render(scale=2).to_pil()
    except VectorizationError:
        raise
    except Exception as exc:
        raise VectorizationError("The first PDF page could not be rendered.") from exc


def decode_image(data: bytes, filename: str = "") -> Image.Image:
    """Decode input to RGBA; Pillow normalizes formats but does not trace paths."""
    if not data:
        raise VectorizationError("Choose a non-empty image file.")
    if len(data) > MAX_INPUT_BYTES:
        raise VectorizationError("The selected file exceeds the 25 MB upload limit.")

    suffix = Path(filename).suffix.lower()
    try:
        image = _decode_pdf(data) if suffix == ".pdf" else Image.open(BytesIO(data))
        image.seek(0)
        if image.width * image.height > MAX_SOURCE_PIXELS:
            raise VectorizationError("The decoded image exceeds the 40-megapixel processing limit.")
        rgba = ImageOps.exif_transpose(image).convert("RGBA")
    except VectorizationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise VectorizationError("The selected file is not a readable image.") from exc

    background = Image.new("RGBA", rgba.size, "white")
    background.alpha_composite(rgba)
    if background.width < 2 or background.height < 2:
        raise VectorizationError("The image must be at least two pixels in each dimension.")
    return background


def _dominant_border_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    pixels = rgb.load()
    border = [pixels[x, 0] for x in range(rgb.width)]
    border.extend(pixels[x, rgb.height - 1] for x in range(rgb.width))
    border.extend(pixels[0, y] for y in range(rgb.height))
    border.extend(pixels[rgb.width - 1, y] for y in range(rgb.height))
    return Counter(border).most_common(1)[0][0]


def _parse_color(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    value = value.strip().lower()
    if value.startswith("#") and len(value) == 7:
        try:
            return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))
        except ValueError:
            return None
    if value.startswith("rgb(") and value.endswith(")"):
        try:
            channels = tuple(int(part.strip()) for part in value[4:-1].split(","))
        except ValueError:
            return None
        return channels if len(channels) == 3 else None
    return None


def _path_color(element: ElementTree.Element) -> tuple[int, int, int] | None:
    color = _parse_color(element.get("fill"))
    if color is not None:
        return color
    declarations = {
        key.strip(): value.strip()
        for declaration in element.get("style", "").split(";")
        if ":" in declaration
        for key, value in [declaration.split(":", 1)]
    }
    return _parse_color(declarations.get("fill"))


def _is_close_color(
    first: tuple[int, int, int], second: tuple[int, int, int], tolerance: int = 12
) -> bool:
    return max(abs(a - b) for a, b in zip(first, second, strict=True)) <= tolerance


def _describe_path(path_data: str) -> PathLoop:
    try:
        path = SVGPath(path_data)
    except Exception as exc:
        raise VectorizationError("The SVG tracer produced an unreadable path.") from exc
    curves = sum(isinstance(segment, (CubicBezier, QuadraticBezier, Arc)) for segment in path)
    lines = sum(isinstance(segment, Line) and not isinstance(segment, Close) for segment in path)
    return PathLoop(
        svg_path=path_data,
        is_closed=any(isinstance(segment, Close) for segment in path),
        curve_segments=curves,
        line_segments=lines,
    )


def _trace_svg(image: Image.Image, options: VectorizationOptions) -> str:
    config = vtracer.Config(
        mode="spline",
        hierarchical="cutout",
        filter_speckle=max(1, round(options.minimum_area)),
        max_colors=options.color_count,
        simplify=options.simplification or None,
        path_precision=4,
        optimize=2,
    )
    try:
        return config.convert_pixels(image.tobytes(), image.width, image.height)
    except Exception as exc:
        raise VectorizationError("The image could not be converted to SVG curves.") from exc


def _regions_from_svg(
    svg: str, *, background_color: tuple[int, int, int] | None
) -> tuple[ColorRegion, ...]:
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:
        raise VectorizationError("The SVG tracer returned invalid XML.") from exc

    grouped: dict[tuple[int, int, int], list[PathLoop]] = {}
    for element in root.iter():
        if not element.tag.endswith("path"):
            continue
        path_data = element.get("d", "").strip()
        color = _path_color(element)
        if not path_data or color is None:
            continue
        if background_color is not None and _is_close_color(color, background_color):
            continue
        loop = _describe_path(path_data)
        if loop.is_closed:
            grouped.setdefault(color, []).append(loop)

    return tuple(
        ColorRegion(identifier=index, color=color, loops=tuple(loops))
        for index, (color, loops) in enumerate(sorted(grouped.items()), start=1)
        if loops
    )


def vectorize_image(
    data: bytes, *, filename: str, options: VectorizationOptions
) -> VectorizationResult:
    """Convert uploaded artwork into closed SVG spline paths grouped by color."""
    options.validate()
    image = decode_image(data, filename)
    traced_svg = _trace_svg(image, options)
    background = _dominant_border_color(image) if options.ignore_border_color else None
    regions = _regions_from_svg(traced_svg, background_color=background)
    if not regions:
        raise VectorizationError(
            "No usable foreground regions were found. Try including the border color or lowering the minimum area."
        )

    scale = options.output_width / image.width
    warnings = [
        "Curves are exported as native cubic DXF splines; circle and arc recognition still requires validation.",
        "Review all paths and scale in CAD software before sending output to cutting equipment.",
    ]
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        warnings.append("Only the first PDF page is processed in this version.")
    if suffix == ".gif":
        warnings.append("Only the first GIF frame is processed in this version.")

    return VectorizationResult(
        source_width=image.width,
        source_height=image.height,
        output_width=options.output_width,
        output_height=image.height * scale,
        units=options.units,
        regions=regions,
        preview_svg=traced_svg.encode("utf-8"),
        warnings=tuple(warnings),
    )
