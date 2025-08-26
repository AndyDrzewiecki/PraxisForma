import json
import pytest
from httpx import AsyncClient

from api.worker import app


@pytest.mark.asyncio
async def test_pubsub_push(monkeypatch):
    # Mock analyzer
    sample = {
        "video": {"name": "x.mp4", "duration_ms": 1000},
        "pqs": {
            "total": 600,
            "components": {
                "shoulder_alignment": 120,
                "hip_rotation": 120,
                "release_angle": 120,
                "power_transfer": 120,
                "footwork_timing": 120,
            },
            "deductions": 0,
            "release_t_ms": 500,
            "handedness": "right",
            "flags": [],
            "notes": [],
        },
    }

    def fake_analyze(uri: str):
        return json.loads(json.dumps(sample))

    monkeypatch.setattr("backend.discus_analyzer_v2.analyze_video", fake_analyze)

    # Mock Firestore and GCS clients
    class _FakeDoc:
        def set(self, data, merge=False):
            self.data = data

    class _FakeFS:
        def __init__(self, *args, **kwargs):
            pass
        def collection(self, name):
            return self
        def document(self, doc_id):
            return _FakeDoc()

    class _FakeBlob:
        def __init__(self, name):
            self.name = name
        def upload_from_string(self, s, content_type=None):
            self.payload = s

    class _FakeBucket:
        def blob(self, path):
            return _FakeBlob(path)

    class _FakeStorage:
        def __init__(self, *args, **kwargs):
            pass
        def bucket(self, name):
            return _FakeBucket()

    monkeypatch.setattr("api.worker.firestore.Client", lambda *a, **k: _FakeFS())
    monkeypatch.setattr("api.worker.storage.Client", lambda *a, **k: _FakeStorage())

    message = {
        "message": {
            "data": json.dumps({
                "userId": "u1",
                "original_uri": "gs://b/incoming/u1/s.mp4",
                "blurred_uri": "gs://b/blurred/u1/s.mp4",
                "filename": "s.mp4",
                "sessionId": "sess-1",
            }).encode("utf-8")
        },
        "subscription": "projects/x/subscriptions/y"
    }

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/pubsub", json=message)
        assert r.status_code == 204


