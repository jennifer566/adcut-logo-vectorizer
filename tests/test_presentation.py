from base64 import b64decode

import pytest

from adcut.presentation import svg_data_uri


def test_svg_data_uri_round_trip():
    svg = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0Z"/></svg>'
    )

    uri = svg_data_uri(svg)

    prefix, encoded = uri.split(",", maxsplit=1)
    assert prefix == "data:image/svg+xml;base64"
    assert b64decode(encoded) == svg


def test_svg_data_uri_rejects_non_svg_data():
    with pytest.raises(ValueError, match="<svg>"):
        svg_data_uri(b"not an image")
