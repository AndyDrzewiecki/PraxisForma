from pqs_algorithm import make_frame, calculate_pqs, Frame, Landmark
import math


def test_release_detection_right():
    # Wrist moves upward and speeds up near the end
    frames = []
    for i in range(20):
        t = i * 40  # 25 fps
        # Simple motion: wrist accelerates; shoulder and elbow roughly static
        wrist_x = 0.2 + 0.02 * i
        wrist_y = 0.8 - 0.02 * i
        points = {
            "right_shoulder": (0.3, 0.6),
            "right_elbow": (0.35, 0.65),
            "right_wrist": (wrist_x, wrist_y),
        }
        frames.append(make_frame(t, points))

    result = calculate_pqs(frames)
    assert result.release_t_ms is not None
    assert result.handedness == "right"


def test_handedness_left():
    # Left wrist shows much higher peak speed
    frames = []
    for i in range(20):
        t = i * 33
        left_wrist_x = 0.8 - 0.03 * i
        left_wrist_y = 0.8 - 0.01 * i
        points = {
            "left_shoulder": (0.7, 0.6),
            "left_elbow": (0.65, 0.65),
            "left_wrist": (left_wrist_x, left_wrist_y),
        }
        frames.append(make_frame(t, points))

    result = calculate_pqs(frames)
    assert result.handedness == "left"


if __name__ == "__main__":
    test_release_detection_right()
    test_handedness_left()
    
    # Component scorer tests (synthetic)
    # 1) Release angle ~35°
    frames = []
    for i in range(5):
        t = i * 40
        frames.append(make_frame(t, {"right_shoulder": (0.4, 0.6), "right_elbow": (0.5, 0.6), "right_wrist": (0.6, 0.55)}))
    res = calculate_pqs(frames)
    assert res.release_t_ms is not None
    # 2) Confidence gating: create low-confidence around release
    # Manually lower scores in ±200 ms
    rel_ms = res.release_t_ms
    def low_conf(f: Frame) -> Frame:
        new_kp = {}
        for k, v in f.kp.items():
            new_kp[k] = Landmark(x=v.x, y=v.y, score=(0.5 if abs(f.t_ms - rel_ms) <= 200 else 1.0))
        return Frame(t_ms=f.t_ms, kp=new_kp)
    lowc_frames = [low_conf(f) for f in frames]
    res2 = calculate_pqs(lowc_frames)
    # Since gating applies, total with low confidence should be <= baseline
    assert res2.total <= res.total
    print("Smoke and component gating tests passed")


