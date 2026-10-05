"""Raster decoding, color reduction, contour tracing, and preview generation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


class VectorizationError(ValueError):
    """Raised when an input cannot produce usable vector geometry."""


@dataclass(frozen=True)
class VectorizationOptions:
    output_width: float
    units: str
    color_count: int = 4
    simplification: float = 0.002
    minimum_area: float = 12.0
    ignore_border_color: bool = True

    def validate(self) -> None:
        if not np.isfinite(self.output_width) or self.output_width <= 0:
            raise VectorizationError("Output width must be a positive number.")
        if self.units not in {"mm", "in"}:
            raise VectorizationError("Units must be millimeters or inches.")
        if not 2 <= self.color_count <= 12:
            raise VectorizationError("Color count must be between 2 and 12.")
        if not 0 <= self.simplification <= 0.05:
            raise VectorizationError("Simplification must be between 0 and 0.05.")
        if self.minimum_area < 1:
            raise VectorizationError("Minimum area must be at least one pixel.")


@dataclass(frozen=True)
class PathLoop:
    points: tuple[tuple[float, float], ...]
    is_hole: bool


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
    preview_png: bytes
    warnings: tuple[str, ...]

    @property
    def path_count(self) -> int:
        return sum(len(region.loops) for region in self.regions)


def _decode_pdf(data: bytes) -> Image.Image:
    try:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(data)
        if len(document) == 0:
            raise VectorizationError("The PDF does not contain any pages.")
        page = document[0]
        return page.render(scale=2).to_pil()
    except VectorizationError:
        raise
    except Exception as exc:
        raise VectorizationError("The first PDF page could not be rendered.") from exc


def decode_image(data: bytes, filename: str = "") -> Image.Image:
    """Decode a supported file and return an opaque RGB image.

    GIF processing uses the first frame. PDF processing uses the first page until
    the client confirms page and crop behavior.
    """
    if not data:
        raise VectorizationError("Choose a non-empty image file.")

    suffix = Path(filename).suffix.lower()
    try:
        image = _decode_pdf(data) if suffix == ".pdf" else Image.open(BytesIO(data))
        image.seek(0)
        image = ImageOps.exif_transpose(image)
        rgba = image.convert("RGBA")
    except VectorizationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise VectorizationError("The selected file is not a readable image.") from exc

    background = Image.new("RGBA", rgba.size, "white")
    background.alpha_composite(rgba)
    rgb = background.convert("RGB")
    if rgb.width < 2 or rgb.height < 2:
        raise VectorizationError("The image must be at least two pixels in each dimension.")
    return rgb


def _border_index(indexed: np.ndarray) -> int:
    border = np.concatenate((indexed[0, :], indexed[-1, :], indexed[:, 0], indexed[:, -1]))
    return Counter(int(value) for value in border).most_common(1)[0][0]


def _quantize(
    image: Image.Image, color_count: int
) -> tuple[np.ndarray, dict[int, tuple[int, int, int]]]:
    quantized = image.quantize(colors=color_count, method=Image.Quantize.MEDIANCUT)
    indexed = np.asarray(quantized, dtype=np.uint8)
    palette = quantized.getpalette()
    used = sorted(int(value) for value in np.unique(indexed))
    colors = {
        index: tuple(int(channel) for channel in palette[index * 3 : index * 3 + 3])
        for index in used
    }
    return indexed, colors


def _scaled_points(
    contour: np.ndarray, *, scale: float, source_height: int
) -> tuple[tuple[float, float], ...]:
    return tuple(
        (
            round(float(point[0][0]) * scale, 6),
            round((source_height - float(point[0][1])) * scale, 6),
        )
        for point in contour
    )


def vectorize_image(
    data: bytes, *, filename: str, options: VectorizationOptions
) -> VectorizationResult:
    """Convert a raster image into closed color-region paths.

    This first implementation produces closed polylines. Native curve fitting and
    shared-edge deduplication remain separate validation work.
    """
    options.validate()
    image = decode_image(data, filename)
    indexed, colors = _quantize(image, options.color_count)
    ignored_index = _border_index(indexed) if options.ignore_border_color else None
    scale = options.output_width / image.width
    output_height = image.height * scale
    regions: list[ColorRegion] = []
    preview = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)

    for palette_index, color in colors.items():
        if palette_index == ignored_index:
            continue
        mask = np.where(indexed == palette_index, 255, 0).astype(np.uint8)
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if hierarchy is None:
            continue
        loops: list[PathLoop] = []
        retained_contours: list[np.ndarray] = []
        for index, contour in enumerate(contours):
            if abs(cv2.contourArea(contour)) < options.minimum_area:
                continue
            perimeter = cv2.arcLength(contour, True)
            epsilon = options.simplification * perimeter
            approximated = cv2.approxPolyDP(contour, epsilon, True)
            if len(approximated) < 3:
                continue
            points = _scaled_points(approximated, scale=scale, source_height=image.height)
            loops.append(PathLoop(points=points, is_hole=bool(hierarchy[0][index][3] >= 0)))
            retained_contours.append(approximated)

        if loops:
            region = ColorRegion(identifier=len(regions) + 1, color=color, loops=tuple(loops))
            regions.append(region)
            cv2.drawContours(preview, retained_contours, -1, (75, 41, 19), 2)

    if not regions:
        raise VectorizationError(
            "No usable foreground regions were found. Try including the border color or lowering the minimum area."
        )

    success, encoded = cv2.imencode(".png", preview)
    if not success:
        raise VectorizationError("The preview image could not be created.")

    warnings = [
        "This initial trace uses closed polylines; native circle and arc fitting is not applied yet.",
        "Adjacent color regions may contain duplicate shared edges and require CAD review before cutting.",
    ]
    if Path(filename).suffix.lower() == ".pdf":
        warnings.append("Only the first PDF page is processed in this version.")
    if Path(filename).suffix.lower() == ".gif":
        warnings.append("Only the first GIF frame is processed in this version.")

    return VectorizationResult(
        source_width=image.width,
        source_height=image.height,
        output_width=options.output_width,
        output_height=output_height,
        units=options.units,
        regions=tuple(regions),
        preview_png=encoded.tobytes(),
        warnings=tuple(warnings),
    )
