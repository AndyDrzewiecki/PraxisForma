from backend.pqs_algorithm import calculate_pqs_v2, Frame, Landmark


def _mk_seq_frames():
    frames = []
    for i in range(60):
        t = i * 10
        # Hips rotate first
        lh = Landmark(x=0.4, y=0.5)
        rh = Landmark(x=0.6, y=0.5 + 0.1)
        # Shoulders lag
        ls = Landmark(x=0.4, y=0.3)
        rs = Landmark(x=0.6, y=0.3 + (0.1 if i > 5 else 0.0))
        # Hand speed peaks later
        w = Landmark(x=0.5 + (i/60)*0.3, y=0.2)
        frames.append(Frame(t_ms=t, kp={'left_hip': lh, 'right_hip': rh, 'left_shoulder': ls, 'right_shoulder': rs, 'right_wrist': w}))
    return frames


def test_sep_seq_and_platform_scores_change_with_envelope(monkeypatch):
    frames = _mk_seq_frames()
    # Favorable sequencing window
    env1 = ({'version': 10, 'components': {'separation_sequencing': {'Δhip_torso_ms': [40, 120], 'Δtorso_hand_ms': [35, 100], 'chain_order_score_min': 0.6}, 'release_quality': {'release_angle_deg': [30, 40]}}}, False)
    env2 = ({'version': 11, 'components': {'separation_sequencing': {'Δhip_torso_ms': [10, 20], 'Δtorso_hand_ms': [10, 20], 'chain_order_score_min': 0.95}, 'release_quality': {'release_angle_deg': [20, 25]}}}, False)
    monkeypatch.setattr('backend.biomech.envelope_store.load_active_envelope', lambda e,a,s,h: env1[0])
    res1 = calculate_pqs_v2(frames, 'right', None, event='discus', age_band='Open', sex='M')
    monkeypatch.setattr('backend.biomech.envelope_store.load_active_envelope', lambda e,a,s,h: env2[0])
    res2 = calculate_pqs_v2(frames, 'right', None, event='discus', age_band='Open', sex='M')
    assert res1['components']['separation_sequencing'] >= res2['components']['separation_sequencing']


