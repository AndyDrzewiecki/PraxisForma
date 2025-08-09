from fastapi.testclient import TestClient
from backend.api.main import app


def test_admin_envelopes_flow(monkeypatch):
    # Stub auth
    from backend.api import auth as _auth
    monkeypatch.setattr(_auth, 'verify_bearer_token', lambda h: 'admin1')
    # Stub admins allowlist
    class _Doc:
        def __init__(self, exists=True, data=None, id=''): self._exists=exists; self._data=data or {}; self.id=id
        def get(self): return self
        @property
        def exists(self): return self._exists
        def to_dict(self): return self._data
        def set(self, *args, **kwargs): pass
    class _Col:
        def __init__(self, name): self.name=name
        def document(self, id): return _Doc(id=id)
        def where(self, *args, **kwargs): return self
        def stream(self): return []
    class _FS:
        def collection(self, name): return _Col(name)
    monkeypatch.setattr('backend.api.admin_envelopes.firestore.Client', lambda: _FS())

    c = TestClient(app)
    # Create draft
    r = c.post('/admin/envelopes', headers={'Authorization':'Bearer t'}, json={
        'event':'discus','ageBand':'Open','sex':'M','handedness':'right','components':{},'timing_windows':{}
    })
    assert r.status_code == 200
    # Activate
    r = c.post('/admin/envelopes/activate', headers={'Authorization':'Bearer t'}, json={
        'event':'discus','ageBand':'Open','sex':'M','handedness':'right','version':1
    })
    assert r.status_code == 200


