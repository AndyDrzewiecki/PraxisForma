Biomechanics Expansion — Explicit Formulas

This document summarizes the shared conventions and formulas implemented in `backend/biomech/features.py` for Sprint 12.

- Frames: Camera (image), Global floor (X lateral, Y forward), Local pelvis.
- Vector helpers: unit, dot, crossz; signed angles via atan2 and unwrap.
- Smoothing: 100 Hz resample, ≤150 ms gap fill, Savitzky–Golay (window 11, poly 3) pre-derivative.
- Derivatives: central difference on unwrapped radians; convert to deg/s and deg/s² for reporting.

Key features
- Segment angles: knee, hip, shoulder, elbow, wrist per three-point angle.
- Pelvis/thorax rotation: signed vs global X using left→right axis; separation = thorax − pelvis.
- Angular velocities/accelerations: ω, α via central differences.
- Hand linear velocity: wrist finite diff; normalized by shoulder width at t0.
- Sequencing: first prominent positive peaks for ω_pelvis, ω_thorax, v_hand_norm in delivery; Δhip_torso, Δtorso_hand, Δhip_hand; chain_order_score in [0,1].
- Rotational accel quality: α_ratio = peak+ / |min−| for pelvis in delivery.
- Block-leg force proxies: horizontal decel proxy from ω_thorax drop in last 150 ms; vertical proxy from mean positive α_pelvis; both normalized by 95th percentile v_hand_norm.
- Foot progression and stance width: stance ratio ankle distance / shoulder width; foot angle vs forward (reserved).

Persistence
- Per-frame series added under `pqs_v2.series`: `t_ms`, `separation_deg`, `ω_pelvis`, `ω_thorax`, `v_hand_norm`.
- Summary metrics in `pqs_v2.metrics`: `Δhip_torso_ms`, `Δtorso_hand_ms`, `chain_order_score`, `α_peak_pelvis_pos`, `α_min_pelvis_neg`, `α_ratio`, `F_block_horiz_proxy`, `F_block_vert_proxy`, `v_hand_peak_norm`.

Smoothing
- Central differences on unwrapped radians for ω and α; optional moving-average smoothing (window W=5 frames by default) applied to `ω_pelvis`, `ω_thorax`, `α_pelvis`, `α_thorax`, and `v_hand_norm`.
- Both raw and smoothed series are exposed: e.g., `ω_pelvis` and `ω_pelvis_smooth`.

Hand speed normalization
- Preferred basis: standing-height surrogate if available; else shoulder–hip composite length at t0. The goal is to reduce camera distance effects while tracking implement speed proxy.


