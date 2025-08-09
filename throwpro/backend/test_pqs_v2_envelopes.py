from backend.pqs_algorithm import calculate_pqs_v2, Frame, Landmark


def _make_frames():
    # Minimal frames around release to exercise release angle metric
    frames = []
    for t in range(0, 300, 33):
        # Straight horizontal forearm ~35 deg at t=165
        ang = 35.0
        # Use simple two-point elbow-wrist with shoulder as reference
        f = Frame(t_ms=t, kp={
            'right_shoulder': Landmark(x=0.5, y=0.5),
            'right_elbow': Landmark(x=0.5, y=0.5),
            'right_wrist': Landmark(x=0.5 - 0.2, y=0.5 - 0.2),
        })
        frames.append(f)
    return frames


def test_envelope_changes_release_scoring(monkeypatch):
    # Monkeypatch envelope store to return two different bands
    from backend import pqs_algorithm as algo
    frames = _make_frames()
    # Band 1: tight around 35 (high score)
    monkeypatch.setattr('backend.biomech.envelope_store.load_active_envelope', lambda e,a,s,h: ({'version': 2, 'components': {'release_quality': {'release_angle_deg': [32, 38]}}}, False))
    res1 = calculate_pqs_v2(frames, 'right', rel_idx=4, event='discus', age_band='Open', sex='M')
    # Band 2: far from 35 (lower score)
    monkeypatch.setattr('backend.biomech.envelope_store.load_active_envelope', lambda e,a,s,h: ({'version': 3, 'components': {'release_quality': {'release_angle_deg': [10, 20]}}}, False))
    res2 = calculate_pqs_v2(frames, 'right', rel_idx=4, event='discus', age_band='Open', sex='M')
    assert res1['components']['release_quality'] >= res2['components']['release_quality']


