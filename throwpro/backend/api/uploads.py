from typing import Optional
import re
import uuid

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from google.cloud import storage, firestore

from backend.api.auth import verify_bearer_token
from backend.config import GCS_BUCKET, FIRESTORE_COLLECTION


router = APIRouter()


_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class InitUploadRequest(BaseModel):
    filename: str = Field(..., description="Client filename, e.g. throw.mp4")
    content_type: str = Field(..., description="MIME type, e.g. video/mp4")


@router.post("/uploads/init")
async def init_resumable_upload(req: InitUploadRequest, authorization: Optional[str] = Header(default=None)):
    # AuthN
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or missing ID token")

    # Validate filename (no paths, no special chars)
    filename = (req.filename or "").strip()
    if not filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not _SAFE_FILENAME_RE.match(filename):
        raise HTTPException(status_code=400, detail="Filename contains invalid characters")

    # Generate a session id and object path; embed session id to correlate ingest trigger back to session
    session_id = str(uuid.uuid4())
    object_path = f"incoming/{uid}/{session_id}__{filename}"
    gs_uri = f"gs://{GCS_BUCKET}/{object_path}"

    # Create resumable upload session URL
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET)
        blob = bucket.blob(object_path)
        upload_url = blob.create_resumable_upload_session(content_type=req.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create upload session: {e}")

    # Upsert initial Firestore session document
    fs = firestore.Client()
    # Load athlete profile snapshot
    profile_snap = fs.collection('athleteProfiles').document(uid).get()
    profile = profile_snap.to_dict() if profile_snap.exists else None
    doc_ref = fs.collection(FIRESTORE_COLLECTION).document(session_id)
    doc_ref.set(
        {
            "userId": uid,
            "filename": filename,
            "original_uri": gs_uri,
            "athlete_profile": profile or {
                "event": "discus",
                "ageBand": "Open",
                "sex": "M",
                "handedness": "right",
            },
            "status": {
                "state": "UPLOADING",
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            "created_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    return {"upload_url": upload_url, "gs_uri": gs_uri, "sessionId": session_id}


