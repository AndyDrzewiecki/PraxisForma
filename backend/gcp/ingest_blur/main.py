"""
Cloud Function (2nd gen) entrypoint for GCS -> blur -> Pub/Sub orchestrate.
Trigger: GCS finalize on bucket GCS_BUCKET; process only paths under incoming/.
"""

import base64
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone

from google.cloud import storage, pubsub_v1, firestore

from backend.config import GCP_PROJECT, GCS_BUCKET, PUBSUB_TOPIC, FIRESTORE_COLLECTION
from backend.face_blur import blur_faces_in_video


def _publish_message(payload: dict) -> None:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GCP_PROJECT, PUBSUB_TOPIC)
    data = json.dumps(payload).encode("utf-8")
    future = publisher.publish(topic_path, data)
    future.result(timeout=30)


def gcs_entrypoint(event: dict, context) -> None:
    name = event.get("name") or ""
    bucket = event.get("bucket") or GCS_BUCKET
    if not name.startswith("incoming/"):
        return

    # Expect incoming/{userId}/{filename}
    parts = name.split("/", 2)
    if len(parts) < 3:
        return
    _, user_id, filename = parts

    # Optional session id prefix: <sessionId>__filename
    session_id = None
    if "__" in filename:
        maybe_session, rest = filename.split("__", 1)
        # Validate UUID-ish format length; if not, treat as regular filename
        if len(maybe_session) >= 8:
            session_id = maybe_session
            filename = rest

    request_id = str(uuid.uuid4())
    storage_client = storage.Client()
    src_bucket = storage_client.bucket(bucket)
    src_blob = src_bucket.blob(name)

    # Download to temp
    fd_in, tmp_in = tempfile.mkstemp(suffix=os.path.splitext(filename)[1] or ".mp4")
    os.close(fd_in)
    fd_out, tmp_out = tempfile.mkstemp(suffix=os.path.splitext(filename)[1] or ".mp4")
    os.close(fd_out)

    try:
        src_blob.download_to_filename(tmp_in)
        blur_faces_in_video(tmp_in, tmp_out)

        # Upload to blurred/{userId}/{filename}
        blurred_path = f"blurred/{user_id}/{filename}"
        dst_blob = src_bucket.blob(blurred_path)
        dst_blob.upload_from_filename(tmp_out, content_type=src_blob.content_type or "video/mp4")

        # Update status: BLURRING at start, then QUEUED after upload
        fs = firestore.Client()
        if session_id:
            fs.collection(FIRESTORE_COLLECTION).document(session_id).set(
                {"status": {"state": "BLURRING", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True
            )

        payload = {
            "userId": user_id,
            "original_uri": f"gs://{bucket}/{name}",
            "blurred_uri": f"gs://{bucket}/{blurred_path}",
            "filename": filename,
            "sessionId": session_id or str(uuid.uuid4()),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "with_coaching": True,
            "with_overlay": True,
        }
        _publish_message(payload)
        if session_id:
            fs.collection(FIRESTORE_COLLECTION).document(session_id).set(
                {"status": {"state": "QUEUED", "updated_at": firestore.SERVER_TIMESTAMP}}, merge=True
            )
        print(f"request_id={request_id} session={payload['sessionId']} user={user_id} queued")
    finally:
        try:
            os.remove(tmp_in)
        except Exception:
            pass
        try:
            os.remove(tmp_out)
        except Exception:
            pass


