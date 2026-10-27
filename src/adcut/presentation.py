"""Browser presentation helpers for generated vector artwork."""

from base64 import b64encode


def svg_data_uri(svg: bytes) -> str:
    """Return SVG bytes as a browser-safe data URI."""
    if b"<svg" not in svg.lstrip()[:512].lower():
        raise ValueError("SVG preview must contain an <svg> element")
    encoded = b64encode(svg).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
