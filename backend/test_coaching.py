from coaching.throwpro import generate_throw_feedback


def test_coaching_priority_fix_low_separation():
    pqs_v2 = {
        "total": 400,
        "components": {
            "lower_body_platform": 150,
            "separation_sequencing": 80,  # <70% triggers
            "arm_implement_kinetics": 150,
            "release_quality": 150,
            "smoothness_control": 150,
        },
        "metrics": {
            "x_factor_peak_deg": 20.0,
            "chain_order_score": 40.0,
            "release_angle_deg": 30.0,
            "release_height_norm": 0.1,
            "hand_speed_proxy": 0.5,
        },
    }
    fb = generate_throw_feedback(pqs_v2, event_type="discus", athlete_profile={"experience_level": "novice"})
    assert fb["priority_fixes"]


def test_coaching_strengths_high_scores():
    pqs_v2 = {
        "total": 950,
        "components": {
            "lower_body_platform": 190,
            "separation_sequencing": 195,
            "arm_implement_kinetics": 190,
            "release_quality": 190,
            "smoothness_control": 195,
        },
        "metrics": {
            "x_factor_peak_deg": 60.0,
            "chain_order_score": 100.0,
            "release_angle_deg": 35.0,
            "release_height_norm": 0.2,
            "hand_speed_proxy": 3.0,
        },
    }
    fb = generate_throw_feedback(pqs_v2, event_type="discus", athlete_profile={"experience_level": "advanced"})
    assert fb["reinforce_strengths"]

