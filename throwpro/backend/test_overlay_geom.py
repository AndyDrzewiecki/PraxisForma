from visual.geom import arc_points, label_box


def test_arc_points_monotonic():
    pts = arc_points(100, 100, 50, 0, 90)
    assert len(pts) > 0
    # x should be non-decreasing for 0..90 deg
    xs = [p[0] for p in pts]
    assert all(xs[i] <= xs[i+1] for i in range(len(xs)-1))


def test_label_box_bounds():
    x0, y0, x1, y1 = label_box(500, 500, 200, 50, 10, 640, 360)
    assert 0 <= x0 < x1 <= 640
    assert 0 <= y0 < y1 <= 360


