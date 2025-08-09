import json
import pytest
from httpx import AsyncClient

from api.main import app


@pytest.mark.asyncio
async def test_signed_url_rejects_without_token():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/signed-url", json={"gs_uri": "gs://praxisforma-videos/blurred/u1/f.mp4"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_signed_url_valid(monkeypatch):
    # Stub token verifier to return uid
    monkeypatch.setattr("api.auth.verify_bearer_token", lambda h: "u1")

    class _Blob:
        def generate_signed_url(self, expiration=None, method="GET"):
            return "https://signed/url"

    class _Bucket:
        def blob(self, name):
            return _Blob()

    class _Storage:
        def bucket(self, name):
            return _Bucket()

    monkeypatch.setattr("api.signed_url.storage.Client", lambda: _Storage())

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(
            "/signed-url",
            headers={"Authorization": "Bearer faketoken"},
            json={"gs_uri": "gs://praxisforma-videos/blurred/u1/f.mp4"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "url" in body and body["url"].startswith("https://")
        assert "expires_at" in body


@pytest.mark.asyncio
async def test_signed_url_rejects_wrong_path(monkeypatch):
    monkeypatch.setattr("api.auth.verify_bearer_token", lambda h: "u1")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(
            "/signed-url",
            headers={"Authorization": "Bearer faketoken"},
            json={"gs_uri": "gs://praxisforma-videos/incoming/u1/f.mp4"},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_signed_url_enforces_uid(monkeypatch):
    monkeypatch.setattr("api.auth.verify_bearer_token", lambda h: "u1")
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(
            "/signed-url",
            headers={"Authorization": "Bearer faketoken"},
            json={"gs_uri": "gs://praxisforma-videos/blurred/u2/f.mp4"},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_signed_url_overlays(monkeypatch):
    monkeypatch.setattr("api.auth.verify_bearer_token", lambda h: "u1")
    class _Blob:
        def generate_signed_url(self, expiration=None, method="GET"):
            return "https://signed/url"
    class _Bucket:
        def blob(self, name):
            return _Blob()
    class _Storage:
        def bucket(self, name):
            return _Bucket()
    monkeypatch.setattr("api.signed_url.storage.Client", lambda: _Storage())
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post(
            "/signed-url",
            headers={"Authorization": "Bearer faketoken"},
            json={"gs_uri": "gs://praxisforma-videos/overlays/u1/f.overlay.mp4"},
        )
        assert r.status_code == 200


async def test_signed_url_landmarks_and_results(monkeypatch):
    # Mock auth to return uid
    from backend.api import auth as _auth
    monkeypatch.setattr(_auth, 'verify_bearer_token', lambda h: 'u1')

    # Stub storage client
    class _Blob:
        def __init__(self, n): pass
        def generate_signed_url(self, **kwargs): return 'https://signed'
    class _Bucket:
        def blob(self, n): return _Blob(n)
    class _Storage:
        def bucket(self, n): return _Bucket()
    monkeypatch.setattr('backend.api.signed_url.storage.Client', lambda: _Storage())

    from fastapi.testclient import TestClient
    from backend.api.main import app
    c = TestClient(app)
    for uri in [
        f"gs://praxisforma-videos/landmarks/u1/x.landmarks.json",
        f"gs://praxisforma-videos/results/u1/x.features.csv",
    ]:
        r = c.post('/signed-url', headers={'Authorization':'Bearer t','Content-Type':'application/json'}, json={'gs_uri': uri})
        assert r.status_code == 200


