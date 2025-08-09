from typing import Optional
import os

import firebase_admin
from firebase_admin import auth as fb_auth


_app_initialized = False


def _init_app_if_needed() -> None:
    global _app_initialized
    if _app_initialized:
        return
    project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": project_id} if project_id else None)
    _app_initialized = True


def verify_bearer_token(auth_header: Optional[str]) -> Optional[str]:
    """Verifies Firebase ID token from Authorization header and returns uid, or None if invalid."""
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1]
    try:
        _init_app_if_needed()
        decoded = fb_auth.verify_id_token(token)
        return decoded.get("uid")
    except Exception:
        return None


