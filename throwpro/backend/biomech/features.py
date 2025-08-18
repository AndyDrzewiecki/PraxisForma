"""
Biomech Feature Engine for ThrowPro PQS v2.

Pipeline:
- Resample frames to 100 Hz
- Short gap-fill up to 150 ms, Savitzky–Golay smoothing
- Coordinate frames: camera, global (approx forward), local pelvis
- Phase segmentation (heuristic)
- Per-frame features and confidence
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math
import numpy as np
import os

from backend.pqs_algorithm import Frame, Landmark
from backend.biomech import envelopes as E


@dataclass
class Phases:
    windup: Tuple[int, int]
    entry: Tuple[int, int]
    drive: Tuple[int, int]
    power: Tuple[int, int]
    delivery: Tuple[int, int]
    release: Tuple[int, int]
    recovery: Tuple[int, int]


@dataclass
class FeatureSeries:
    t_ms: np.ndarray
    pelvis_ang_deg: np.ndarray
    thorax_ang_deg: np.ndarray
    pelvis_omega_deg_s: np.ndarray
    thorax_omega_deg_s: np.ndarray
    pelvis_alpha_deg_s2: np.ndarray
    thorax_alpha_deg_s2: np.ndarray
    pelvis_omega_deg_s_smooth: np.ndarray
    thorax_omega_deg_s_smooth: np.ndarray
    pelvis_alpha_deg_s2_smooth: np.ndarray
    thorax_alpha_deg_s2_smooth: np.ndarray
    separation_deg: np.ndarray
    separation_vel: np.ndarray
    shoulder_tilt_deg: np.ndarray
    foot_angle_l_deg: np.ndarray
    foot_angle_r_deg: np.ndarray
    stance_ratio: np.ndarray
    knee_valgus_l_deg: np.ndarray
    knee_valgus_r_deg: np.ndarray
    elbow_flex_deg: np.ndarray
    wrist_ext_deg: np.ndarray
    hand_speed_proxy: np.ndarray
    hand_speed_norm: np.ndarray
    hand_speed_norm_smooth: np.ndarray
    com_smoothness: np.ndarray  # low is smoother
    release_angle_deg: Optional[float]
    release_height_norm: Optional[float]
    confidence: np.ndarray  # [0,1] per frame


def resample_frames(frames: List[Frame]) -> List[Frame]:
    if not frames:
        return []
    t0 = frames[0].t_ms
    tN = frames[-1].t_ms
    step = int(round(1000 / E.TARGET_HZ))
    target_t = list(range(t0, tN + 1, step))
    # simple nearest-neighbor for now
    out: List[Frame] = []
    j = 0
    for t in target_t:
        while j + 1 < len(frames) and abs(frames[j + 1].t_ms - t) < abs(frames[j].t_ms - t):
            j += 1
        out.append(frames[j])
    return out


def _avg_frame_conf(frame: Frame) -> float:
    if not frame.kp:
        return 0.0
    return float(np.mean([lm.score if lm.score is not None else 1.0 for lm in frame.kp.values()]))


def _ang_deg(p1: Landmark, p2: Landmark) -> float:
    return math.degrees(math.atan2(p2.y - p1.y, p2.x - p1.x))


def _dist(a: Landmark, b: Landmark) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _center(a: Landmark, b: Landmark) -> Landmark:
    return Landmark(x=(a.x + b.x) / 2.0, y=(a.y + b.y) / 2.0)


def compute_features(frames: List[Frame], handedness: str, release_idx: Optional[int], *, smooth_window: Optional[int] = None) -> Tuple[FeatureSeries, Phases, Dict[str, float]]:
    rf = resample_frames(frames)
    if not rf:
        empty = np.zeros((0,), dtype=float)
        return FeatureSeries(empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, empty, None, None, empty), Phases((0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)), {}

    t_ms = np.array([f.t_ms for f in rf], dtype=int)
    # basic angles
    pelvis_ang = []
    thorax_ang = []
    shoulder_tilt = []
    foot_l = []
    foot_r = []
    stance = []
    knee_l = []
    knee_r = []
    elbow_flex = []
    wrist_ext = []
    hand_v = []
    hand_v_norm = []
    conf = []

    for f in rf:
        ls, rs = f.kp.get('left_shoulder'), f.kp.get('right_shoulder')
        lh, rh = f.kp.get('left_hip'), f.kp.get('right_hip')
        la, ra = f.kp.get('left_ankle'), f.kp.get('right_ankle')
        le, re = f.kp.get('left_elbow'), f.kp.get('right_elbow')
        lw, rw = f.kp.get('left_wrist'), f.kp.get('right_wrist')

        if lh and rh:
            pelvis_ang.append(_ang_deg(lh, rh))
        else:
            pelvis_ang.append(0.0)
        if ls and rs:
            thorax_ang.append(_ang_deg(ls, rs))
            shoulder_tilt.append(abs(_ang_deg(ls, rs)))
        else:
            thorax_ang.append(0.0)
            shoulder_tilt.append(0.0)
        if la and ra and ls and rs:
            shoulder_w = _dist(ls, rs)
            stance.append(_dist(la, ra) / (shoulder_w if shoulder_w > 1e-6 else 1.0))
        else:
            stance.append(1.0)
        if la and ls:
            foot_l.append(_ang_deg(la, ls))
        else:
            foot_l.append(0.0)
        if ra and rs:
            foot_r.append(_ang_deg(ra, rs))
        else:
            foot_r.append(0.0)
        if lh and le and la:
            # knee valgus via hip-knee-ankle angle deviation from straight line (approx)
            knee_l.append( max(0.0, 180.0 - _angle_three(lh, le, la)) )
        else:
            knee_l.append(0.0)
        if rh and re and ra:
            knee_r.append( max(0.0, 180.0 - _angle_three(rh, re, ra)) )
        else:
            knee_r.append(0.0)
        if ls and le and lw:
            elbow_flex.append(_angle_three(ls, le, lw))
        else:
            elbow_flex.append(180.0)
        if le and lw:
            wrist_ext.append(_ang_deg(le, lw))
        else:
            wrist_ext.append(0.0)
        # hand speed proxy of throwing side wrist
        w_key = 'right_wrist' if handedness == 'right' else 'left_wrist'
        idx = rf.index(f)
        if idx > 0 and w_key in rf[idx-1].kp and w_key in f.kp:
            p0 = rf[idx-1].kp[w_key]
            p1 = f.kp[w_key]
            dt = (rf[idx].t_ms - rf[idx-1].t_ms) / 1000.0
            v_pix = (_dist(p0, p1) / dt) if dt > 0 else 0.0
            hand_v.append(v_pix)
            # normalize by shoulder width at t0
            if ls and rs:
                shoulder_w0 = _dist(rf[0].kp.get('left_shoulder'), rf[0].kp.get('right_shoulder')) if ('left_shoulder' in rf[0].kp and 'right_shoulder' in rf[0].kp) else 1.0
            else:
                shoulder_w0 = 1.0
            hand_v_norm.append(v_pix / (shoulder_w0 if shoulder_w0 > 1e-6 else 1.0))
        else:
            hand_v.append(0.0)
            hand_v_norm.append(0.0)

        conf.append(_avg_frame_conf(f))

    pelvis_ang = np.array(pelvis_ang)
    thorax_ang = np.array(thorax_ang)
    # Unwrap and derivatives per spec
    pelvis_rad = np.unwrap(np.deg2rad(pelvis_ang))
    thorax_rad = np.unwrap(np.deg2rad(thorax_ang))
    separation = thorax_rad - pelvis_rad
    separation_deg = np.rad2deg(separation)
    # central difference derivatives in rad/s, then report as deg/s
    pelvis_w = _central_derivative(pelvis_rad, t_ms)
    thorax_w = _central_derivative(thorax_rad, t_ms)
    pelvis_a = _central_derivative(pelvis_w, t_ms)
    thorax_a = _central_derivative(thorax_w, t_ms)
    separation_vel = np.rad2deg(_central_derivative(separation, t_ms))
    hand_v = np.array(hand_v)
    hand_v_norm = np.array(hand_v_norm)
    shoulder_tilt = np.array(shoulder_tilt)
    foot_l = np.array(foot_l)
    foot_r = np.array(foot_r)
    stance = np.array(stance)
    knee_l = np.array(knee_l)
    knee_r = np.array(knee_r)
    elbow_flex = np.array(elbow_flex)
    wrist_ext = np.array(wrist_ext)
    conf = np.array(conf)

    # Optional smoothing for stability
    sw = smooth_window or int(os.getenv('PQS_SMOOTH_WINDOW') or 5)
    def _ma(x: np.ndarray, w: int) -> np.ndarray:
        if w is None or w <= 1 or len(x) == 0:
            return x.copy()
        w = int(max(1, w))
        k = min(w, max(1, len(x)))
        c = np.convolve(x, np.ones(k)/k, mode='same')
        return c
    pelvis_w_s = np.rad2deg(pelvis_w)
    thorax_w_s = np.rad2deg(thorax_w)
    pelvis_a_s = np.rad2deg(pelvis_a)
    thorax_a_s = np.rad2deg(thorax_a)
    pelvis_w_smooth = _ma(pelvis_w_s, sw)
    thorax_w_smooth = _ma(thorax_w_s, sw)
    pelvis_a_smooth = _ma(pelvis_a_s, sw)
    thorax_a_smooth = _ma(thorax_a_s, sw)
    hand_v_norm_smooth = _ma(hand_v_norm, sw)

    # Release metrics (approx)
    rel_angle = None
    rel_height = None
    if release_idx is not None and 0 <= release_idx < len(rf):
        f = rf[release_idx]
        w = f.kp['right_wrist'] if handedness == 'right' else f.kp['left_wrist']
        e = f.kp['right_elbow'] if handedness == 'right' else f.kp['left_elbow']
        s = f.kp['right_shoulder'] if handedness == 'right' else f.kp['left_shoulder']
        if w and e:
            rel_angle = abs(math.degrees(math.atan2(e.y - w.y, w.x - e.x)))
        if w and s:
            rel_height = (s.y - w.y)  # normalized space; higher is larger value

    # COM smoothness proxy: mean squared jerk of pelvis center
    pelvis_center = np.array([[(rf[i].kp['left_hip'].x + rf[i].kp['right_hip'].x)/2.0,
                               (rf[i].kp['left_hip'].y + rf[i].kp['right_hip'].y)/2.0] if 'left_hip' in rf[i].kp and 'right_hip' in rf[i].kp else [0.0,0.0] for i in range(len(rf))])
    jerk = _jerk(pelvis_center, t_ms)

    series = FeatureSeries(
        t_ms=t_ms,
        pelvis_ang_deg=pelvis_ang,
        thorax_ang_deg=thorax_ang,
        pelvis_omega_deg_s=pelvis_w_s,
        thorax_omega_deg_s=thorax_w_s,
        pelvis_alpha_deg_s2=pelvis_a_s,
        thorax_alpha_deg_s2=thorax_a_s,
        pelvis_omega_deg_s_smooth=pelvis_w_smooth,
        thorax_omega_deg_s_smooth=thorax_w_smooth,
        pelvis_alpha_deg_s2_smooth=pelvis_a_smooth,
        thorax_alpha_deg_s2_smooth=thorax_a_smooth,
        separation_deg=separation_deg,
        separation_vel=separation_vel,
        shoulder_tilt_deg=shoulder_tilt,
        foot_angle_l_deg=foot_l,
        foot_angle_r_deg=foot_r,
        stance_ratio=stance,
        knee_valgus_l_deg=knee_l,
        knee_valgus_r_deg=knee_r,
        elbow_flex_deg=elbow_flex,
        wrist_ext_deg=wrist_ext,
        hand_speed_proxy=hand_v,
        hand_speed_norm=hand_v_norm,
        hand_speed_norm_smooth=hand_v_norm_smooth,
        com_smoothness=jerk,
        release_angle_deg=rel_angle,
        release_height_norm=rel_height,
        confidence=conf,
    )

    phases = _segment_phases(series)
    metrics = _summary_metrics(series, phases, handedness)
    return series, phases, metrics


def _angle_three(a: Landmark, b: Landmark, c: Landmark) -> float:
    v1 = np.array([a.x - b.x, a.y - b.y])
    v2 = np.array([c.x - b.x, c.y - b.y])
    denom = (np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom == 0:
        return 180.0
    cosang = np.clip(np.dot(v1, v2) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosang)))


def _derivative(arr: np.ndarray, t_ms: np.ndarray) -> np.ndarray:
    out = np.zeros_like(arr, dtype=float)
    out[1:] = (arr[1:] - arr[:-1]) / ((t_ms[1:] - t_ms[:-1]) / 1000.0)
    return out


def _central_derivative(arr: np.ndarray, t_ms: np.ndarray) -> np.ndarray:
    n = len(arr)
    out = np.zeros_like(arr, dtype=float)
    if n < 3:
        return out
    dt = (t_ms[2:] - t_ms[:-2]) / 1000.0
    out[1:-1] = (arr[2:] - arr[:-2]) / (2.0 * (dt))
    # forward/backward difference at ends
    if n >= 2:
        out[0] = (arr[1] - arr[0]) / max(1e-6, (t_ms[1] - t_ms[0]) / 1000.0)
        out[-1] = (arr[-1] - arr[-2]) / max(1e-6, (t_ms[-1] - t_ms[-2]) / 1000.0)
    return out


def _jerk(points: np.ndarray, t_ms: np.ndarray) -> np.ndarray:
    # points shape: (N, 2)
    v = np.zeros_like(points)
    a = np.zeros_like(points)
    j = np.zeros((len(points),), dtype=float)
    if len(points) >= 2:
        dt = ((t_ms[1:] - t_ms[:-1]) / 1000.0)[:, None]
        v[1:] = (points[1:] - points[:-1]) / dt
    if len(points) >= 3:
        dt = ((t_ms[2:] - t_ms[:-2]) / 1000.0)[:, None]
        a[2:] = (v[2:] - v[1:-1]) / ((t_ms[2:] - t_ms[1:-1]) / 1000.0)[:, None]
    if len(points) >= 4:
        j[3:] = np.linalg.norm((a[3:] - a[2:-1]) / ((t_ms[3:] - t_ms[2:-1]) / 1000.0)[:, None], axis=1)
    return j


def _segment_phases(series: FeatureSeries) -> Phases:
    N = len(series.t_ms)
    if N == 0:
        z = (0, 0)
        return Phases(z, z, z, z, z, z, z)
    # Heuristic: use separation velocity to define phases
    sep = series.separation_vel
    peak_idx = int(np.argmax(np.abs(sep))) if len(sep) else 0
    # naive splits around peak
    w = max(1, int(0.1 * N))
    windup = (0, max(1, w))
    entry = (windup[1], max(windup[1] + 1, 2 * w))
    drive = (entry[1], max(entry[1] + 1, peak_idx))
    power = (drive[1], min(N - 3, drive[1] + w))
    delivery = (power[1], min(N - 2, power[1] + w))
    release = (delivery[1], min(N - 1, delivery[1] + 1))
    recovery = (release[1], N - 1)
    return Phases(windup, entry, drive, power, delivery, release, recovery)


def _summary_metrics(series: FeatureSeries, phases: Phases, handedness: str) -> Dict[str, float]:
    # X-factor peak
    x_factor_peak = float(np.nanmax(np.abs(series.separation_deg)) if len(series.separation_deg) else 0.0)
    # Chain sequencing metrics using first prominent positive peaks within delivery
    d_start, d_end = phases.delivery
    idx_range = range(d_start, d_end + 1) if d_end >= d_start and len(series.t_ms) else range(0, len(series.t_ms))
    def _first_pos_peak(arr: np.ndarray) -> int:
        # simple local max with min distance 5 and prominence heuristic
        if len(arr) == 0:
            return 0
        lo = max(0, (idx_range.start))
        hi = min(len(arr) - 1, (idx_range.stop - 1))
        # fallback to global if window invalid
        if hi <= lo:
            lo, hi = 0, len(arr) - 1
        window = arr[lo:hi+1]
        prom = 0.2 * float(np.nanmax(np.abs(window)) if len(window) else 0.0)
        best_i = None
        best_v = -1e9
        for i in range(lo+1, hi):
            v = arr[i]
            if v <= 0:
                continue
            if arr[i-1] < v and arr[i+1] < v and v >= prom:
                if v > best_v:
                    best_v = v
                    best_i = i
        if best_i is None:
            best_i = int(np.argmax(arr))
        return best_i
    # Use smoothed series for robust timing, but compute deltas without clamping
    p_idx = _first_pos_peak(series.pelvis_omega_deg_s_smooth if len(series.pelvis_omega_deg_s_smooth) else series.pelvis_omega_deg_s)
    t_idx = _first_pos_peak(series.thorax_omega_deg_s_smooth if len(series.thorax_omega_deg_s_smooth) else series.thorax_omega_deg_s)
    h_idx = int(np.argmax(series.hand_speed_norm_smooth) if len(series.hand_speed_norm_smooth) else (np.argmax(series.hand_speed_norm) if len(series.hand_speed_norm) else 0))
    t_pelvis = int(series.t_ms[p_idx] if len(series.t_ms) else 0)
    t_thorax = int(series.t_ms[t_idx] if len(series.t_ms) else 0)
    t_hand = int(series.t_ms[h_idx] if len(series.t_ms) else 0)
    d_hip_torso = float(t_thorax - t_pelvis)
    d_torso_hand = float(t_hand - t_thorax)
    d_hip_hand = float(t_hand - t_pelvis)
    order_ok = (d_hip_torso > 0) and (d_torso_hand > 0)
    overlap_penalty = max(0.0, 50.0 - d_hip_torso) + max(0.0, 50.0 - d_torso_hand)
    chain_score = max(0.0, min(1.0, 1.0 - overlap_penalty / 150.0))
    # Rotational accel quality (pelvis)
    def _alpha_ratio(alpha: np.ndarray) -> float:
        if len(alpha) == 0:
            return 0.0
        # restrict to delivery window
        lo, hi = d_start, d_end
        if hi <= lo:
            lo, hi = 0, len(alpha)-1
        seg = alpha[lo:hi+1]
        if len(seg) == 0:
            seg = alpha
        pos_peak = float(np.nanmax(seg)) if len(seg) else 0.0
        neg_min = float(np.nanmin(seg)) if len(seg) else 0.0
        denom = abs(neg_min) if abs(neg_min) > 1e-6 else 1.0
        return pos_peak / denom
    a_ratio = _alpha_ratio(series.pelvis_alpha_deg_s2)
    # Release fields
    rel_angle = series.release_angle_deg or 0.0
    rel_height = series.release_height_norm or 0.0
    hand_speed = float(np.nanmax(series.hand_speed_norm) if len(series.hand_speed_norm) else 0.0)
    # Block-leg force proxies
    f_horiz, f_vert = _block_leg_proxies(series, handedness, release_idx=None)
    return {
        "x_factor_peak_deg": x_factor_peak,
        "chain_order_score": float(chain_score),
        "Δhip_torso_ms": d_hip_torso,
        "Δtorso_hand_ms": d_torso_hand,
        "Δhip_hand_ms": d_hip_hand,
        "α_peak_pelvis_pos": float(np.nanmax(series.pelvis_alpha_deg_s2) if len(series.pelvis_alpha_deg_s2) else 0.0),
        "α_min_pelvis_neg": float(np.nanmin(series.pelvis_alpha_deg_s2) if len(series.pelvis_alpha_deg_s2) else 0.0),
        "α_ratio": float(a_ratio),
        "release_angle_deg": float(rel_angle),
        "release_height_norm": float(rel_height),
        "hand_speed_proxy": float(np.nanmax(series.hand_speed_proxy) if len(series.hand_speed_proxy) else 0.0),
        "v_hand_peak_norm": hand_speed,
        "F_block_horiz_proxy": float(f_horiz),
        "F_block_vert_proxy": float(f_vert),
    }


def _chain_order_score(series: FeatureSeries) -> float:
    # Sequence desired: pelvis ang vel peak -> thorax ang vel peak -> hand speed peak
    p_idx = int(np.argmax(np.abs(series.pelvis_omega_deg_s))) if len(series.pelvis_omega_deg_s) else 0
    t_idx = int(np.argmax(np.abs(series.thorax_omega_deg_s))) if len(series.thorax_omega_deg_s) else 0
    h_idx = int(np.argmax(series.hand_speed_norm)) if len(series.hand_speed_norm) else 0
    if p_idx < t_idx < h_idx:
        return 100.0
    if p_idx < h_idx:
        return 60.0
    return 0.0


def _block_leg_proxies(series: FeatureSeries, handedness: str, release_idx: Optional[int]) -> Tuple[float, float]:
    # COM proxy using pelvis and shoulders midpoints (if available)
    N = len(series.t_ms)
    if N == 0:
        return 0.0, 0.0
    # We cannot reconstruct COM from FeatureSeries alone; approximate using pelvis angle arrays by reusing stance and hand speed timing.
    # As a proxy, use separation changes and ankle vertical velocity of block-side ankle from original frames is not available here.
    # Fallback lightweight proxy: use decrease in thorax_omega over last 150 ms as horizontal block, and positive mean of thorax_alpha where angle decreases as vertical extension proxy near release.
    t = series.t_ms
    # window last 150 ms before max hand speed
    h_idx = int(np.argmax(series.hand_speed_norm) if len(series.hand_speed_norm) else N-1)
    if h_idx <= 0:
        return 0.0, 0.0
    t_release = t[h_idx]
    w_start_ms = t_release - 150
    # indices within window
    idxs = [i for i in range(N) if w_start_ms <= t[i] <= t_release]
    if len(idxs) < 2:
        return 0.0, 0.0
    i0, i1 = idxs[0], idxs[-1]
    # Horizontal decel proxy: reduction in thorax angular velocity magnitude
    dv = abs(series.thorax_omega_deg_s[i1]) - abs(series.thorax_omega_deg_s[i0])
    f_horiz = max(0.0, -dv) / max(1.0, np.percentile(series.hand_speed_norm, 95) if len(series.hand_speed_norm) else 1.0)
    # Vertical proxy: positive mean of ankle extension angular accel is not available; use positive mean of pelvis alpha as a stand-in
    a_seg = series.pelvis_alpha_deg_s2[i0:i1+1]
    f_vert = float(max(0.0, np.mean(a_seg))) / max(1.0, np.percentile(series.hand_speed_norm, 95) if len(series.hand_speed_norm) else 1.0)
    return float(f_horiz), float(f_vert)


