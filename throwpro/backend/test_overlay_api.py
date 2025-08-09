import json
import pytest
from httpx import AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_overlay_endpoint_auth(monkeypatch):
    # Mock auth to return uid
    monkeypatch.setattr("api.auth.verify_bearer_token", lambda h: "u1")

    # Mock Firestore doc
    class _Doc:
        def __init__(self, data):
            self._data = data
        @property
        def exists(self):
            return True
        def to_dict(self):
            return self._data
        def set(self, *a, **k):
            pass

    class _FS:
        def collection(self, name):
            return self
        def document(self, id):
            return self
        def get(self):
            return _Doc({"userId": "u1", "blurred_uri": "gs://praxisforma-videos/blurred/u1/f.mp4", "pqs": {}, "pqs_v2": {}})
        def set(self, *a, **k):
            pass

    monkeypatch.setattr("api.main.firestore.Client", lambda *a, **k: _FS())

    class _Blob:
        def upload_from_string(self, *a, **k):
            pass
    class _Bucket:
        def blob(self, *a, **k):
            return _Blob()
    class _Storage:
        def bucket(self, *a, **k):
            return _Bucket()
    monkeypatch.setattr("api.main.storage.Client", lambda *a, **k: _Storage())

    # Mock renderer
    monkeypatch.setattr("api.main.render_coaching_video", lambda *a, **k: {"overlay_uri": "gs://praxisforma-videos/overlays/u1/f.overlay.mp4"})

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/sessions/abc/overlay", headers={"Authorization": "Bearer tok"})
        assert r.status_code == 200
        assert r.json()["overlay_uri"].endswith(".overlay.mp4")


