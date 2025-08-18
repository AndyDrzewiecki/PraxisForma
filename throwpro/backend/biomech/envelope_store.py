import time
from typing import Dict, Optional, Tuple
import json
import os
from google.cloud import storage

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


# -------- Envelope v2 JSON store with hierarchical fallback ----------

def _env_path_local(level: str, sex: str, hand: str) -> str:
    base = os.path.join(os.path.dirname(__file__), 'envelopes')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"envelope_{level}_{sex}_{hand}.json")


def _read_json_local(path: str) -> Optional[Dict]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _write_json_local(path: str, data: Dict) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def _read_json_gcs(bucket_name: str, blob_path: str) -> Optional[Dict]:
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        if not blob.exists():
            return None
        content = blob.download_as_text()
        return json.loads(content)
    except Exception:
        return None


def _write_json_gcs(bucket_name: str, blob_path: str, data: Dict) -> None:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(json.dumps(data, indent=2), content_type='application/json')


def resolve_envelope(level: str, sex: str, hand: str) -> Tuple[Dict, str]:
    """Resolve envelope bands with hierarchical fallback.
    Order: exact (level,sex,hand) → ignore hand → ignore sex → ignore level → built-in fallback.
    Returns (bands, source) where source is one of 'gcs','local','fallback'.
    """
    use_gcs = os.getenv('ENVELOPES_USE_GCS', 'false').lower() == 'true'
    bucket = os.getenv('GCS_BUCKET')
    keys = [
        (level, sex, hand),
        (level, sex, 'X'),
        (level, 'X', hand),
        ('X', sex, hand),
        ('X', 'X', 'X'),
    ]
    for lv, sx, hd in keys:
        filename = f"envelopes/envelope_{lv}_{sx}_{hd}.json"
        if use_gcs and bucket:
            data = _read_json_gcs(bucket, filename)
            if data:
                return data, 'gcs'
        path = _env_path_local(lv, sx, hd)
        data = _read_json_local(path)
        if data:
            return data, 'local'
    # fallback
    return {
        'release_quality': {
            'release_angle_deg': [getattr(fallback_envelopes, 'RELEASE_ANGLE_LOW', 20.0), getattr(fallback_envelopes, 'RELEASE_ANGLE_HIGH', 55.0)]
        },
        'separation_sequencing': {
            'Δhip_torso_ms': [50.0, 120.0],
            'Δtorso_hand_ms': [40.0, 100.0],
            'chain_order_score_min': 0.7,
        }
    }, 'fallback'


def upsert_envelope(level: str, sex: str, hand: str, bands: Dict) -> str:
    """Persist bands to local JSON and optionally mirror to GCS. Returns source written."""
    source = 'local'
    path = _env_path_local(level, sex, hand)
    _write_json_local(path, bands)
    if os.getenv('ENVELOPES_USE_GCS', 'false').lower() == 'true' and os.getenv('GCS_BUCKET'):
        _write_json_gcs(os.getenv('GCS_BUCKET'), f"envelopes/envelope_{level}_{sex}_{hand}.json", bands)
        source = 'gcs'
    return source



