from fastapi.testclient import TestClient
from backend.api.main import app


def test_features_privacy_blocks(monkeypatch):
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
        def document(self, doc): return _DocRef({'userId': 'u1', 'pqs_v2': {'series': {'t_ms': []}}})
        def get(self): return _Doc({'exists': True})
    monkeypatch.setattr('backend.api.main.firestore', type('X', (), {'Client': lambda: _FS()}))
    r = client.get('/sessions/s1/features?v=2', headers={'Authorization': 'Bearer x'})
    assert r.status_code == 400
    assert r.json().get('error') == 'privacy_gate'


def test_progress_privacy_skips(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr('backend.api.auth.verify_bearer_token', lambda auth: 'u1')
    class _Doc: 
        def __init__(self, id, data): self.id=id; self._d=data
        def to_dict(self): return self._d
    class _Query:
        def where(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def start_after(self, *a, **k): return self
        def stream(self):
            return [ _Doc('s1', {'userId':'u1','created_at':None,'pqs_v2':{'metrics':{},'total':700}, 'landmarks_only': True}) ]
    class _FS:
        def collection(self, name): return _Query()
    monkeypatch.setattr('backend.api.progress.firestore', type('X', (), {'Client': lambda: _FS()}))
    r = client.get('/athletes/u1/progress', headers={'Authorization':'Bearer x'})
    assert r.status_code == 200
    assert len(r.json().get('items') or []) == 1


