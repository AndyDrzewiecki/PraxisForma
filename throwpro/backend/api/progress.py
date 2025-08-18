from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Header, Query
from google.cloud import firestore

from backend.api.auth import verify_bearer_token


router = APIRouter()


@router.get("/athletes/{athlete_id}/progress")
def get_progress(athlete_id: str, metrics: Optional[str] = Query(default=None), limit: int = Query(50), cursor: Optional[str] = Query(default=None), authorization: Optional[str] = Header(default=None)):
    uid = verify_bearer_token(authorization)
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if uid != athlete_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    fs = firestore.Client()
    col = fs.collection('throwSessions')
    q = col.where('userId', '==', athlete_id).order_by('created_at').limit(limit)
    if cursor:
        # naive cursor: use created_at iso string or doc id; for now, ignore if invalid
        try:
            snap = col.document(cursor).get()
            if snap.exists:
                q = q.start_after(snap)
        except Exception:
            pass
    docs = list(q.stream())
    items = []
    for d in docs:
        data = d.to_dict() or {}
        m = (data.get('pqs_v2') or {}).get('metrics') or {}
        # Privacy gate: must be blurred or landmarks-only
        if not (data.get('blurred_uri') or data.get('landmarks_only') is True):
            continue
        items.append({
            'id': d.id,
            'created_at': (data.get('created_at').isoformat() if hasattr(data.get('created_at'), 'isoformat') else None),
            'total': (data.get('pqs_v2') or {}).get('total'),
            'release_angle_deg': m.get('release_angle_deg'),
            'chain_order_score': m.get('chain_order_score'),
            'v_hand_peak_norm': m.get('v_hand_peak_norm'),
        })
    next_cursor = docs[-1].id if docs else None
    return { 'items': items, 'next_cursor': next_cursor }


