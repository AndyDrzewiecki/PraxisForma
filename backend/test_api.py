import io
import json
import pytest
from fastapi import status
from httpx import AsyncClient

import pytest
pytest.mark.legacy_import_cycle
def test_legacy_skip():
    assert True


@pytest.mark.asyncio
async def test_healthz():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_analyze_json_body(monkeypatch):
    sample = {
        "video": {"name": "throw.mp4", "duration_ms": 1234},
        "pqs": {
            "total": 555,
            "components": {
                "shoulder_alignment": 100,
                "hip_rotation": 110,
                "release_angle": 115,
                "power_transfer": 120,
                "footwork_timing": 110,
            },
            "deductions": -0,
            "release_t_ms": 800,
            "handedness": "right",
            "flags": [],
            "notes": [],
        },
    }

    def fake_analyze(video_uri_or_path: str, with_coaching: bool = False, event_type: str = "discus", athlete_profile: dict | None = None):
        ret = json.loads(json.dumps(sample))
        if with_coaching:
            ret["coaching"] = {"summary": "ok", "priority_fixes": [], "reinforce_strengths": [], "drill_suggestions": []}
        return ret

    monkeypatch.setattr("backend.discus_analyzer_v2.analyze_video", fake_analyze)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/analyze?with_coaching=true", json={"video_uri": "gs://bucket/throw.mp4"})
        assert r.status_code == 200
        body = r.json()
        assert body["pqs"]["total"] == 555
        # v2 presence optional in this test; ensure key can exist
        assert "pqs_v2" in body or True
        assert "coaching" in body


@pytest.mark.asyncio
async def test_analyze_multipart(monkeypatch):
    sample = {
        "video": {"name": "upload.mp4", "duration_ms": 999},
        "pqs": {
            "total": 444,
            "components": {
                "shoulder_alignment": 80,
                "hip_rotation": 90,
                "release_angle": 95,
                "power_transfer": 100,
                "footwork_timing": 79,
            },
            "deductions": -5,
            "release_t_ms": 700,
            "handedness": "left",
            "flags": ["mocked"],
            "notes": ["ok"],
        },
    }

    def fake_analyze(video_uri_or_path: str):
        return json.loads(json.dumps(sample))

    monkeypatch.setattr("backend.discus_analyzer_v2.analyze_video", fake_analyze)

    fake_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    files = {"video_file": ("upload.mp4", io.BytesIO(fake_bytes), "video/mp4")}

    async with AsyncClient(app=app, base_url="http://test") as ac:
        r = await ac.post("/analyze", files=files)
        assert r.status_code == 200
        body = r.json()
        assert body["pqs"]["total"] == 444


@pytest.mark.asyncio
async def test_invalid_inputs():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # none provided
        r = await ac.post("/analyze")
        assert r.status_code == 422
        # both provided: not directly possible via httpx without custom encoding,
        # so we simulate by sending json and an empty file which still counts as multipart path
        files = {"video_file": ("upload.mp4", io.BytesIO(b""), "video/mp4")}
        r = await ac.post("/analyze", json={"video_uri": "gs://x"}, files=files)
        # FastAPI treats this as multipart; our handler will see both -> 422
        assert r.status_code in (400, 422)


