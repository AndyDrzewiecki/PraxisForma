from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from google.cloud import storage

from backend.api.auth import verify_bearer_token
from backend.config import GCS_BUCKET


router = APIRouter()


class SignedUrlRequest(BaseModel):
    gs_uri: str


@router.post("/signed-url")
async def create_signed_url(req: SignedUrlRequest, authorization: Optional[str] = Header(default=None)):
    # AuthN
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid or missing ID token")

    # Validate URI: allow blurred/, overlays/, landmarks/, and results/*.csv
    allowed = (
        req.gs_uri.startswith(f"gs://{GCS_BUCKET}/blurred/") or
        req.gs_uri.startswith(f"gs://{GCS_BUCKET}/overlays/") or
        req.gs_uri.startswith(f"gs://{GCS_BUCKET}/landmarks/") or
        req.gs_uri.startswith(f"gs://{GCS_BUCKET}/results/")
    )
    if not allowed:
        raise HTTPException(status_code=400, detail="Only blurred, overlays, landmarks, or results URIs are allowed")

    # Enforce uid path match
    path = req.gs_uri.split(f"gs://{GCS_BUCKET}/", 1)[1]
    parts = path.split("/", 3)
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail="Malformed URI")
    _, user_id, _rest = parts[0], parts[1], parts[2]
    if user_id != uid:
        raise HTTPException(status_code=403, detail="Forbidden for this user")

    rel_path = path  # already without bucket
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(rel_path)
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    url = blob.generate_signed_url(expiration=expires, method="GET")
    return {"url": url, "expires_at": expires.isoformat()}


