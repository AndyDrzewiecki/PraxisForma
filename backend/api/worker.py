"""
Cloud Run worker receiving Pub/Sub push and running analysis.
"""

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Any, Dict
import json
import base64
import os
import uuid
import time

from google.cloud import storage, firestore

from backend.config import GCP_PROJECT, GCS_BUCKET, FIRESTORE_COLLECTION
# Lazy import inside handler to avoid circular deps during test collection


app = FastAPI()


class PubSubEnvelope(BaseModel):
    message: Dict[str, Any]
    subscription: str


app = FastAPI()

@app.post("/pubsub")
async def pubsub_push(envelope: PubSubEnvelope, request: Request):
    req_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        if "data" not in envelope.message:
            raise HTTPException(status_code=400, detail="Missing data field in Pub/Sub message")
        raw = envelope.message["data"]
        if isinstance(raw, str):
            # Some tests pass already-decoded JSON string
            decoded = json.loads(raw)
        else:
            decoded = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Pub/Sub message: {e}")

    user_id = decoded.get("userId")
    blurred_uri = decoded.get("blurred_uri")
    original_uri = decoded.get("original_uri")
    filename = decoded.get("filename")
    session_id = decoded.get("sessionId")
    if not all([user_id, blurred_uri, filename, session_id]):
        raise HTTPException(status_code=400, detail="Missing required fields in message")

    fs = firestore.Client(project=GCP_PROJECT)
    doc_ref = fs.collection(FIRESTORE_COLLECTION).document(session_id)
    try:
        # ANALYZING
        doc_ref.set({"status": {"state": "ANALYZING", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True)
        from backend.discus_analyzer_v2 import analyze_video
        with_coaching = bool(decoded.get("with_coaching", False))
        # Derive athlete context from Firestore session doc if present
        session_data = doc_ref.get().to_dict() or {}
        prof = session_data.get('athlete_profile') or {}
        event = prof.get('event') or 'discus'
        age_band = prof.get('ageBand') or 'Open'
        sex = prof.get('sex') or 'M'
        p_hand = prof.get('handedness') or 'right'
        pqs = analyze_video(blurred_uri, with_coaching=with_coaching, event_type=event)

        # Persist analysis
        doc_ref.set(
            {
                "userId": user_id,
                "original_uri": original_uri,
                "blurred_uri": blurred_uri,
                "created_at": firestore.SERVER_TIMESTAMP,
                "pqs": pqs["pqs"],
                "pqs_v2": pqs.get("pqs_v2"),
            },
            merge=True,
        )

        # Persist envelope version if provided via pqs_v2 (future: store from envelope_store)
        env_ver = (pqs.get('pqs_v2') or {}).get('envelope_version')
        if env_ver is not None:
            doc_ref.set({"envelope_version": env_ver}, merge=True)

        # Write JSON to GCS results/{userId}/{basename}.pqs.json
        bucket = storage.Client().bucket(GCS_BUCKET)
        basename = os.path.splitext(filename)[0]
        out_path = f"results/{user_id}/{basename}.pqs.json"
        blob = bucket.blob(out_path)
        blob.upload_from_string(json.dumps(pqs), content_type="application/json")

        # COACHING / OVERLAY stages
        if with_coaching:
            doc_ref.set({"status": {"state": "COACHING", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True)
        if with_coaching and decoded.get("with_overlay"):
            doc_ref.set({"status": {"state": "OVERLAY", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True)
            from backend.visual.overlay import render_coaching_video
            overlay_uri = f"gs://{GCS_BUCKET}/overlays/{user_id}/{basename}.overlay.mp4"
            ov = render_coaching_video(blurred_uri, pqs, overlay_uri)
            doc_ref.set({"assets": {"overlay_uri": ov.get("overlay_uri")}}, merge=True)
            sidecar = bucket.blob(f"results/{user_id}/{basename}.assets.json")
            sidecar.upload_from_string(json.dumps({"assets": {"overlay_uri": ov.get("overlay_uri")}}), content_type="application/json")

        # Export per-frame feature CSV
        try:
            from backend.pqs_algorithm import compute_features as _cf  # if available under this path
        except Exception:
            _cf = None
        try:
            if _cf is not None and "pqs_v2" in pqs:
                # No direct frames here anymore; rely on results JSON to drive features if available
                # For scope, write minimal CSV from pqs_v2 metrics with timestamp column placeholder
                csv_lines = ["timestamp_ms"]
                metrics = pqs.get("pqs_v2", {}).get("metrics", {}) or {}
                header_extra = sorted(metrics.keys())
                csv_lines[0:1] = ["timestamp_ms," + ",".join(header_extra)]
                # approximate rows by video duration
                total_ms = int(pqs.get("video", {}).get("duration_ms", 0) or 0)
                step = 33
                rows = []
                t = 0
                while t <= total_ms:
                    row = [str(t)] + [str(metrics.get(k, "")) for k in header_extra]
                    rows.append(",".join(row))
                    t += step
                contents = "\n".join([csv_lines[0]] + rows)
                csv_blob = bucket.blob(f"results/{user_id}/{basename}.features.csv")
                csv_blob.upload_from_string(contents, content_type="text/csv")
                doc_ref.set({"assets": {"features_csv_uri": f"gs://{GCS_BUCKET}/results/{user_id}/{basename}.features.csv"}}, merge=True)
        except Exception:
            pass

        # COMPLETE
        doc_ref.set({"status": {"state": "COMPLETE", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True)

        ms = int((time.perf_counter() - start) * 1000)
        print(f"request_id={req_id} session={session_id} analyzed in {ms}ms uri={blurred_uri}")
        return Response(status_code=204)
    except Exception as e:
        doc_ref.set({"status": {"state": "ERROR", "error": str(e), "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True)
        raise


