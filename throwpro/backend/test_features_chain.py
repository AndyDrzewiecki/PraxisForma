import numpy as np
from backend.pqs_algorithm import Frame, Landmark
from backend.biomech.features import compute_features


def _mk_frames_with_peaks():
    frames = []
    t = 0
    # pelvis angle increases then decreases; thorax lags; hand speed lags further
    for i in range(50):
        t = i * 10
        # Create synthetic hips/shoulders alignment to simulate rotations
        lh = Landmark(x=0.4, y=0.5)
        rh = Landmark(x=0.6, y=0.5 + 0.1*np.sin(i/8))
        ls = Landmark(x=0.4, y=0.3)
        rs = Landmark(x=0.6, y=0.3 + 0.1*np.sin((i-4)/8))
        # Wrist moves fastest later
        w = Landmark(x=0.7 + 0.2*np.sin((i-8)/6), y=0.2)
        f = Frame(t_ms=t, kp={'left_hip': lh, 'right_hip': rh, 'left_shoulder': ls, 'right_shoulder': rs, 'right_wrist': w})
        frames.append(f)
    return frames


def test_delta_peaks_increasing():
    frames = _mk_frames_with_peaks()
    series, phases, metrics = compute_features(frames, 'right', release_idx=None)
    assert metrics['Δhip_torso_ms'] >= 0
    assert metrics['Δtorso_hand_ms'] >= 0


