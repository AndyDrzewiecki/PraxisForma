from typing import Dict, List

from backend.coaching.rules_throwpro import RULES


def _score_to_pct(score: int, max_points: int = 200) -> float:
    return max(0.0, min(1.0, score / float(max_points)))


def _cap_priorities(num: int, athlete_profile: Dict) -> int:
    lvl = (athlete_profile or {}).get("experience_level", "novice").lower()
    if lvl in ("novice", "beginner"):
        return min(num, 2)
    if lvl in ("intermediate",):
        return min(num, 3)
    return min(num, 4)


def generate_throw_feedback(pqs_v2: Dict, event_type: str, athlete_profile: Dict) -> Dict:
    comps = (pqs_v2 or {}).get("components", {})
    metrics = (pqs_v2 or {}).get("metrics", {})
    rules = RULES.get(event_type, {})

    priority_fixes: List[Dict] = []
    reinforce: List[Dict] = []
    drills: List[Dict] = []

    # Map underperformance (<70%) to rule-based fixes
    for comp_key, score in comps.items():
        pct = _score_to_pct(int(score))
        if pct < 0.7:
            for rule in rules.get(comp_key, []):
                cond = rule.get("condition")
                thr = rule.get("threshold")
                hit = False
                if cond == "low_x_factor_peak":
                    hit = metrics.get("x_factor_peak_deg", 0.0) < thr
                elif cond == "poor_chain_order":
                    hit = metrics.get("chain_order_score", 0.0) < thr
                elif cond == "unstable_stance":
                    # Heuristic: we don't have variance here; attach anyway when platform low
                    hit = True
                elif cond == "low_hand_speed":
                    hit = metrics.get("hand_speed_proxy", 0.0) < thr
                elif cond == "angle_low":
                    hit = metrics.get("release_angle_deg", 0.0) < thr
                elif cond == "angle_high":
                    hit = metrics.get("release_angle_deg", 0.0) > thr
                elif cond == "high_jerk":
                    hit = True
                if hit:
                    # Rough phase mapping by component
                    phase = {
                        "separation_sequencing": "power",
                        "lower_body_platform": "delivery",
                        "arm_implement_kinetics": "delivery",
                        "release_quality": "release",
                        "smoothness_control": "entry",
                    }.get(comp_key, "delivery")
                    priority_fixes.append({
                        "phase": phase,
                        "issue": comp_key.replace("_", " ").title(),
                        "tip": rule.get("tip"),
                        "why": rule.get("why"),
                    })
                    drills.append({"name": rule.get("drill"), "link": "https://example.com/drills"})
                    break

    # Reinforce strengths (>90%)
    for comp_key, score in comps.items():
        pct = _score_to_pct(int(score))
        if pct >= 0.9:
            phase = {
                "separation_sequencing": "power",
                "lower_body_platform": "delivery",
                "arm_implement_kinetics": "delivery",
                "release_quality": "release",
                "smoothness_control": "entry",
            }.get(comp_key, "delivery")
            reinforce.append({
                "phase": phase,
                "strength": comp_key.replace("_", " ").title(),
            })

    # Cap number of fixes by experience
    cap = _cap_priorities(len(priority_fixes), athlete_profile)
    priority_fixes = priority_fixes[:cap]
    drills = drills[:max(1, cap)]

    # Summary
    total = int(pqs_v2.get("total", 0))
    if total >= 800:
        summary = "Great work—keep building on your strengths and stay smooth through the finish!"
    elif total >= 500:
        summary = "Strong throw! A couple small tweaks will help you unlock more distance."
    else:
        summary = "You’re learning fast—let’s focus on one or two simple things to boost power."

    return {
        "summary": summary,
        "priority_fixes": priority_fixes,
        "reinforce_strengths": reinforce,
        "drill_suggestions": drills,
    }


