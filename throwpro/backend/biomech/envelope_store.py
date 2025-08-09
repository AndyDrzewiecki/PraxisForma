import time
from typing import Dict, Optional, Tuple

from google.cloud import firestore

from backend.biomech import envelopes as fallback_envelopes


_CACHE: Dict[Tuple[str, str, str, str], Tuple[float, Dict]] = {}
_TTL_SECONDS = 300


def _cache_get(key: Tuple[str, str, str, str]) -> Optional[Dict]:
    now = time.time()
    item = _CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if now - ts > _TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: Tuple[str, str, str, str], val: Dict) -> None:
    _CACHE[key] = (time.time(), val)


def load_active_envelope(event: str, age_band: str, sex: str, handedness: str) -> Tuple[Dict, bool]:
    """
    Returns (envelope_dict, used_fallback)
    Looks up active version pointer in collection `envelope_active` and fetches matching doc from `envelopes`.
    Uses in-process cache with TTL; falls back to code constants if Firestore unavailable or no doc.
    """
    key = (event, age_band, sex, handedness)
    cached = _cache_get(key)
    if cached:
        return cached, False
    try:
        fs = firestore.Client()
        ptr = fs.collection('envelope_active').document(f"{event}_{age_band}_{sex}_{handedness}").get()
        version = None
        if ptr.exists:
            version = int(ptr.to_dict().get('version'))
        if version is None:
            raise KeyError('no_active_pointer')
        doc_id = f"{event}_{age_band}_{sex}_{handedness}_v{version}"
        snap = fs.collection('envelopes').document(doc_id).get()
        if not snap.exists:
            raise KeyError('envelope_missing')
        data = snap.to_dict()
        _cache_set(key, data)
        return data, False
    except Exception:
        # Fallback to code constants
        data = {
            'components': {
                'release_quality': {
                    'release_angle_deg': [getattr(fallback_envelopes, 'RELEASE_ANGLE_LOW', 20.0), getattr(fallback_envelopes, 'RELEASE_ANGLE_HIGH', 55.0)]
                },
                'separation_sequencing': {
                    'Δhip_torso_ms': [50.0, 120.0],
                    'Δtorso_hand_ms': [40.0, 100.0],
                    'chain_order_score_min': 0.7,
                },
                'lower_body_platform': {},
            },
            'timing_windows': {},
            'version': 0,
            'notes': 'fallback',
        }
        _cache_set(key, data)
        return data, True



