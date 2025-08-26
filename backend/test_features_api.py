from fastapi.testclient import TestClient
from backend.api.main import app


def test_features_owner_or_admin(monkeypatch):
    # Stub auth uid
    from backend.api import auth as _auth
    monkeypatch.setattr(_auth, 'verify_bearer_token', lambda h: 'u1')

    # FS stub with session doc
    class _Doc:
        def __init__(self, data): self._data=data
        def get(self): return self
        @property
        def exists(self): return True
        def to_dict(self): return self._data
    class _Col:
        def __init__(self, name): self.name=name
        def document(self, id):
            if self.name=='throwSessions':
                return _Doc({ 'userId':'u1', 'pqs': {'release_t_ms': 100}, 'pqs_v2': {'series': {'t_ms':[0, 50, 100]}, 'metrics': {'release_angle_deg': 37.5}}, 'envelope_version': 1 })
            if self.name=='admins':
                return _Doc({}) if id=='u1' and False else _Doc(None)
            return _Doc(None)
    class _FS:
        def collection(self, name): return _Col(name)
    monkeypatch.setattr('backend.api.main.firestore.Client', lambda: _FS())

    c = TestClient(app)
    r = c.get('/sessions/abc/features', headers={'Authorization':'Bearer t'})
    assert r.status_code == 200
    body = r.json()
    assert 'separation' in body and 'release_angle' in body




