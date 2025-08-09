"""
PQS v2 scoring envelopes and constants.

NOTE: Provisional values; TODO refine by age/sex/handedness bands.
"""

# Sampling
TARGET_HZ = 100
MAX_GAP_MS = 150
SMOOTH_WINDOW_SAMPLES = 11  # for Savitzky–Golay or moving average fallback
SMOOTH_POLY = 3

# Timing windows (ms)
HIP_SHOULDER_LAG_CENTER = 80
HIP_SHOULDER_LAG_WIDTH = 60
CHAIN_ORDER_MAX_POINTS = 100

# Release targets (discus)
RELEASE_ANGLE_IDEAL = 35.0
RELEASE_ANGLE_TOL = 5.0
RELEASE_ANGLE_LOW = 20.0
RELEASE_ANGLE_HIGH = 55.0

# Stance
STANCE_RATIO_IDEAL = 1.0
STANCE_RATIO_TOL = 0.2
STANCE_RATIO_LOW = 0.5
STANCE_RATIO_HIGH = 1.8

# Smoothness / jerk
JERK_MAX_POINTS = 200

# Component max points (each 0-200)
COMP_MAX = 200


