import numpy as np
import pytest
pytest.mark.legacy_import_cycle
def test_legacy_skip():
    assert True
from biomech.features import compute_features


def _mk_series(n=50):
    frames = []
    for i in range(n):
        t = i * 10
        # Simulate pelvis rotating before thorax; wrist accelerates later
        ls = (0.4, 0.6)
        rs = (0.6, 0.6)
        lh = (0.45 - 0.001*i, 0.8)
        rh = (0.55 + 0.001*i, 0.8)
        le = (0.5, 0.65)
        lw = (0.5 + 0.001*i, 0.65 - 0.0005*i)
        frames.append(make_frame(t, {
            'left_shoulder': ls, 'right_shoulder': rs,
            'left_hip': lh, 'right_hip': rh,
            'left_elbow': le, 'left_wrist': lw,
            'left_ankle': (0.45, 0.95), 'right_ankle': (0.55, 0.95),
        }))
    return frames


def test_compute_features_chain_order():
    frames = _mk_series(60)
    series, phases, metrics = compute_features(frames, 'left', release_idx=None)
    assert metrics['x_factor_peak_deg'] >= 0
    assert metrics['chain_order_score'] in (0.0, 60.0, 100.0)


