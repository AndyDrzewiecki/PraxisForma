from __future__ import annotations

"""
PraxisForma PQS v1 (Discus)

Assumptions/Conventions:
- Landmarks follow Google Video Intelligence 17-point set, mapped to names:
  'nose','left_eye','right_eye','left_ear','right_ear','left_shoulder','right_shoulder',
  'left_elbow','right_elbow','left_wrist','right_wrist','left_hip','right_hip','left_knee',
  'right_knee','left_ankle','right_ankle'.
- Coordinates are normalized to [0,1] image space with origin at top-left.
- Time is in milliseconds (t_ms).
- Release angle target for discus is 30–40 degrees. We approximate release angle using
  forearm orientation at detected release (elbow→wrist vector vs horizontal).
- Confidence gating: In a ±200 ms window around release, compute the minimum average
  landmark confidence across frames. If this minimum is below 0.7, multiply all component
  scores by (min_avg_conf / 0.7), clamped to [0.0, 1.0]. If confidences are missing,
  assume 1.0 (no reduction).
- Each component returns 0–200 pts; total before deductions is 1000; deductions are ≤ 0.

Heuristics are used for phase detection and event timing; these are explicitly marked
and should be refined with data.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math
from backend.biomech.features import compute_features
from backend.biomech import envelopes as E
from backend.biomech.envelope_store import load_active_envelope


# ----------------------------- Data Models -----------------------------


@dataclass
class Landmark:
    x: float
    y: float
    z: Optional[float] = None
    score: float = 1.0


@dataclass
class Frame:
    t_ms: int
    kp: Dict[str, Landmark]  # keys like 'left_shoulder', 'right_wrist', etc.


@dataclass
class PQSBreakdown:
    total: int
    shoulder_alignment: int
    hip_rotation: int
    release_angle: int
    power_transfer: int
    footwork_timing: int
    deductions: int
    release_t_ms: Optional[int]
    handedness: str  # 'left' | 'right'
    flags: List[str]
    notes: List[str]


# ----------------------------- Public API ------------------------------


def calculate_pqs(frames: List[Frame]) -> PQSBreakdown:
    """
    Minimal PQS scaffold focusing on release detection first.
    Returns zeros for component scores until full scorers are added.
    """
    if not frames:
        return PQSBreakdown(
            total=0,
            shoulder_alignment=0,
            hip_rotation=0,
            release_angle=0,
            power_transfer=0,
            footwork_timing=0,
            deductions=0,
            release_t_ms=None,
            handedness="right",
            flags=["no_frames"],
            notes=["No frames provided"],
        )

    handedness = detect_handedness(frames)
    rel_idx = detect_release_idx(frames, handedness)
    flags: List[str] = []
    notes: List[str] = []

    if rel_idx is None:
        flags.append("release_not_found")
        notes.append("Could not confidently detect release. Try clearer video and full throw.")

    # Component scores (0–200 each)
    shoulder_alignment, notes_sa = score_shoulder_alignment(frames, rel_idx, handedness)
    hip_rotation, notes_hr = score_hip_rotation(frames, rel_idx, handedness)
    release_angle, notes_ra = score_release_angle(frames, rel_idx, handedness)
    power_transfer, notes_pt = score_power_transfer(frames, rel_idx, handedness)
    footwork_timing, notes_ft = score_footwork_timing(frames, rel_idx, handedness)

    # Confidence gating
    gate = confidence_gate(frames, rel_idx, window_ms=200)
    shoulder_alignment = int(round(shoulder_alignment * gate))
    hip_rotation = int(round(hip_rotation * gate))
    release_angle = int(round(release_angle * gate))
    power_transfer = int(round(power_transfer * gate))
    footwork_timing = int(round(footwork_timing * gate))

    deductions, ded_flags, ded_notes = score_deductions(frames, rel_idx, handedness)

    total = max(0, shoulder_alignment + hip_rotation + release_angle + power_transfer + footwork_timing + deductions)

    return PQSBreakdown(
        total=total,
        shoulder_alignment=shoulder_alignment,
        hip_rotation=hip_rotation,
        release_angle=release_angle,
        power_transfer=power_transfer,
        footwork_timing=footwork_timing,
        deductions=deductions,
        release_t_ms=(frames[rel_idx].t_ms if rel_idx is not None else None),
        handedness=handedness,
        flags=flags + ded_flags,
        notes=notes + notes_sa + notes_hr + notes_ra + notes_pt + notes_ft + ded_notes,
    )


def calculate_pqs_v2(frames: List[Frame], handedness: str, rel_idx: Optional[int], *, event: str = 'discus', age_band: str = 'Open', sex: str = 'M') -> Dict[str, object]:
    series, phases, metrics = compute_features(frames, handedness, rel_idx)
    # Confidence score: mean over series
    conf = float(sum(series.confidence) / len(series.confidence)) if len(series.confidence) else 0.0
    attenuation = min(1.0, max(0.0, conf))

    # Component scoring (0–200 each)
    # Lower body platform: stance stability and foot angles variance
    stance_var = float((series.stance_ratio.std() if len(series.stance_ratio) else 1.0))
    lbp = max(0, 200 - int(stance_var * 200))

    # Separation & sequencing: x-factor magnitude + timing deltas + order score
    x_peak = float(metrics.get("x_factor_peak_deg", 0.0))
    d_ht = float(metrics.get("Δhip_torso_ms", 0.0))
    d_th = float(metrics.get("Δtorso_hand_ms", 0.0))
    seq_score01 = float(metrics.get("chain_order_score", 0.0))  # 0..1

    # Arm/implement kinetics: peak normalized hand speed
    hand_peak_norm = float(metrics.get("v_hand_peak_norm", 0.0) or metrics.get("hand_speed_proxy", 0.0))
    aik = int(min(200, (min(hand_peak_norm, 3.0) / 3.0) * 200))

    # Release quality: use envelope band if available
    envelope, used_fallback = load_active_envelope(event, age_band, sex, handedness)
    r_angle = float(metrics.get("release_angle_deg", 0.0))
    band = (((envelope.get('components') or {}).get('release_quality') or {}).get('release_angle_deg'))
    low, high = (E.RELEASE_ANGLE_LOW, E.RELEASE_ANGLE_HIGH)
    ideal, tol = (E.RELEASE_ANGLE_IDEAL, E.RELEASE_ANGLE_TOL)
    if isinstance(band, list) and len(band) == 2:
        low, high = float(band[0]), float(band[1])
        ideal = (low + high) / 2.0
        tol = max(1.0, (high - low) / 6.0)
    r_score = _triangular(r_angle, ideal=ideal, tol=tol,
                          zero_at_low=low, zero_at_high=high, max_points=160)
    h_norm = metrics.get("release_height_norm", 0.0)
    h_score = int(min(40, max(0, 40 * (h_norm + 0.5))))  # heuristic
    relq = int(min(200, r_score + h_score))

    # Smoothness/control: jerk penalties (lower jerk -> higher score)
    jerk_mean = float(series.com_smoothness.mean() if len(series.com_smoothness) else 1.0)
    # Smoothness/control + accel/brake bonus
    smc_base = max(0, 200 - int(min(200, jerk_mean * 20)))
    a_ratio = float(metrics.get('α_ratio', 0.0))
    a_bonus = int(min(40, max(0.0, (a_ratio - 1.0) * 20.0)))
    smc = int(min(200, smc_base + a_bonus))

    # Separation/Sequencing score composition with envelope timing bands
    sep_cfg = ((envelope.get('components') or {}).get('separation_sequencing') or {})
    dht_band = sep_cfg.get('Δhip_torso_ms') or [50.0, 120.0]
    dth_band = sep_cfg.get('Δtorso_hand_ms') or [40.0, 100.0]
    seq_min = float(sep_cfg.get('chain_order_score_min') or 0.7)
    def _band_score(x: float, band: List[float], tol_frac: float = 0.2, max_points: int = 100) -> int:
        lo, hi = float(band[0]), float(band[1])
        ideal_local = (lo + hi) / 2.0
        tol_local = max(1.0, (hi - lo) * tol_frac)
        return _triangular(x, ideal_local, tol_local, lo, hi, max_points)
    s_x = int(min(120, (min(x_peak, 60.0) / 60.0) * 120))
    s_ht = int(_band_score(d_ht, dht_band, 0.3, 50))
    s_th = int(_band_score(d_th, dth_band, 0.3, 50))
    s_order = int(min(40, max(0, 40 * ((seq_score01 - seq_min) / max(1e-6, (1.0 - seq_min))))))
    sep_seq = int(min(200, s_x + s_ht + s_th + s_order))

    # Apply attenuation
    comps = {
        "lower_body_platform": int(round(lbp * attenuation)),
        "separation_sequencing": int(round(sep_seq * attenuation)),
        "arm_implement_kinetics": int(round(aik * attenuation)),
        "release_quality": int(round(relq * attenuation)),
        "smoothness_control": int(round(smc * attenuation)),
    }
    total = int(sum(comps.values()))

    phases_obj = {
        "windup": [int(series.t_ms[phases.windup[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.windup[1]] if len(series.t_ms) else 0)],
        "entry": [int(series.t_ms[phases.entry[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.entry[1]] if len(series.t_ms) else 0)],
        "drive": [int(series.t_ms[phases.drive[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.drive[1]] if len(series.t_ms) else 0)],
        "power": [int(series.t_ms[phases.power[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.power[1]] if len(series.t_ms) else 0)],
        "delivery": [int(series.t_ms[phases.delivery[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.delivery[1]] if len(series.t_ms) else 0)],
        "release": [int(series.t_ms[phases.release[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.release[1]] if len(series.t_ms) else 0)],
        "recovery": [int(series.t_ms[phases.recovery[0]] if len(series.t_ms) else 0), int(series.t_ms[phases.recovery[1]] if len(series.t_ms) else 0)],
    }

    out = {
        "version": "2.0",
        "total": total,
        "components": comps,
        "confidence": round(attenuation, 3),
        "phases": phases_obj,
        "metrics": {
            "x_factor_peak_deg": float(metrics.get("x_factor_peak_deg", 0.0)),
            "chain_order_score": float(metrics.get("chain_order_score", 0.0)),
            "Δhip_torso_ms": float(metrics.get("Δhip_torso_ms", 0.0)),
            "Δtorso_hand_ms": float(metrics.get("Δtorso_hand_ms", 0.0)),
            "α_peak_pelvis_pos": float(metrics.get("α_peak_pelvis_pos", 0.0)),
            "α_min_pelvis_neg": float(metrics.get("α_min_pelvis_neg", 0.0)),
            "α_ratio": float(metrics.get("α_ratio", 0.0)),
            "release_angle_deg": float(metrics.get("release_angle_deg", 0.0)),
            "release_height_norm": float(metrics.get("release_height_norm", 0.0)),
            "hand_speed_proxy": float(metrics.get("hand_speed_proxy", 0.0)),
            "v_hand_peak_norm": float(metrics.get("v_hand_peak_norm", 0.0)),
            "F_block_horiz_proxy": float(metrics.get("F_block_horiz_proxy", 0.0)),
            "F_block_vert_proxy": float(metrics.get("F_block_vert_proxy", 0.0)),
        },
    }
    if 'version' in envelope:
        out['envelope_version'] = envelope.get('version')
    # Expose series for compare UI
    out['series'] = {
        "t_ms": [int(t) for t in list(series.t_ms)],
        "separation_deg": [float(v) for v in list(series.separation_deg)],
        "ω_pelvis": [float(v) for v in list(series.pelvis_omega_deg_s)],
        "ω_thorax": [float(v) for v in list(series.thorax_omega_deg_s)],
        "v_hand_norm": [float(v) for v in list(series.hand_speed_norm)],
    }
    if 'used_fallback' in locals() and used_fallback:
        out.setdefault('flags', []).append('envelope_fallback')
    return out


# ----------------------------- Core Logic ------------------------------


def detect_handedness(frames: List[Frame]) -> str:
    """
    Detect throwing side by comparing wrist peak speeds across the motion.
    Returns 'right' or 'left'. If ambiguous, default to 'right'.
    """
    right_v = _speed_series(frames, "right_wrist")
    left_v = _speed_series(frames, "left_wrist")

    if not right_v and not left_v:
        return "right"

    right_peak = max(right_v) if right_v else 0.0
    left_peak = max(left_v) if left_v else 0.0

    # Require a minimal separation to switch to left
    if left_peak > right_peak * 1.15:
        return "left"
    return "right"


def detect_release_idx(frames: List[Frame], handedness: str) -> Optional[int]:
    """
    Release detection:
    - Peak wrist speed near when the wrist is at/above shoulder height
    - Forearm (shoulder-elbow-wrist) extension >= 150 deg preferred
    Fallback: global wrist speed peak
    """
    wrist_key = f"{handedness}_wrist"
    shoulder_key = f"{handedness}_shoulder"
    elbow_key = f"{handedness}_elbow"

    v = _speed_series(frames, wrist_key)
    if not v:
        return None

    # Candidate: global speed peak
    peak_idx = int(max(range(len(v)), key=lambda i: v[i]))

    # Check criteria around the peak within a small neighborhood
    neighborhood = _indices_window(peak_idx, len(frames), radius=2)
    best_idx = None
    best_score = -1.0
    for i in neighborhood:
        f = frames[i]
        if wrist_key not in f.kp or shoulder_key not in f.kp or elbow_key not in f.kp:
            continue
        wrist = f.kp[wrist_key]
        shoulder = f.kp[shoulder_key]
        elbow = f.kp[elbow_key]

        # In image coords, lower y means higher on screen; consider wrist higher than shoulder
        wrist_above_shoulder = wrist.y <= shoulder.y
        extension = _joint_angle_deg(shoulder, elbow, wrist)
        extension_good = extension >= 150.0

        # Soft score combining speed rank and biomech checks
        score = v[i]
        if wrist_above_shoulder:
            score *= 1.1
        if extension_good:
            score *= 1.1

        if score > best_score:
            best_score = score
            best_idx = i

    return best_idx if best_idx is not None else peak_idx


# ----------------------------- Scoring utils ---------------------------


def _tilt_deg(frame: Frame, left_key: str, right_key: str) -> Optional[float]:
    if left_key not in frame.kp or right_key not in frame.kp:
        return None
    left = frame.kp[left_key]
    right = frame.kp[right_key]
    dx = right.x - left.x
    dy = right.y - left.y
    if dx == 0:
        return 90.0
    return abs(math.degrees(math.atan2(dy, dx)))


def _triangular(x: float, ideal: float, tol: float, zero_at_low: float, zero_at_high: float, max_points: int) -> int:
    if x <= zero_at_low or x >= zero_at_high:
        return 0
    if abs(x - ideal) <= tol:
        return max_points
    if x < ideal:
        return int(max_points * (x - zero_at_low) / (ideal - zero_at_low))
    return int(max_points * (zero_at_high - x) / (zero_at_high - ideal))


def _bell(x: float, center: float, width: float, max_points: int) -> float:
    # Gaussian-like bell; width ~ stddev
    if width <= 0:
        return 0.0
    return max_points * math.exp(-0.5 * ((x - center) / width) ** 2)


# ----------------------------- Kinematic utils -------------------------


def _speed_series(frames: List[Frame], key: str) -> List[float]:
    if not frames or key not in frames[0].kp:
        # Attempt to scan to find first occurrence; speeds for missing will be zeros
        found_any = any(key in f.kp for f in frames)
        if not found_any:
            return []
    speeds: List[float] = [0.0] * len(frames)
    for i in range(1, len(frames)):
        f0, f1 = frames[i - 1], frames[i]
        if key not in f0.kp or key not in f1.kp:
            speeds[i] = speeds[i - 1]
            continue
        p0 = f0.kp[key]
        p1 = f1.kp[key]
        dt = max(1, f1.t_ms - f0.t_ms)  # avoid div by zero; milliseconds
        dx = p1.x - p0.x
        dy = p1.y - p0.y
        speeds[i] = math.hypot(dx, dy) * 1000.0 / dt  # units: norm units per second
    return speeds


def _joint_angle_deg(a: Landmark, b: Landmark, c: Landmark) -> float:
    # angle at point b, between vectors ba and bc
    v1x, v1y = a.x - b.x, a.y - b.y
    v2x, v2y = c.x - b.x, c.y - b.y
    dot = v1x * v2x + v1y * v2y
    m1 = math.hypot(v1x, v1y)
    m2 = math.hypot(v2x, v2y)
    if m1 == 0 or m2 == 0:
        return 0.0
    cos_ang = max(-1.0, min(1.0, dot / (m1 * m2)))
    return math.degrees(math.acos(cos_ang))


def _indices_window(center_idx: int, n: int, radius: int) -> List[int]:
    start = max(0, center_idx - radius)
    end = min(n - 1, center_idx + radius)
    return list(range(start, end + 1))


# ----------------------------- Convenience -----------------------------


def make_landmark(x: float, y: float, score: float = 1.0) -> Landmark:
    return Landmark(x=x, y=y, score=score)


def make_frame(t_ms: int, points: Dict[str, Tuple[float, float]]) -> Frame:
    kp = {name: Landmark(x=xy[0], y=xy[1], score=1.0) for name, xy in points.items()}
    return Frame(t_ms=t_ms, kp=kp)


# -------------------------- Additional Helpers -------------------------


def _axis_angle_series(frames: List[Frame], axis: str) -> List[Optional[float]]:
    """Angle in degrees of left→right axis ('hip' or 'shoulder')."""
    if axis not in ("hip", "shoulder"):
        raise ValueError("axis must be 'hip' or 'shoulder'")
    left_key = f"left_{axis if axis != 'shoulder' else 'shoulder'}"
    right_key = f"right_{axis if axis != 'shoulder' else 'shoulder'}"
    ang: List[Optional[float]] = []
    for f in frames:
        if left_key in f.kp and right_key in f.kp:
            left = f.kp[left_key]
            right = f.kp[right_key]
            dx = right.x - left.x
            dy = right.y - left.y
            if dx == 0 and dy == 0:
                ang.append(0.0)
            else:
                ang.append(math.degrees(math.atan2(dy, dx)))
        else:
            ang.append(None)
    return ang


def _series_fill_forward(values: List[Optional[float]]) -> List[float]:
    filled: List[float] = []
    last = 0.0
    for v in values:
        if v is None:
            filled.append(last)
        else:
            filled.append(v)
            last = v
    return filled


def _derivative(series: List[Optional[float]], frames: List[Frame]) -> List[float]:
    vals = _series_fill_forward(series)
    der = [0.0] * len(vals)
    for i in range(1, len(vals)):
        dt = max(1, frames[i].t_ms - frames[i - 1].t_ms) / 1000.0
        der[i] = (vals[i] - vals[i - 1]) / dt
    return der


def _peak_idx(series: List[float]) -> int:
    # peak by absolute magnitude
    if not series:
        return 0
    return int(max(range(len(series)), key=lambda i: abs(series[i])))


def _stance_width_score(frame: Frame, max_points: int) -> int:
    """Score stance width using ankle-to-ankle vs shoulder-to-shoulder distance ratio."""
    required = ["left_ankle", "right_ankle", "left_shoulder", "right_shoulder"]
    if not all(k in frame.kp for k in required):
        return 0
    la, ra = frame.kp["left_ankle"], frame.kp["right_ankle"]
    ls, rs = frame.kp["left_shoulder"], frame.kp["right_shoulder"]
    ankle_dist = math.hypot(ra.x - la.x, ra.y - la.y)
    shoulder_dist = max(1e-6, math.hypot(rs.x - ls.x, rs.y - ls.y))
    ratio = ankle_dist / shoulder_dist
    # Ideal stance ~ 1.0 (ankles roughly shoulder width), tolerance broad for camera perspective
    return _triangular(ratio, ideal=1.0, tol=0.2, zero_at_low=0.5, zero_at_high=1.8, max_points=max_points)


def _trunk_lean_deg(frame: Frame) -> float:
    required = ["left_hip", "right_hip", "left_shoulder", "right_shoulder"]
    if not all(k in frame.kp for k in required):
        return 0.0
    hip_mid = Landmark(x=(frame.kp["left_hip"].x + frame.kp["right_hip"].x) / 2.0,
                       y=(frame.kp["left_hip"].y + frame.kp["right_hip"].y) / 2.0)
    sh_mid = Landmark(x=(frame.kp["left_shoulder"].x + frame.kp["right_shoulder"].x) / 2.0,
                      y=(frame.kp["left_shoulder"].y + frame.kp["right_shoulder"].y) / 2.0)
    dx = sh_mid.x - hip_mid.x
    dy = sh_mid.y - hip_mid.y
    # Angle from vertical
    if dy == 0 and dx == 0:
        return 0.0
    ang = abs(math.degrees(math.atan2(dx, dy)))  # swap to measure vs vertical
    return ang


def _knee_valgus_deg(frame: Frame, side: str) -> float:
    key_knee = f"{side}_knee"
    key_hip = f"{side}_hip"
    key_ankle = f"{side}_ankle"
    if not all(k in frame.kp for k in (key_knee, key_hip, key_ankle)):
        return 0.0
    ang = _joint_angle_deg(frame.kp[key_hip], frame.kp[key_knee], frame.kp[key_ankle])
    # Valgus heuristic: deviation from straight (~180°). Larger deviation → more valgus.
    return max(0.0, 180.0 - ang)


def _avg_conf(frames: List[Frame], rel_idx: Optional[int], window_ms: int) -> float:
    if rel_idx is None or not frames:
        return 1.0
    rel_t = frames[rel_idx].t_ms
    total = 0.0
    count = 0
    for f in frames:
        if abs(f.t_ms - rel_t) <= window_ms:
            # average landmark scores in this frame
            if f.kp:
                for lm in f.kp.values():
                    total += (lm.score if lm.score is not None else 1.0)
                    count += 1
    return (total / count) if count > 0 else 1.0


def confidence_gate(frames: List[Frame], rel_idx: Optional[int], window_ms: int = 200) -> float:
    min_avg = _avg_conf(frames, rel_idx, window_ms)
    if min_avg >= 0.7:
        return 1.0
    return max(0.0, min(1.0, min_avg / 0.7))


# ------------------------------ Scorers --------------------------------


def score_shoulder_alignment(frames: List[Frame], rel_idx: Optional[int], handedness: str) -> Tuple[int, List[str]]:
    # Rotation phase window: -600 ms to release
    if rel_idx is None:
        return 0, ["No release detected for shoulder alignment scoring"]
    rel_t = frames[rel_idx].t_ms
    window = [f for f in frames if rel_t - 600 <= f.t_ms <= rel_t]
    tilts = []
    for f in window:
        t = _tilt_deg(f, "left_shoulder", "right_shoulder")
        if t is not None:
            tilts.append(abs(t))
    if not tilts:
        return 0, ["Insufficient shoulder landmarks"]
    p50 = sorted(tilts)[len(tilts) // 2]
    # Map: ideal <=5°, ok to 10°, zero at 20°
    score = _score_with_plateau(value=p50, ideal=5, ok=10, max_bad=20, max_points=200, lower_is_better=True)
    notes = ["Great shoulder level through the turn" if p50 <= 8 else "Keep shoulders level—imagine balancing a book"]
    return int(score), notes


def score_hip_rotation(frames: List[Frame], rel_idx: Optional[int], handedness: str) -> Tuple[int, List[str]]:
    pelvis_ang = _axis_angle_series(frames, "hip")
    shoulder_ang = _axis_angle_series(frames, "shoulder")
    pelvis_w = _derivative(pelvis_ang, frames)
    shoulder_w = _derivative(shoulder_ang, frames)
    p_idx = _peak_idx(pelvis_w)
    s_idx = _peak_idx(shoulder_w)
    lag_ms = frames[s_idx].t_ms - frames[p_idx].t_ms
    lag_score = _bell(lag_ms, center=80, width=60, max_points=140)
    # Smoothness: prefer a single clean peak (low variance outside peak)
    smooth_score = _smoothness_score(pelvis_w, peak_idx=p_idx, max_points=60)
    total = min(200, int(round(lag_score + smooth_score)))
    notes = ["Good hip lead" if 40 <= lag_ms <= 120 else "Let hips start before shoulders"]
    return total, notes


def score_release_angle(frames: List[Frame], rel_idx: Optional[int], handedness: str) -> Tuple[int, List[str]]:
    if rel_idx is None:
        return 0, ["No release detected for release-angle scoring"]
    f = frames[rel_idx]
    wrist_key = f"{handedness}_wrist"
    elbow_key = f"{handedness}_elbow"
    if wrist_key not in f.kp or elbow_key not in f.kp:
        return 0, ["Missing elbow/wrist landmarks at release"]
    wrist = f.kp[wrist_key]
    elbow = f.kp[elbow_key]
    # Forearm vector angle vs horizontal (degrees above horizontal)
    angle = abs(math.degrees(math.atan2(elbow.y - wrist.y, wrist.x - elbow.x)))
    score = _triangular(angle, ideal=35, tol=5, zero_at_low=15, zero_at_high=60, max_points=200)
    note = "Awesome release angle" if 30 <= angle <= 40 else f"Aim for ~35° release (you were ~{angle:.0f}°)"
    return int(score), [note]


def score_power_transfer(frames: List[Frame], rel_idx: Optional[int], handedness: str) -> Tuple[int, List[str]]:
    pelvis_w = _derivative(_axis_angle_series(frames, "hip"), frames)
    shoulder_w = _derivative(_axis_angle_series(frames, "shoulder"), frames)
    wrist_v = _speed_series(frames, f"{handedness}_wrist")
    p_idx, s_idx = _peak_idx(pelvis_w), _peak_idx(shoulder_w)
    w_idx = _peak_idx(wrist_v)
    order_bonus = 100 if p_idx < s_idx < w_idx else 40 if p_idx < w_idx else 0
    hip_to_shoulder = frames[s_idx].t_ms - frames[p_idx].t_ms
    shoulder_to_wrist = frames[w_idx].t_ms - frames[s_idx].t_ms
    timing = _bell(hip_to_shoulder, 80, 50, 60) + _bell(shoulder_to_wrist, 50, 40, 60)
    total = min(200, int(round(order_bonus + timing)))
    notes = ["Nice energy flow: hips→shoulders→hand" if order_bonus >= 100 else "Let hips start, then shoulders, then snap the hand"]
    return total, notes


def score_footwork_timing(frames: List[Frame], rel_idx: Optional[int], handedness: str) -> Tuple[int, List[str]]:
    if rel_idx is None:
        return 0, ["No release detected for footwork scoring"]
    f_rel = frames[rel_idx]
    stance = _stance_width_score(f_rel, max_points=80)
    # Block foot timing heuristic using ankle speed minima near release
    block_side = "left" if handedness == "right" else "right"
    block_key = f"{block_side}_ankle"
    speeds = _speed_series(frames, block_key)
    # Local minimum in a -400..0 ms window
    rel_t = f_rel.t_ms
    idxs = [i for i, f in enumerate(frames) if rel_t - 400 <= f.t_ms <= rel_t]
    min_i = None
    if idxs and speeds:
        min_i = min(idxs, key=lambda i: speeds[i])
    else:
        min_i = rel_idx
    plant_to_rel = rel_t - frames[min_i].t_ms
    timing = _bell(plant_to_rel, center=120, width=100, max_points=120)
    total = int(round(min(200, stance + timing)))
    notes = ["Strong block and base at release" if 80 <= plant_to_rel <= 160 else "Plant your block foot a beat earlier"]
    return total, notes


def score_deductions(frames: List[Frame], rel_idx: Optional[int], handedness: str) -> Tuple[int, List[str], List[str]]:
    ded = 0
    flags: List[str] = []
    notes: List[str] = []
    if rel_idx is not None:
        f = frames[rel_idx]
        trunk = abs(_trunk_lean_deg(f))
        if trunk > 35:
            d = -int(min(80, (trunk - 35) * 2))
            ded += d
            flags.append("excess_trunk_lean")
            notes.append("Keep your chest taller at release")
        side_block = "left" if handedness == "right" else "right"
        valgus = _knee_valgus_deg(f, side=side_block)
        if valgus > 12:
            d = -int(min(60, (valgus - 12) * 3))
            ded += d
            flags.append("knee_valgus")
            notes.append("Knee over toes on the block leg")
    avg_c = _avg_conf(frames, rel_idx, window_ms=200)
    if avg_c < 0.6:
        d = -int((0.6 - avg_c) * 100)
        ded += d
        flags.append("low_confidence_window")
    return ded, flags, notes


def _smoothness_score(series: List[float], peak_idx: int, max_points: int) -> float:
    if not series:
        return 0.0
    peak_val = abs(series[peak_idx])
    if peak_val == 0:
        return 0.0
    # energy outside peak window penalized
    radius = 2
    lo = max(0, peak_idx - radius)
    hi = min(len(series) - 1, peak_idx + radius)
    area_total = sum(abs(v) for v in series)
    area_peak = sum(abs(series[i]) for i in range(lo, hi + 1))
    purity = area_peak / max(1e-6, area_total)
    return max_points * purity


def _score_with_plateau(value: float, ideal: float, ok: float, max_bad: float, max_points: int, lower_is_better: bool) -> int:
    if lower_is_better:
        if value <= ideal:
            return max_points
        if value <= ok:
            return int(max_points * 0.9)
        if value >= max_bad:
            return 0
        # linear drop from ok to max_bad
        return int(max_points * (1 - (value - ok) / (max_bad - ok)))
    else:
        if value >= ideal:
            return max_points
        if value >= ok:
            return int(max_points * 0.9)
        if value <= max_bad:
            return 0
        return int(max_points * (value - max_bad) / (ok - max_bad))


