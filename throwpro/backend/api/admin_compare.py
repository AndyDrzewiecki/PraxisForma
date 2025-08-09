from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Header
from google.cloud import firestore

from backend.api.auth import verify_bearer_token
from backend.biomech.envelope_store import load_active_envelope
from backend.config import FIRESTORE_COLLECTION


router = APIRouter(prefix="/admin")


@router.get("/compare")
def admin_compare(sessionId: str, curves: Optional[str] = None, authorization: Optional[str] = Header(default=None)):
    """Admin compare API returning curves, phases, envelope bands and key metrics."""
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    fs = firestore.Client()
    snap = fs.collection(FIRESTORE_COLLECTION).document(sessionId).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Session not found")
    data = snap.to_dict() or {}
    # Only admins allowed
    if not fs.collection('admins').document(uid).get().exists:
        raise HTTPException(status_code=403, detail="Admin only")

    pqs_v2 = data.get('pqs_v2') or {}
    ser = pqs_v2.get('series') or {}
    t_ms = ser.get('t_ms') or []
    want = set((curves or '').split(',')) if curves else set()
    out_curves: Dict[str, list] = {}
    if not want or 'separation' in want:
        sep = ser.get('separation_deg') or []
        out_curves['separation'] = [{"t_ms": int(t_ms[i]), "deg": float(sep[i]) if i < len(sep) else None} for i in range(len(t_ms))]
        # in_band flag for separation requires envelope band if available
    if 'ω_pelvis' in want:
        v = ser.get('ω_pelvis') or []
        out_curves['ω_pelvis'] = [{"t_ms": int(t_ms[i]), "deg_s": float(v[i]) if i < len(v) else None} for i in range(len(t_ms))]
    if 'ω_thorax' in want:
        v = ser.get('ω_thorax') or []
        out_curves['ω_thorax'] = [{"t_ms": int(t_ms[i]), "deg_s": float(v[i]) if i < len(v) else None} for i in range(len(t_ms))]
    if 'v_hand' in want or 'v_hand_norm' in want:
        v = ser.get('v_hand_norm') or []
        out_curves['v_hand'] = [{"t_ms": int(t_ms[i]), "norm": float(v[i]) if i < len(v) else None} for i in range(len(t_ms))]

    phases = pqs_v2.get('phases') or {}

    # Envelope bands used: compute live from athlete profile context
    prof = data.get('athlete_profile') or {}
    event = (prof.get('event') or 'discus')
    age_band = (prof.get('ageBand') or 'Open')
    sex = (prof.get('sex') or 'M')
    hand = (prof.get('handedness') or data.get('pqs', {}).get('handedness') or 'right')
    envelope, _ = load_active_envelope(event, age_band, sex, hand)
    comps = (envelope.get('components') or {})
    env_used = pqs_v2.get('envelope_version') or envelope.get('version')

    # Mark in_band for separation using band if present
    if 'separation' in out_curves:
        sep_band = (comps.get('separation_sequencing') or {}).get('separation_deg')  # optional future field
        # if not present, skip marking; else add boolean
        if isinstance(sep_band, list) and len(sep_band) == 2:
            lo, hi = float(sep_band[0]), float(sep_band[1])
            for pt in out_curves['separation']:
                val = pt.get('deg')
                if val is None:
                    pt['in_band'] = None
                else:
                    pt['in_band'] = (lo <= float(val) <= hi)

    metrics = pqs_v2.get('metrics') or {}
    return {
        "curves": out_curves,
        "phases": phases,
        "envelope": comps,
        "metrics": {k: metrics.get(k) for k in ("Δhip_torso_ms","Δtorso_hand_ms","chain_order_score") if k in metrics},
        "envelope_version": env_used,
    }


