"""Drawing geometry of walls: a wall is drawn only where it borders the fluid."""
import numpy as np
import pytest

from app.geometry import clip_polygon, fluid_polygon, rect_polygon, visible_wall_segment
from physics import SymmetryWall as W

XR, YR = (-5.0, 5.0), (-4.0, 4.0)


def test_single_wall_spans_the_view():
    a, b = visible_wall_segment(W(yw=-1.0), [], XR, YR)
    assert {a.real, b.real} == {-5.0, 5.0} and a.imag == b.imag == -1.0


def test_wall_outside_view_is_not_drawn():
    assert visible_wall_segment(W(yw=10.0), [], XR, YR) is None


def test_90_degree_corner_is_an_L():
    """Fluid in the first quadrant: the walls are drawn only along x >= 0 and y >= 0."""
    a = W(xw=0.0, yw=0.0, theta_w=0.0, side=0)           # y = 0, fluid above
    b = W(xw=0.0, yw=0.0, theta_w=90.0, side=1)          # x = 0, fluid to the right
    sa = visible_wall_segment(a, [b], XR, YR)
    sb = visible_wall_segment(b, [a], XR, YR)
    assert sorted(z.real for z in sa) == pytest.approx([0.0, 5.0])
    assert sorted(z.imag for z in sb) == pytest.approx([0.0, 4.0])


@pytest.mark.parametrize("angle", [30.0, 60.0, 135.0])
def test_wedge_of_any_angle(angle):
    """Two walls meeting at the origin: each is drawn as a ray from the vertex into the wedge side."""
    a = W(xw=0.0, yw=0.0, theta_w=0.0, side=0)
    b = W(xw=0.0, yw=0.0, theta_w=angle, side=1)
    sa = visible_wall_segment(a, [b], XR, YR)
    sb = visible_wall_segment(b, [a], XR, YR)
    assert min(abs(z) for z in sa) == pytest.approx(0.0, abs=1e-12)   # starts at the vertex
    assert min(abs(z) for z in sb) == pytest.approx(0.0, abs=1e-12)
    far_b = max(sb, key=abs)
    assert np.degrees(np.angle(far_b)) == pytest.approx(angle)        # along the second wall's direction
    assert max(z.real for z in sa) == pytest.approx(5.0)               # along +x


def test_channel_walls_both_fully_visible():
    a, b = W(yw=-1.0, side=0), W(yw=1.0, side=1)
    for w, o in ((a, b), (b, a)):
        s = visible_wall_segment(w, [o], XR, YR)
        assert sorted(z.real for z in s) == pytest.approx([-5.0, 5.0])


def test_wall_behind_another_wall_is_hidden():
    front, hidden = W(yw=0.0, side=0), W(yw=-2.0, side=0)     # fluid above y = 0 hides y = −2
    assert visible_wall_segment(hidden, [front], XR, YR) is None


def test_fluid_polygon_and_clip():
    a = W(xw=0.0, yw=0.0, theta_w=0.0, side=0)
    b = W(xw=0.0, yw=0.0, theta_w=90.0, side=1)
    poly = fluid_polygon([a, b], XR, YR)
    xs, ys = [z.real for z in poly], [z.imag for z in poly]
    assert min(xs) == pytest.approx(0.0) and max(xs) == pytest.approx(5.0)
    assert min(ys) == pytest.approx(0.0) and max(ys) == pytest.approx(4.0)
    assert fluid_polygon([W(yw=0.0, side=1), W(yw=2.0, side=0)], XR, YR) == []   # no fluid
    half = clip_polygon(rect_polygon(XR, YR), lambda z: z.real)
    assert min(z.real for z in half) == pytest.approx(0.0)
