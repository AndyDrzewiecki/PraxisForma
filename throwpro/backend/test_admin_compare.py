import pytest
from backend.api.main import app
from fastapi.testclient import TestClient


def test_compare_features_shape(monkeypatch):
    client = TestClient(app)
    # Stub auth
    monkeypatch.setattr('backend.api.auth.verify_bearer_token', lambda auth: 'u1')
    # Stub Firestore
    class _Doc:
        def __init__(self, data): self._data = data
        @property
        def exists(self): return True
        def to_dict(self): return self._data
    class _DocRef:
        def __init__(self, data): self._data = data
        def get(self): return _Doc(self._data)
    class _FS:
        def __init__(self, data): self._data = data
        def collection(self, name):
            return self
        def document(self, _id):
            return _DocRef(self._data)
        @property
        def exists(self): return True
    series = {
        't_ms': [0,10,20],
        'separation_deg': [0,1,2],
        'ω_pelvis': [0,2,1],
        'ω_thorax': [0,1,3],
        'v_hand_norm': [0,0.5,1.0],
    }
    pqs_v2 = {
        'series': series,
        'phases': { 'delivery': [0,20] },
        'metrics': { 'Δhip_torso_ms': 60, 'Δtorso_hand_ms': 50, 'chain_order_score': 0.8 },
        'envelope_version': 'discus_U20_M_right_v3',
    }
    data = { 'userId': 'u1', 'pqs_v2': pqs_v2 }
    monkeypatch.setattr('backend.api.main.firestore', type('X', (), {'Client': lambda: _FS(data)}))

    r = client.get('/sessions/s123/features?curves=separation,ω_pelvis,ω_thorax,v_hand', headers={'Authorization': 'Bearer x'})
    assert r.status_code == 200
    body = r.json()
    assert 'curves' in body and 'phases' in body and 'metrics' in body
    assert 'separation' in body['curves'] and 'ω_pelvis' in body['curves'] and 'v_hand' in body['curves']


