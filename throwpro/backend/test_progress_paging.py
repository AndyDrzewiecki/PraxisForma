from fastapi.testclient import TestClient
from backend.api.main import app


def test_progress_paging_cursor(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr('backend.api.auth.verify_bearer_token', lambda auth: 'u1')
    class _Doc:
        def __init__(self, id, data): self.id=id; self._d=data
        def to_dict(self): return self._d
    class _Query:
        def __init__(self, docs): self._docs=docs
        def where(self, *a, **k): return self
        def order_by(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def start_after(self, *a, **k): return self
        def stream(self): return self._docs
    class _FS:
        def collection(self, name):
            docs = [ _Doc('s1', {'userId':'u1','created_at':None,'pqs_v2':{'metrics':{},'total':700}, 'blurred_uri': 'gs://x'}) ]
            return _Query(docs)
    monkeypatch.setattr('backend.api.progress.firestore', type('X', (), {'Client': lambda: _FS()}))
    r = client.get('/athletes/u1/progress?limit=1', headers={'Authorization':'Bearer x'})
    assert r.status_code == 200
    body = r.json()
    assert body.get('items') and body.get('next_cursor') == 's1'


