import math
from typing import Tuple


def arc_points(cx: int, cy: int, radius: int, start_deg: float, end_deg: float, step_deg: float = 4.0):
    pts = []
    s = math.radians(start_deg)
    e = math.radians(end_deg)
    if e < s:
        s, e = e, s
    a = s
    while a <= e:
        x = int(cx + radius * math.cos(a))
        y = int(cy - radius * math.sin(a))
        pts.append((x, y))
        a += math.radians(step_deg)
    return pts


def label_box(x: int, y: int, text_w: int, text_h: int, pad: int, frame_w: int, frame_h: int) -> Tuple[int, int, int, int]:
    # Keep box within frame
    w = text_w + 2 * pad
    h = text_h + 2 * pad
    x0 = max(0, min(x, frame_w - w))
    y0 = max(0, min(y, frame_h - h))
    return x0, y0, x0 + w, y0 + h


