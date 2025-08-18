from backend.pqs_algorithm import calculate_pqs_v2, Frame, Landmark


def _frames_simple():
  # Minimal frames to produce metrics with deterministic times
  fs = []
  for i in range(10):
    t = i * 10
    fs.append(Frame(t_ms=t, kp={
      'left_hip': Landmark(x=0.4, y=0.5), 'right_hip': Landmark(x=0.6, y=0.5),
      'left_shoulder': Landmark(x=0.4, y=0.3), 'right_shoulder': Landmark(x=0.6, y=0.3),
      'right_wrist': Landmark(x=0.5 + i*0.01, y=0.2)
    }))
  return fs


def test_band_fit_keys_present(monkeypatch):
  frames = _frames_simple()
  # Envelope bands that make metrics fall inside
  monkeypatch.setattr('backend.biomech.envelope_store.load_active_envelope', lambda e,a,s,h: ({'version': 1, 'components': {'separation_sequencing': {'Δhip_torso_ms': [0, 200], 'Δtorso_hand_ms': [0, 200], 'chain_order_score_min': 0.0}, 'release_quality': {'release_angle_deg': [20, 60]}}}, False))
  res = calculate_pqs_v2(frames, 'right', None, event='discus', age_band='Open', sex='M')
  bf = res.get('metrics_band_fit')
  assert bf and set(['Δhip_torso_ms','Δtorso_hand_ms','chain_order_score']).issubset(bf.keys())

