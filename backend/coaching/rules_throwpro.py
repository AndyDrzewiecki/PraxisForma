"""
ThrowPro coaching rules (provisional). Coaches can edit these without touching engine code.

Structure:
RULES[event_type][component] = list of rule dicts

Each rule:
- condition: semantic key
- threshold: numeric threshold (meaning depends on condition)
- tip: short actionable cue
- drill: drill name
- why: plain-language rationale
"""

from typing import Dict, List


RULES: Dict[str, Dict[str, List[dict]]] = {
    "discus": {
        "separation_sequencing": [
            {
                "condition": "low_x_factor_peak",
                "threshold": 30,  # degrees
                "tip": "Delay your shoulder turn a beat—let the hips lead",
                "drill": "Wall Separation Drill",
                "why": "Creates more twist between hips and shoulders to build torque",
            },
            {
                "condition": "poor_chain_order",
                "threshold": 60,  # chain order score
                "tip": "Hips start, then shoulders, then fast hand—count it out",
                "drill": "Step-in Kinetics Drill",
                "why": "Right sequence sends power from ground to hand efficiently",
            },
        ],
        "lower_body_platform": [
            {
                "condition": "unstable_stance",
                "threshold": 0.15,  # stance variance
                "tip": "Plant the block foot and keep your base steady into release",
                "drill": "South African Drill",
                "why": "A stable base lets your upper body rotate and release cleanly",
            },
        ],
        "arm_implement_kinetics": [
            {
                "condition": "low_hand_speed",
                "threshold": 1.0,  # proxy
                "tip": "Snap the wrist at the finish—'pop' the throw",
                "drill": "Wrist Flicks + Light Implement Throws",
                "why": "A fast hand at the end adds distance without extra strain",
            }
        ],
        "release_quality": [
            {
                "condition": "angle_low",
                "threshold": 28,  # deg
                "tip": "Lift through the finish—aim your throw a little higher",
                "drill": "High Release Target Drill",
                "why": "A better release angle helps your throw carry farther",
            },
            {
                "condition": "angle_high",
                "threshold": 42,  # deg
                "tip": "Don't lean back—drive forward and release out, not up",
                "drill": "Forward Drive Release",
                "why": "Keeps energy moving into the sector without stalling",
            },
        ],
        "smoothness_control": [
            {
                "condition": "high_jerk",
                "threshold": 2.0,  # jerk proxy
                "tip": "Make your turn smooth—think 'glide' not 'jump'",
                "drill": "Slow-Mo South Africans",
                "why": "Smoother motion stays balanced and transfers power better",
            }
        ],
    },
    "shot_put_rotational": {
        "separation_sequencing": [
            {
                "condition": "low_x_factor_peak",
                "threshold": 25,
                "tip": "Keep your shoulders closed as hips open to the sector",
                "drill": "Wall Separation Drill (Shot)",
                "why": "More separation builds torque for a stronger finish",
            }
        ],
        "release_quality": [
            {
                "condition": "angle_low",
                "threshold": 30,
                "tip": "Punch up through the ball—think 'up and out'",
                "drill": "Tall Finish Drill",
                "why": "Improves ball flight and distance",
            }
        ],
    },
    "shot_put_glide": {
        "lower_body_platform": [
            {
                "condition": "unstable_stance",
                "threshold": 0.15,
                "tip": "Stick the block and lock the knee gently at finish",
                "drill": "Power Position Holds",
                "why": "A solid block turns linear speed into a strong release",
            }
        ],
    },
}


