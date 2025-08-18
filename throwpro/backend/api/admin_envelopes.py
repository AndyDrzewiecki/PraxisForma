from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel

from backend.api.auth import verify_bearer_token
from backend.biomech.envelope_store import resolve_envelope, upsert_envelope


router = APIRouter(prefix="/admin/envelopes2")


class EnvUpsert(BaseModel):
    level: str
    sex: str
    hand: str
    bands: Dict


@router.post("")
def post_envelope(env: EnvUpsert, authorization: Optional[str] = Header(default=None)):
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # In production, check admin claim; here assume upstream gate
    src = upsert_envelope(env.level, env.sex, env.hand, env.bands)
    return {"ok": True, "source": src}


@router.get("")
def get_envelope(level: str = Query('X'), sex: str = Query('X'), hand: str = Query('X'), authorization: Optional[str] = Header(default=None)):
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    bands, src = resolve_envelope(level, sex, hand)
    return {"bands": bands, "source": src}

from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from google.cloud import firestore

from backend.api.auth import verify_bearer_token


router = APIRouter(prefix="/admin/envelopes")


class EnvelopeModel(BaseModel):
    event: str
    ageBand: str
    sex: str
    handedness: str
    components: Dict
    timing_windows: Dict
    notes: Optional[str] = None


def _require_admin(authorization: Optional[str]) -> str:
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # In production, verify admin claim via Firebase Admin SDK; here, accept env flag or Firestore allowlist
    # For now, check a Firestore allowlist collection 'admins'
    fs = firestore.Client()
    if not fs.collection('admins').document(uid).get().exists:
        raise HTTPException(status_code=403, detail="Admin only")
    return uid


@router.get("/list")
def list_envelopes(event: str, ageBand: str, sex: str, handedness: str, authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    fs = firestore.Client()
    prefix = f"{event}_{ageBand}_{sex}_{handedness}_"
    docs = fs.collection('envelopes').where("event", "==", event).where("ageBand", "==", ageBand).where("sex", "==", sex).where("handedness", "==", handedness).stream()
    out = []
    for d in docs:
        x = d.to_dict()
        x['id'] = d.id
        out.append(x)
    return {"items": out}


@router.post("")
def create_or_update(env: EnvelopeModel, authorization: Optional[str] = Header(default=None)):
    uid = _require_admin(authorization)
    fs = firestore.Client()
    # Determine next version
    ptr_id = f"{env.event}_{env.ageBand}_{env.sex}_{env.handedness}"
    # Find max version
    existing = list(fs.collection('envelopes').where("event","==",env.event).where("ageBand","==",env.ageBand).where("sex","==",env.sex).where("handedness","==",env.handedness).stream())
    max_v = 0
    for d in existing:
        try:
            v = int((d.to_dict() or {}).get('version') or 0)
            max_v = max(max_v, v)
        except Exception:
            pass
    next_v = max_v + 1
    doc_id = f"{ptr_id}_v{next_v}"
    fs.collection('envelopes').document(doc_id).set({
        "event": env.event,
        "ageBand": env.ageBand,
        "sex": env.sex,
        "handedness": env.handedness,
        "version": next_v,
        "created_at": firestore.SERVER_TIMESTAMP,
        "author_uid": uid,
        "components": env.components,
        "timing_windows": env.timing_windows,
        "notes": env.notes or "",
        "is_active": False,
    })
    return {"id": doc_id, "version": next_v}


class ActivateRequest(BaseModel):
    event: str
    ageBand: str
    sex: str
    handedness: str
    version: int


@router.post("/activate")
def activate(req: ActivateRequest, authorization: Optional[str] = Header(default=None)):
    _require_admin(authorization)
    fs = firestore.Client()
    ptr_id = f"{req.event}_{req.ageBand}_{req.sex}_{req.handedness}"
    doc_id = f"{ptr_id}_v{req.version}"
    snap = fs.collection('envelopes').document(doc_id).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Envelope version not found")
    # Atomically set active pointer and mark is_active
    fs.collection('envelope_active').document(ptr_id).set({"version": req.version, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    fs.collection('envelopes').document(doc_id).set({"is_active": True}, merge=True)
    return {"ok": True}



