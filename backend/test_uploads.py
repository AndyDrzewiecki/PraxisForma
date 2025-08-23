import json
import types
import uuid as _uuid

from fastapi.testclient import TestClient

from backend.api.main import app


def test_init_upload_requires_auth(monkeypatch):
    client = TestClient(app)
    r = client.post('/uploads/init', json={"filename": "x.mp4", "content_type": "video/mp4"})
    assert r.status_code == 401


def test_init_upload_valid(monkeypatch):
    # Stub auth
    from backend.api import auth as _auth
    monkeypatch.setattr(_auth, 'verify_bearer_token', lambda h: 'user123')

    # Stub storage
    class _Blob:
        def __init__(self, name): self.name = name
        def create_resumable_upload_session(self, content_type=None): return f"https://upload.fake/{self.name}"
    class _Bucket:
        def blob(self, name): return _Blob(name)
    class _Storage:
        def bucket(self, name): return _Bucket()
    monkeypatch.setattr('backend.api.uploads.storage.Client', lambda: _Storage())

    # Stub firestore
    class _Doc:
        def set(self, *args, **kwargs): pass
    class _FS:
        def collection(self, name):
            assert name == 'throwSessions'
            return types.SimpleNamespace(document=lambda _id: _Doc())
    monkeypatch.setattr('backend.api.uploads.firestore.Client', lambda: _FS())

    client = TestClient(app)
    r = client.post('/uploads/init', headers={'Authorization': 'Bearer token'}, json={"filename": "throw.mp4", "content_type": "video/mp4"})
    assert r.status_code == 200
    body = r.json()
    assert 'upload_url' in body and body['upload_url'].startswith('https://upload.fake/')
    assert body['gs_uri'].startswith('gs://')
    assert body['sessionId']


def test_init_upload_invalid_filename(monkeypatch):
    from backend.api import auth as _auth
    monkeypatch.setattr(_auth, 'verify_bearer_token', lambda h: 'user123')
    client = TestClient(app)
    r = client.post('/uploads/init', headers={'Authorization': 'Bearer token'}, json={"filename": "../../bad.mp4", "content_type": "video/mp4"})
    assert r.status_code == 400



