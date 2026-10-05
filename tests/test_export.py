from io import StringIO

import ezdxf
import pytest

from adcut.export import Circle, export_circles


def test_native_circle_round_trip():
    doc = ezdxf.read(StringIO(export_circles([Circle(10, 20, 5)], units=4)))
    entities = list(doc.modelspace())
    assert len(entities) == 1
    assert entities[0].dxftype() == "CIRCLE"
    assert entities[0].dxf.radius == 5
    assert tuple(entities[0].dxf.center) == (10, 20, 0)
    assert doc.units == 4
    assert not doc.audit().has_errors


@pytest.mark.parametrize("radius", [0, -1, float("nan"), float("inf")])
def test_invalid_radius_is_rejected(radius):
    with pytest.raises(ValueError):
        export_circles([Circle(0, 0, radius)], units=4)


def test_units_must_be_explicit_and_supported():
    with pytest.raises(ValueError):
        export_circles([Circle(0, 0, 5)], units=0)


def test_empty_geometry_is_rejected():
    with pytest.raises(ValueError):
        export_circles([], units=4)
