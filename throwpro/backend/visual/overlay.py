import os
import tempfile
from typing import Dict, List
import cv2
import numpy as np
from google.cloud import storage

from backend.visual.constants import (
    FONT_SCALE, FONT_THICKNESS, LINE_THICKNESS,
    COLOR_TEXT, COLOR_BANNER, COLOR_SKELETON, COLOR_RELEASE,
    COLOR_BAR_BG, COLOR_BAR_FG, PADDING, ENDCARD_SECS,
    TARGET_WIDTH, TARGET_HEIGHT, SKELETON_EDGES,
)
from backend.visual.geom import arc_points


def _download(gs_uri: str) -> str:
    assert gs_uri.startswith("gs://")
    _, rest = gs_uri.split("gs://", 1)
    bucket_name, blob_name = rest.split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    fd, path = tempfile.mkstemp(suffix=os.path.splitext(blob_name)[1] or ".mp4")
    os.close(fd)
    blob.download_to_filename(path)
    return path


def _upload(local: str, out_gs_uri: str) -> None:
    assert out_gs_uri.startswith("gs://")
    _, rest = out_gs_uri.split("gs://", 1)
    bucket_name, blob_name = rest.split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local, content_type="video/mp4")


def _draw_banner(frame: np.ndarray, text: str):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 40), COLOR_BANNER, -1)
    cv2.putText(frame, text, (PADDING, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_TEXT, 2, cv2.LINE_AA)


def _draw_skeleton(frame: np.ndarray, kps: Dict[str, Dict[str, float]]):
    h, w = frame.shape[:2]
    def xy(n):
        if n not in kps:
            return None
        return int(kps[n]['x'] * w), int(kps[n]['y'] * h)
    for a, b in SKELETON_EDGES:
        pa, pb = xy(a), xy(b)
        if pa and pb:
            cv2.line(frame, pa, pb, COLOR_SKELETON, LINE_THICKNESS, cv2.LINE_AA)

def _load_landmarks(gs_uri: str) -> List[Dict]:
    # Accept compressed JSON uploaded as content_type application/json
    assert gs_uri.startswith("gs://")
    _, rest = gs_uri.split("gs://", 1)
    bucket_name, blob_name = rest.split("/", 1)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    data = blob.download_as_bytes()
    try:
        import gzip, json as _json
        frames = _json.loads(gzip.decompress(data).decode('utf-8'))
    except Exception:
        import json as _json
        frames = _json.loads(data.decode('utf-8'))
    return frames


def _draw_release_arc(frame: np.ndarray, center: tuple[int,int], angle_deg: float):
    radius = 80
    pts = arc_points(center[0], center[1], radius, 0, angle_deg)
    for i in range(1, len(pts)):
        cv2.line(frame, pts[i-1], pts[i], COLOR_RELEASE, 2, cv2.LINE_AA)
    cv2.putText(frame, f"{angle_deg:.0f}°", (center[0]+radius+8, center[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_RELEASE, 2, cv2.LINE_AA)


def _draw_endcard(frame: np.ndarray, pqs_v2: Dict, coaching: Dict|None):
    h, w = frame.shape[:2]
    y = h//4
    cv2.putText(frame, f"PQS v2: {pqs_v2.get('total', 0)}", (w//6, y), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255,255,255), 3, cv2.LINE_AA)
    comps = pqs_v2.get('components', {})
    labels = [
        ("Platform", comps.get('lower_body_platform', 0)),
        ("Separation", comps.get('separation_sequencing', 0)),
        ("Kinetics", comps.get('arm_implement_kinetics', 0)),
        ("Release", comps.get('release_quality', 0)),
        ("Smooth", comps.get('smoothness_control', 0)),
    ]
    bar_w = w//2
    x0 = w//6
    y0 = y + 40
    for i, (lab, val) in enumerate(labels):
        yy = y0 + i*28
        cv2.rectangle(frame, (x0, yy), (x0+bar_w, yy+18), COLOR_BAR_BG, -1)
        fill = int(bar_w * min(1.0, max(0.0, val/200.0)))
        cv2.rectangle(frame, (x0, yy), (x0+fill, yy+18), COLOR_BAR_FG, -1)
        cv2.putText(frame, f"{lab}", (x0-90, yy+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230,230,230), 1, cv2.LINE_AA)

    if coaching and coaching.get('priority_fixes'):
        fixes = coaching['priority_fixes'][:2]
        yy = y0 + len(labels)*28 + 20
        cv2.putText(frame, "Priority Fixes:", (x0, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
        for i, f in enumerate(fixes):
            cv2.putText(frame, f"[{f.get('phase')}] {f.get('tip')}", (x0, yy+22*(i+1)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1, cv2.LINE_AA)


def render_coaching_video(gs_uri: str, analysis: Dict, out_gs_uri: str) -> Dict:
    src = _download(gs_uri)
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    in_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    in_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    scale = min(TARGET_WIDTH / max(1, in_w), TARGET_HEIGHT / max(1, in_h))
    w = int(in_w * scale)
    h = int(in_h * scale)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fd_out, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd_out)
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

    pqs_v2 = analysis.get('pqs_v2', {})
    coaching = analysis.get('coaching')
    phases = pqs_v2.get('phases', {})
    rel_t = analysis.get('pqs', {}).get('release_t_ms')
    phase_labels = [
        ('windup', 'Windup'), ('entry','Entry'), ('drive','Drive'),
        ('power','Power'), ('delivery','Delivery'), ('release','Release'), ('recovery','Recovery')
    ]

    # Precompute phase ranges
    phase_ranges = {}
    for k,_ in phase_labels:
        rng = phases.get(k)
        if isinstance(rng, list) and len(rng) == 2:
            phase_ranges[k] = (int(rng[0]), int(rng[1]))

    t0 = analysis.get('video', {}).get('duration_ms', 0)
    # Load landmarks if provided in analysis assets
    landmarks_frames = []
    lm_uri = (analysis.get('assets') or {}).get('landmarks_uri')
    if lm_uri:
        try:
            landmarks_frames = _load_landmarks(lm_uri)
        except Exception:
            landmarks_frames = []

    # Render frames
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.resize(frame, (w, h))

        # Draw skeleton for this frame if landmarks available
        if landmarks_frames:
            ms_per_frame = int(1000.0 / fps)
            cur_ms = idx * ms_per_frame
            # find nearest landmarks by timestamp
            # assume frames are sorted
            # simple nearest search
            nearest = None
            if 0 <= idx < len(landmarks_frames):
                nearest = landmarks_frames[idx]
            else:
                # fallback: find by timestamp
                best_dt = 10**9
                for rec in landmarks_frames:
                    dt = abs(rec.get('timestamp_ms', 0) - cur_ms)
                    if dt < best_dt:
                        best_dt = dt
                        nearest = rec
            if nearest and isinstance(nearest.get('landmarks'), list):
                # map into dict with canonical names if counts match; otherwise, draw connecting sequential points
                # We don't have names here; draw edges only when we have 17 points in order nose..ankles
                pts = nearest['landmarks']
                if len(pts) >= 17:
                    kps = {
                        'nose': {'x': pts[0]['x'], 'y': pts[0]['y']},
                        'left_eye': {'x': pts[1]['x'], 'y': pts[1]['y']},
                        'right_eye': {'x': pts[2]['x'], 'y': pts[2]['y']},
                        'left_ear': {'x': pts[3]['x'], 'y': pts[3]['y']},
                        'right_ear': {'x': pts[4]['x'], 'y': pts[4]['y']},
                        'left_shoulder': {'x': pts[5]['x'], 'y': pts[5]['y']},
                        'right_shoulder': {'x': pts[6]['x'], 'y': pts[6]['y']},
                        'left_elbow': {'x': pts[7]['x'], 'y': pts[7]['y']},
                        'right_elbow': {'x': pts[8]['x'], 'y': pts[8]['y']},
                        'left_wrist': {'x': pts[9]['x'], 'y': pts[9]['y']},
                        'right_wrist': {'x': pts[10]['x'], 'y': pts[10]['y']},
                        'left_hip': {'x': pts[11]['x'], 'y': pts[11]['y']},
                        'right_hip': {'x': pts[12]['x'], 'y': pts[12]['y']},
                        'left_knee': {'x': pts[13]['x'], 'y': pts[13]['y']},
                        'right_knee': {'x': pts[14]['x'], 'y': pts[14]['y']},
                        'left_ankle': {'x': pts[15]['x'], 'y': pts[15]['y']},
                        'right_ankle': {'x': pts[16]['x'], 'y': pts[16]['y']},
                    }
                    _draw_skeleton(frame, kps)

        # Phase banner using timestamp approximation by index
        # If release_t_ms known, estimate ms per frame
        ms_per_frame = int(1000.0 / fps)
        cur_ms = idx * ms_per_frame
        active = None
        for key, _lab in phase_labels:
            if key in phase_ranges:
                lo, hi = phase_ranges[key]
                if lo <= cur_ms <= hi:
                    active = _lab
                    break
        if active:
            _draw_banner(frame, active)

        # Freeze near release to draw arc
        if rel_t is not None and abs(cur_ms - int(rel_t)) <= 40:
            # Draw angle if available
            ang = pqs_v2.get('metrics', {}).get('release_angle_deg')
            if isinstance(ang, (float, int)):
                center = (w//2, h//2)
                _draw_release_arc(frame, center, float(ang))
            # duplicate few frames to simulate pause
            for _ in range(int(fps * 0.3)):
                writer.write(frame.copy())

        writer.write(frame)
        idx += 1

    # End card frames
    end_frames = int(fps * ENDCARD_SECS)
    end = np.zeros((h, w, 3), dtype=np.uint8)
    _draw_endcard(end, pqs_v2, coaching)
    for _ in range(end_frames):
        writer.write(end)

    cap.release()
    writer.release()

    _upload(out_path, out_gs_uri)
    try:
        os.remove(out_path)
        os.remove(src)
    except Exception:
        pass
    return {"overlay_uri": out_gs_uri, "duration_ms": int(idx * (1000.0 / fps) + ENDCARD_SECS*1000), "width": w, "height": h}


