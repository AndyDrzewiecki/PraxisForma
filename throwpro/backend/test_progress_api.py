from fastapi.testclient import TestClient
from backend.api.main import app
import pytest


def test_progress_shape(monkeypatch):
    client = TestClient(app)
    # stub auth
    monkeypatch.setattr('backend.api.auth.verify_bearer_token', lambda auth: 'u1')
    # stub firestore
    class _Doc:
        def __init__(self, id, data): self._id=id; self._data=data
        @property
        def id(self): return self._id
        def to_dict(self): return self._data
    class _Query:
        def __init__(self, docs): self._docs = docs
        def where(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def start_after(self, *a, **k): return self
        def stream(self):
            return [ _Doc('s1', {'userId':'u1','pqs_v2':{'total':700,'metrics':{'release_angle_deg':34,'chain_order_score':0.8,'v_hand_peak_norm':1.5}}}) ]
    class _FS:
        def collection(self, name): return _Query([])
    monkeypatch.setattr('backend.api.progress.firestore', type('X', (), {'Client': lambda: _FS()}))
    r = client.get('/athletes/u1/progress', headers={'Authorization':'Bearer x'})
    assert r.status_code == 200
    body = r.json()
    assert 'items' in body and isinstance(body['items'], list)
    assert {'id','total','release_angle_deg','chain_order_score','v_hand_peak_norm'}.issubset(body['items'][0].keys())

