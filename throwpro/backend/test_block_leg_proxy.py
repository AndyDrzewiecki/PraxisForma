from backend.biomech.features import compute_features
from backend.pqs_algorithm import Frame, Landmark


def _mk_frames_slowdown():
    frames = []
    # Simulate hand speed peaking near end; thorax omega dropping -> positive horiz proxy
    for i in range(60):
        t = i * 10
        # simple linear decrease in thorax angle rate by crafting shoulder alignment
        dy = 0.2 if i < 45 else 0.05
        ls = Landmark(x=0.4, y=0.3)
        rs = Landmark(x=0.6, y=0.3 + dy)
        lh = Landmark(x=0.4, y=0.5)
        rh = Landmark(x=0.6, y=0.5)
        # wrist increases velocity toward the end
        wx = 0.4 + (i/60)
        wy = 0.2
        w = Landmark(x=wx, y=wy)
        frames.append(Frame(t_ms=t, kp={'left_hip': lh, 'right_hip': rh, 'left_shoulder': ls, 'right_shoulder': rs, 'right_wrist': w}))
    return frames


def test_block_proxies_positive():
    frames = _mk_frames_slowdown()
    series, phases, metrics = compute_features(frames, 'right', release_idx=None)
    assert metrics['F_block_horiz_proxy'] >= 0
    assert metrics['F_block_vert_proxy'] >= 0


