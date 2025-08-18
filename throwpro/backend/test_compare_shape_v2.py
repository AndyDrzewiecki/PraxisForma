from fastapi.testclient import TestClient
from backend.api.main import app


def test_features_v2_shape_includes_band_fit(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr('backend.api.auth.verify_bearer_token', lambda auth: 'u1')
    class _Doc:
        def __init__(self, data): self._d=data
        @property
        def exists(self): return True
        def to_dict(self): return self._d
    class _DocRef:
        def __init__(self, data): self._d=data
        def get(self): return _Doc(self._d)
    class _FS:
        def collection(self, name): return self
        def document(self, _id):
            return _DocRef({'userId':'u1','pqs_v2':{'series':{'t_ms':[0,10]},'phases':{},'metrics':{'Δhip_torso_ms':60,'Δtorso_hand_ms':50,'chain_order_score':0.8},'metrics_band_fit':{'Δhip_torso_ms':'inside'}}, 'blurred_uri':'gs://x'})
    monkeypatch.setattr('backend.api.main.firestore', type('X', (), {'Client': lambda: _FS()}))
    r = client.get('/sessions/abc/features?v=2&curves=separation,ω_pelvis,v_hand', headers={'Authorization':'Bearer x'})
    assert r.status_code == 200
    body = r.json()
    assert 'metrics_band_fit' in body and 'curves' in body and 'phases' in body


