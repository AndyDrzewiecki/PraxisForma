"""
FastAPI service for ThrowPro (PraxisForma) local analysis.

Example curl:
- Health check:
  curl -s http://localhost:8080/healthz

- Analyze via GCS URI:
  curl -s -X POST http://localhost:8080/analyze \
    -H "Content-Type: application/json" \
    -d '{"video_uri":"gs://praxisforma-videos/sample.mp4"}'

- Analyze via multipart upload:
  curl -s -X POST http://localhost:8080/analyze \
    -F "video_file=@samples/throw.mp4"
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi import Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import tempfile
import os
import uuid
import time
import json

from backend.api.signed_url import router as signed_url_router
from backend.api.uploads import router as uploads_router
from backend.api.admin_compare import router as admin_compare_router
from backend.api.progress import router as progress_router
from backend.api.admin_envelopes import router as admin_envelopes_router
from backend.api.admin_envelopes import router as admin_envelopes_v2_router
from backend.config import GCS_BUCKET, FIRESTORE_COLLECTION
from google.cloud import firestore, storage
from backend.visual.overlay import render_coaching_video
from backend.api.auth import verify_bearer_token


class AnalyzeRequest(BaseModel):
    video_uri: str = Field(..., description="gs:// URI of the input video")


class PQSComponents(BaseModel):
    shoulder_alignment: int
    hip_rotation: int
    release_angle: int
    power_transfer: int
    footwork_timing: int


class PQSBlock(BaseModel):
    total: int
    components: PQSComponents
    deductions: int
    release_t_ms: Optional[int]
    handedness: str
    flags: List[str]
    notes: List[str]


class VideoMeta(BaseModel):
    name: str
    duration_ms: int


class PQSResponse(BaseModel):
    video: VideoMeta
    pqs: PQSBlock


app = FastAPI()


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/analyze", response_model=PQSResponse)
async def analyze(
    video_uri_body: Optional[AnalyzeRequest] = Body(default=None),
    video_file: Optional[UploadFile] = File(default=None),
    with_coaching: Optional[bool] = False,
):
    # Lazy import to avoid heavy imports during tests of unrelated endpoints
    from backend.discus_analyzer_v2 import analyze_video
    # Input validation: exactly one provided
    provided = int(video_uri_body is not None) + int(video_file is not None)
    if provided != 1:
        raise HTTPException(status_code=422, detail="Provide exactly one of video_uri or video_file")

    start = time.perf_counter()
    req_id = str(uuid.uuid4())

    if video_uri_body is not None:
        # Privacy gate: only landmarks-only or pre-blurred video allowed
        # For URI analyze, assume pipeline ensures blur; otherwise, instruct to use uploads flow
        result = analyze_video(video_uri_body.video_uri, with_coaching=bool(with_coaching))
        result["request_id"] = req_id
        result["duration_ms_server"] = int((time.perf_counter() - start) * 1000)
        return result

    # Multipart upload path
    assert video_file is not None
    suffix = os.path.splitext(video_file.filename or "upload.mp4")[1] or ".mp4"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        content = await video_file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        # Privacy gate: uploaded videos must be processed by blur pipeline before analyze; block direct raw analysis
        raise HTTPException(status_code=400, detail={"error": "privacy_gate", "how_to_fix": "Use the signed upload flow; analysis runs after face blurring completes."})
        result = analyze_video(tmp_path, with_coaching=bool(with_coaching))
        result["request_id"] = req_id
        result["duration_ms_server"] = int((time.perf_counter() - start) * 1000)
        return result
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


app.include_router(signed_url_router)
app.include_router(uploads_router)
app.include_router(admin_envelopes_router)
app.include_router(admin_envelopes_v2_router)
app.include_router(admin_compare_router)
app.include_router(progress_router)


@app.post("/sessions/{session_id}/overlay")
async def generate_overlay(session_id: str, authorization: Optional[str] = None):
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    fs = firestore.Client()
    doc_ref = fs.collection(FIRESTORE_COLLECTION).document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    data = doc.to_dict()
    if data.get("userId") != uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    blurred = data.get("blurred_uri")
    if not blurred:
        raise HTTPException(status_code=400, detail="No blurred_uri on session")
    basename = (data.get("filename") or blurred.split("/")[-1]).rsplit(".", 1)[0]
    out_uri = f"gs://{GCS_BUCKET}/overlays/{uid}/{basename}.overlay.mp4"
    result = render_coaching_video(blurred, {"pqs": data.get("pqs"), "pqs_v2": data.get("pqs_v2"), "coaching": data.get("coaching"), "assets": data.get("assets") or {}}, out_uri)
    doc_ref.set({"assets": {"overlay_uri": result.get("overlay_uri")}}, merge=True)
    # Sidecar
    bucket = storage.Client().bucket(GCS_BUCKET)
    sidecar = bucket.blob(f"results/{uid}/{basename}.assets.json")
    import json as _json
    sidecar.upload_from_string(_json.dumps({"assets": {"overlay_uri": result.get("overlay_uri")}}), content_type="application/json")
    return result


@app.get("/admin/me")
async def admin_me(authorization: Optional[str] = None):
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    fs = firestore.Client()
    is_admin = fs.collection('admins').document(uid).get().exists
    return {"isAdmin": bool(is_admin)}


@app.get("/sessions/{session_id}/features")
async def get_features(session_id: str, curves: Optional[str] = None, v: Optional[str] = None, authorization: Optional[str] = None):
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    fs = firestore.Client()
    doc_ref = fs.collection(FIRESTORE_COLLECTION).document(session_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Not found")
    data = snap.to_dict()
    # Ownership unless admin
    is_admin = fs.collection('admins').document(uid).get().exists
    if data.get('userId') != uid and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Privacy gate: must be blurred or landmarks-only
    if not (data.get('blurred_uri') or data.get('landmarks_only') is True):
        raise HTTPException(status_code=400, detail={"error": "privacy_gate", "how_to_fix": "Upload via /upload (auto-blur) or provide landmarks-only landmarks JSON."})

    # Versioning: default to v2 if v == '2'; otherwise keep legacy shape and log deprecation
    if v and v.strip() == '2':
        # Build curves payload similar to admin compare API
        pqs_v2 = data.get('pqs_v2') or {}
        series = pqs_v2.get('series') or {}
        t_ms = series.get('t_ms') or []
        want = set((curves or '').split(',')) if curves else set()
        out_curves: Dict[str, list] = {}
        if not want or 'separation' in want:
            sep = series.get('separation_deg') or []
            out_curves['separation'] = [{"t_ms": int(t_ms[i]), "deg": float(sep[i]) if i < len(sep) else None} for i in range(len(t_ms))]
        if 'ω_pelvis' in want:
            vser = series.get('ω_pelvis') or []
            out_curves['ω_pelvis'] = [{"t_ms": int(t_ms[i]), "deg_s": float(vser[i]) if i < len(vser) else None} for i in range(len(t_ms))]
        if 'ω_thorax' in want:
            vser = series.get('ω_thorax') or []
            out_curves['ω_thorax'] = [{"t_ms": int(t_ms[i]), "deg_s": float(vser[i]) if i < len(vser) else None} for i in range(len(t_ms))]
        if 'v_hand' in want or 'v_hand_norm' in want:
            vser = series.get('v_hand_norm') or []
            out_curves['v_hand'] = [{"t_ms": int(t_ms[i]), "norm": float(vser[i]) if i < len(vser) else None} for i in range(len(t_ms))]

        phases = pqs_v2.get('phases') or {}
        # Resolve envelope components live for shading
        try:
            from backend.biomech.envelope_store import load_active_envelope
            prof = data.get('athlete_profile') or {}
            event = (prof.get('event') or 'discus')
            age_band = (prof.get('ageBand') or 'Open')
            sex = (prof.get('sex') or 'M')
            hand = (prof.get('handedness') or data.get('pqs', {}).get('handedness') or 'right')
            env_obj, _ = load_active_envelope(event, age_band, sex, hand)
            envelope = (env_obj.get('components') or {})
            env_used = env_obj.get('version') or data.get('envelope_version')
        except Exception:
            envelope = {}
            env_used = data.get('envelope_version')
        metrics = pqs_v2.get('metrics') or {}
        band_fit = pqs_v2.get('metrics_band_fit') or {}
        return {
            "curves": out_curves,
            "phases": phases,
            "envelope": envelope,
            "metrics": {k: metrics.get(k) for k in ("Δhip_torso_ms","Δtorso_hand_ms","chain_order_score") if k in metrics},
            "metrics_band_fit": band_fit,
            "envelope_version": env_used,
        }

    # v1 fallback (deprecated)
    pqs_v2 = data.get('pqs_v2') or {}
    series = pqs_v2.get('series') or {}
    t_ms = series.get('t_ms') or []
    want = set((curves or '').split(',')) if curves else set()
    out_curves: Dict[str, list] = {}
    # separation
    if not want or 'separation' in want:
        sep = series.get('separation_deg') or []
        out_curves['separation'] = [{"t_ms": int(t_ms[i]), "deg": float(sep[i]) if i < len(sep) else None} for i in range(len(t_ms))]
    if 'ω_pelvis' in want:
        v = series.get('ω_pelvis') or []
        out_curves['ω_pelvis'] = [{"t_ms": int(t_ms[i]), "deg_s": float(v[i]) if i < len(v) else None} for i in range(len(t_ms))]
    if 'ω_thorax' in want:
        v = series.get('ω_thorax') or []
        out_curves['ω_thorax'] = [{"t_ms": int(t_ms[i]), "deg_s": float(v[i]) if i < len(v) else None} for i in range(len(t_ms))]
    if 'v_hand' in want or 'v_hand_norm' in want:
        v = series.get('v_hand_norm') or []
        out_curves['v_hand'] = [{"t_ms": int(t_ms[i]), "norm": float(v[i]) if i < len(v) else None} for i in range(len(t_ms))]

    phases = pqs_v2.get('phases') or {}
    envelope = (pqs_v2.get('envelope') or {})
    metrics = pqs_v2.get('metrics') or {}
    env_used = pqs_v2.get('envelope_version') or data.get('envelope_version')
    return {
        "separation": out_curves.get('separation') or [],
        "release_angle": [{"t_ms": int(data.get('pqs', {}).get('release_t_ms') or 0), "deg": float(metrics.get('release_angle_deg')) if metrics.get('release_angle_deg') is not None else None}],
        "phases": phases,
        "envelope_version": env_used,
    }


@app.post("/sessions/{session_id}/retry")
async def retry_processing(session_id: str, authorization: Optional[str] = None):
    from google.cloud import pubsub_v1
    from backend.config import GCP_PROJECT, PUBSUB_TOPIC

    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    fs = firestore.Client()
    doc_ref = fs.collection(FIRESTORE_COLLECTION).document(session_id)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    data = snap.to_dict()
    if data.get("userId") != uid:
        raise HTTPException(status_code=403, detail="Forbidden")

    blurred_uri = data.get("blurred_uri")
    original_uri = data.get("original_uri")
    filename = data.get("filename") or (original_uri.split("/")[-1] if original_uri else None)
    if not (blurred_uri and filename):
        raise HTTPException(status_code=400, detail="Session missing blurred_uri/filename")

    payload = {
        "sessionId": session_id,
        "userId": uid,
        "original_uri": original_uri,
        "blurred_uri": blurred_uri,
        "filename": filename,
        "with_coaching": True,
        "with_overlay": True,
    }
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT, PUBSUB_TOPIC)
    fut = publisher.publish(topic_path, json.dumps(payload).encode("utf-8"))
    fut.result(timeout=30)

    doc_ref.set({"status": {"state": "QUEUED", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True)
    return {"ok": True}

