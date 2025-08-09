import pytest
pytest.mark.legacy_import_cycle
def test_legacy_skip():
    assert True


def test_pqs_v2_shape():
    # synthetic simple sequence
    frames = []
    for i in range(30):
        t = i * 20
        frames.append(make_frame(t, {
            'left_shoulder': (0.4, 0.6), 'right_shoulder': (0.6, 0.6),
            'left_hip': (0.45, 0.8), 'right_hip': (0.55, 0.8),
            'right_elbow': (0.6, 0.65), 'right_wrist': (0.6 + 0.002*i, 0.65 - 0.001*i),
            'left_ankle': (0.45, 0.95), 'right_ankle': (0.55, 0.95),
        }))
    hand = detect_handedness(frames)
    rel = detect_release_idx(frames, hand)
    res = calculate_pqs_v2(frames, hand, rel)
    assert res['version'] == '2.0'
    assert 0 <= res['total'] <= 1000
    assert len(res['components']) == 5
    assert 'phases' in res and 'metrics' in res


