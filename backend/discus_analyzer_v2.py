from google.cloud import videointelligence
from google.cloud import storage
import json
import gzip
from datetime import datetime
import os
import math
import re
import glob
import tempfile
from typing import List, Dict, Optional
import argparse
from backend.coaching.throwpro import generate_throw_feedback

from pqs_algorithm import Frame as PQSFrame, Landmark as PQSLandmark, calculate_pqs, calculate_pqs_v2, detect_handedness, detect_release_idx

class ComprehensiveDiscusAnalyzer:
    def __init__(self):
        # Available landmarks from Google Video Intelligence (0-16)
        self.LANDMARKS = {
            'nose': 0,
            'left_eye': 1,
            'right_eye': 2, 
            'left_ear': 3,
            'right_ear': 4,
            'left_shoulder': 5,
            'right_shoulder': 6,
            'left_elbow': 7,
            'right_elbow': 8,
            'left_wrist': 9,
            'right_wrist': 10,
            'left_hip': 11,
            'right_hip': 12,
            'left_knee': 13,
            'right_knee': 14,
            'left_ankle': 15,
            'right_ankle': 16
        }
    
    def check_video_size(self, video_name):
        """Check if video is under 400MB"""
        try:
            storage_client = storage.Client()
            bucket_name = "praxisforma-videos"
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(video_name)
            
            # Reload blob to get current metadata
            blob.reload()
            
            if blob.size is None:
                print("ERROR: Could not get file size for " + video_name)
                return False
            
            file_size_mb = float(blob.size) / (1024.0 * 1024.0)
            print("Video size: " + str(round(file_size_mb, 1)) + " MB")
            
            if file_size_mb > 400:
                print("ERROR: Video is too large (" + str(round(file_size_mb, 1)) + "MB)")
                print("Maximum file size is 400MB for reliable processing.")
                return False
            else:
                print("Video size OK for processing (under 400MB)")
                return True
                
        except Exception as e:
            print("ERROR checking video size: " + str(e))
            return False
    
    def analyze_video_with_full_output(self, video_name):
        """Analyze video and save ALL detailed landmark data"""
        print("Starting comprehensive analysis of " + video_name + "...")
        
        # Check size first
        if not self.check_video_size(video_name):
            return None
        
        # Create output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_video_name = video_name.replace(" ", "_").replace("(", "").replace(")", "").replace(".mp4", "")
        output_filename = "full_analysis_" + safe_video_name + "_" + timestamp + ".txt"
        
        # Initialize Video Intelligence client
        client = videointelligence.VideoIntelligenceServiceClient()
        
        # Configure for person detection with ALL pose landmarks
        features = [videointelligence.Feature.PERSON_DETECTION]
        
        person_config = videointelligence.PersonDetectionConfig(
            include_bounding_boxes=True,
            include_attributes=True,
            include_pose_landmarks=True,
        )
        
        video_context = videointelligence.VideoContext(
            person_detection_config=person_config
        )
        
        # Full path to video
        input_uri = "gs://praxisforma-videos/" + video_name
        
        # Start the analysis
        operation = client.annotate_video(
            request={
                "features": features,
                "input_uri": input_uri,
                "video_context": video_context,
            }
        )
        
        print("Processing video... this may take up to 30 minutes")
        result = operation.result(timeout=1800)  # 30 minute timeout
        
        # Extract ALL pose data
        annotations = result.annotation_results[0]
        
        # Open output file for writing
        with open(output_filename, 'w') as f:
            f.write("PRAXISFORMA COMPREHENSIVE DISCUS ANALYSIS\n")
            f.write("Video: " + video_name + "\n")
            f.write("Analysis Time: " + str(datetime.now()) + "\n")
            f.write("=" * 60 + "\n\n")
            
            if annotations.person_detection_annotations:
                total_people = len(annotations.person_detection_annotations)
                f.write("SUMMARY:\n")
                f.write("Found " + str(total_people) + " person detections\n\n")
                print("Found " + str(total_people) + " person detections")
                
                # Process EVERY person with ALL their landmark data
                for person_idx, person in enumerate(annotations.person_detection_annotations):
                    f.write("=" * 50 + "\n")
                    f.write("PERSON " + str(person_idx + 1) + ":\n")
                    f.write("Track confidence: " + str(round(person.tracks[0].confidence, 3)) + "\n")
                    f.write("=" * 50 + "\n\n")
                    
                    total_landmarks_this_person = 0
                    
                    # Process ALL tracks for this person
                    for track in person.tracks:
                        f.write("TRACK DATA:\n")
                        
                        # Process ALL timestamped objects (every frame)
                        for obj_idx, timestamped_object in enumerate(track.timestamped_objects):
                            if timestamped_object.landmarks:
                                time_sec = timestamped_object.time_offset.total_seconds()
                                landmark_count = len(timestamped_object.landmarks)
                                total_landmarks_this_person += landmark_count
                                
                                f.write("\nTime: " + str(round(time_sec, 2)) + "s - " + str(landmark_count) + " landmarks\n")
                                
                                # Write ALL landmark coordinates
                                for landmark_idx, landmark in enumerate(timestamped_object.landmarks):
                                    f.write("  Landmark " + str(landmark_idx) + ": x=" + 
                                           str(round(landmark.point.x, 3)) + ", y=" + 
                                           str(round(landmark.point.y, 3)) + "\n")
                    
                    f.write("\nTotal landmarks for Person " + str(person_idx + 1) + ": " + str(total_landmarks_this_person) + "\n")
                    f.write("-" * 50 + "\n\n")
                    
                    print("Person " + str(person_idx + 1) + ": " + str(total_landmarks_this_person) + " landmarks (confidence: " + str(round(person.tracks[0].confidence, 3)) + ")")
            
            else:
                f.write("No person detections found\n")
                print("No person detections found")
        
        print("\nVideo analysis complete! Full results saved to: " + output_filename)
        return output_filename
    
    def calculate_angle(self, point1, point2, point3):
        """Calculate angle between three points"""
        v1 = (point1['x'] - point2['x'], point1['y'] - point2['y'])
        v2 = (point3['x'] - point2['x'], point3['y'] - point2['y'])
        
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        magnitude1 = math.sqrt(v1[0]**2 + v1[1]**2)
        magnitude2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
            
        cos_angle = dot_product / (magnitude1 * magnitude2)
        cos_angle = max(-1, min(1, cos_angle))
        angle_rad = math.acos(cos_angle)
        return math.degrees(angle_rad)
    
    def analyze_biomechanics_from_file(self, analysis_filename):
        """Extract biomechanics from comprehensive analysis file"""
        print("Analyzing biomechanics from: " + analysis_filename)
        
        with open(analysis_filename, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        all_people_data = {}
        current_person = None
        current_time = None
        
        # Parse all people and their landmark data
        for line in lines:
            # Look for person sections
            if line.startswith("PERSON ") and ":" in line:
                person_match = re.search(r'PERSON (\d+):', line)
                if person_match:
                    current_person = int(person_match.group(1))
                    all_people_data[current_person] = {'confidence': 0, 'frames': {}}
            
            # Look for confidence
            elif "Track confidence:" in line and current_person is not None:
                conf_match = re.search(r'confidence: ([\d.]+)', line)
                if conf_match:
                    all_people_data[current_person]['confidence'] = float(conf_match.group(1))
            
            # Look for time stamps
            elif "Time:" in line and "landmarks" in line and current_person is not None:
                time_match = re.search(r'Time: ([\d.]+)s', line)
                if time_match:
                    current_time = float(time_match.group(1))
                    all_people_data[current_person]['frames'][current_time] = {}
            
            # Look for landmark coordinates
            elif "Landmark" in line and "x=" in line and current_person is not None and current_time is not None:
                landmark_match = re.search(r'Landmark (\d+): x=([\d.]+), y=([\d.]+)', line)
                if landmark_match:
                    landmark_id = int(landmark_match.group(1))
                    x = float(landmark_match.group(2))
                    y = float(landmark_match.group(3))
                    all_people_data[current_person]['frames'][current_time][landmark_id] = {'x': x, 'y': y}
        
        # Now analyze biomechanics for each person
        print("\n" + "=" * 60)
        print("BIOMECHANICAL ANALYSIS OF ALL PEOPLE")
        print("=" * 60)
        
        for person_id, person_data in all_people_data.items():
            if not person_data['frames']:
                continue
                
            print(f"\n=== PERSON {person_id} ===")
            print(f"Confidence: {person_data['confidence']:.3f}")
            print(f"Frames with data: {len(person_data['frames'])}")
            
            # Analyze key frames for this person
            times = sorted(person_data['frames'].keys())
            if len(times) == 0:
                continue
                
            # Sample frames throughout the sequence
            sample_times = times[::max(1, len(times)//5)] if len(times) > 5 else times
            
            for time in sample_times[:3]:  # Show first 3 sample frames
                landmarks = person_data['frames'][time]
                insights = self.analyze_frame_biomechanics(landmarks)
                
                if insights:
                    print(f"\n--- Time: {time:.2f}s ---")
                    for key, value in insights.items():
                        if 'feedback' in key:
                            print(f"{key.replace('_feedback', '').upper()}: {value}")
                        elif 'angle' in key:
                            print(f"{key.replace('_', ' ').upper()}: {value:.1f}°")
        
        # Build PQS-ready frames for the highest-confidence person (if available)
        top_person_id = None
        top_conf = -1.0
        for pid, pdata in all_people_data.items():
            if pdata.get('confidence', 0) > top_conf and pdata.get('frames'):
                top_conf = pdata['confidence']
                top_person_id = pid

        if top_person_id is None:
            print("No person with frames to compute PQS")
            return all_people_data

        person_frames = all_people_data[top_person_id]['frames']
        # Convert to ordered PQSFrame list
        ordered_times = sorted(person_frames.keys())
        pqs_frames: List[PQSFrame] = []
        for t_sec in ordered_times:
            lm_map: Dict[str, PQSLandmark] = {}
            fv = person_frames[t_sec]
            # Map numeric ids to names per LANDMARKS
            name_by_id = {v: k for k, v in self.LANDMARKS.items()}
            for lm_id, xy in fv.items():
                name = name_by_id.get(lm_id)
                if not name:
                    continue
                lm_map[name] = PQSLandmark(x=xy['x'], y=xy['y'], score=1.0)
            pqs_frames.append(PQSFrame(t_ms=int(t_sec * 1000), kp=lm_map))

        # PQS v1 and v2
        handedness = detect_handedness(pqs_frames)
        rel_idx = detect_release_idx(pqs_frames, handedness)
        pqs = calculate_pqs(pqs_frames)
        pqs_v2 = calculate_pqs_v2(pqs_frames, handedness, rel_idx)

        # Emit compact JSON alongside verbose text file
        video_basename = os.path.splitext(os.path.basename(analysis_filename))[0]
        json_out = {
            "video": {"name": video_basename, "duration_ms": (ordered_times[-1] - ordered_times[0]) * 1000 if ordered_times else 0},
            "pqs": {
                "total": pqs.total,
                "components": {
                    "shoulder_alignment": pqs.shoulder_alignment,
                    "hip_rotation": pqs.hip_rotation,
                    "release_angle": pqs.release_angle,
                    "power_transfer": pqs.power_transfer,
                    "footwork_timing": pqs.footwork_timing,
                },
                "deductions": pqs.deductions,
                "release_t_ms": pqs.release_t_ms,
                "handedness": pqs.handedness,
                "flags": pqs.flags,
                "notes": pqs.notes,
            },
            "pqs_v2": pqs_v2,
        }
        json_name = f"{video_basename}.pqs.json"
        with open(json_name, "w") as jf:
            json.dump(json_out, jf, indent=2)

        print(f"PQS={pqs.total} (R@{pqs.release_t_ms}) [side={pqs.handedness}]")
        print(f"Wrote {json_name}")

        return all_people_data


def _annotate_video_from_local(path: str):
    client = videointelligence.VideoIntelligenceServiceClient()
    features = [videointelligence.Feature.PERSON_DETECTION]
    person_config = videointelligence.PersonDetectionConfig(
        include_bounding_boxes=True,
        include_attributes=True,
        include_pose_landmarks=True,
    )
    video_context = videointelligence.VideoContext(person_detection_config=person_config)
    with open(path, "rb") as f:
        content = f.read()
    operation = client.annotate_video(
        request={
            "features": features,
            "input_content": content,
            "video_context": video_context,
        }
    )
    result = operation.result(timeout=1800)
    return result.annotation_results[0]


def _download_gsuri_to_temp(gs_uri: str) -> str:
    assert gs_uri.startswith("gs://")
    _, rest = gs_uri.split("gs://", 1)
    bucket_name, blob_name = rest.split("/", 1)
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    blob.download_to_filename(tmp_path)
    return tmp_path


def analyze_video(video_uri_or_path: str, with_coaching: bool = False, event_type: str = "discus", athlete_profile: dict | None = None) -> dict:
    """
    Accepts a local path or gs:// URI. If gs://, downloads to temp.
    Runs pose -> PQS -> returns a dict matching the .pqs.json schema.
    """
    local_path: Optional[str] = None
    temp_to_cleanup: Optional[str] = None
    try:
        if video_uri_or_path.startswith("gs://"):
            local_path = _download_gsuri_to_temp(video_uri_or_path)
            temp_to_cleanup = local_path
        else:
            local_path = video_uri_or_path

        annotations = _annotate_video_from_local(local_path)

        # Build all_people_data in-memory
        all_people_data: Dict[int, Dict] = {}
        if annotations.person_detection_annotations:
            for person_idx, person in enumerate(annotations.person_detection_annotations):
                conf = float(person.tracks[0].confidence) if person.tracks else 0.0
                frames_map: Dict[float, Dict[int, Dict[str, float]]] = {}
                for track in person.tracks:
                    for timestamped_object in track.timestamped_objects:
                        if not timestamped_object.landmarks:
                            continue
                        t = float(timestamped_object.time_offset.total_seconds())
                        if t not in frames_map:
                            frames_map[t] = {}
                        for landmark_idx, landmark in enumerate(timestamped_object.landmarks):
                            frames_map[t][landmark_idx] = {
                                "x": float(landmark.point.x),
                                "y": float(landmark.point.y),
                            }
                all_people_data[person_idx + 1] = {"confidence": conf, "frames": frames_map}

        # Choose top person by confidence
        if not all_people_data:
            ordered_times = []
            pqs_total = 0
            pqs_obj = {
                "total": 0,
                "components": {
                    "shoulder_alignment": 0,
                    "hip_rotation": 0,
                    "release_angle": 0,
                    "power_transfer": 0,
                    "footwork_timing": 0,
                },
                "deductions": 0,
                "release_t_ms": None,
                "handedness": "right",
                "flags": ["no_person_detected"],
                "notes": ["No pose landmarks detected"],
            }
            return {
                "video": {"name": os.path.basename(video_uri_or_path), "duration_ms": 0},
                "pqs": pqs_obj,
            }

        top_person_id = max(all_people_data.keys(), key=lambda pid: all_people_data[pid].get("confidence", 0))
        person_frames = all_people_data[top_person_id]["frames"]
        ordered_times = sorted(person_frames.keys())
        name_by_id = {
            0: "nose",
            1: "left_eye",
            2: "right_eye",
            3: "left_ear",
            4: "right_ear",
            5: "left_shoulder",
            6: "right_shoulder",
            7: "left_elbow",
            8: "right_elbow",
            9: "left_wrist",
            10: "right_wrist",
            11: "left_hip",
            12: "right_hip",
            13: "left_knee",
            14: "right_knee",
            15: "left_ankle",
            16: "right_ankle",
        }
        pqs_frames: List[PQSFrame] = []
        for t_sec in ordered_times:
            lm_map: Dict[str, PQSLandmark] = {}
            fv = person_frames[t_sec]
            for lm_id, xy in fv.items():
                name = name_by_id.get(lm_id)
                if not name:
                    continue
                lm_map[name] = PQSLandmark(x=xy["x"], y=xy["y"], score=1.0)
            pqs_frames.append(PQSFrame(t_ms=int(t_sec * 1000), kp=lm_map))

        # v1
        pqs = calculate_pqs(pqs_frames)
        # v2
        handedness = detect_handedness(pqs_frames)
        rel_idx = detect_release_idx(pqs_frames, handedness)
        # Use athlete profile context if provided, else defaults
        ctx = athlete_profile or {}
        ctx_event = event_type or 'discus'
        ctx_age = ctx.get('ageBand') or 'Open'
        ctx_sex = ctx.get('sex') or 'M'
        ctx_hand = ctx.get('handedness') or handedness
        pqs_v2 = calculate_pqs_v2(pqs_frames, ctx_hand, rel_idx, event=ctx_event, age_band=ctx_age, sex=ctx_sex)

        result = {
            "video": {
                "name": os.path.basename(video_uri_or_path),
                "duration_ms": int((ordered_times[-1] - ordered_times[0]) * 1000) if ordered_times else 0,
            },
            "pqs": {
                "total": pqs.total,
                "components": {
                    "shoulder_alignment": pqs.shoulder_alignment,
                    "hip_rotation": pqs.hip_rotation,
                    "release_angle": pqs.release_angle,
                    "power_transfer": pqs.power_transfer,
                    "footwork_timing": pqs.footwork_timing,
                },
                "deductions": pqs.deductions,
                "release_t_ms": pqs.release_t_ms,
                "handedness": pqs.handedness,
                "flags": pqs.flags,
                "notes": pqs.notes,
            },
            "pqs_v2": pqs_v2,
        }
        if with_coaching:
            result["coaching"] = generate_throw_feedback(pqs_v2, event_type=event_type, athlete_profile=athlete_profile or {})

        # Persist per-frame landmarks (compressed JSON) to GCS and include URI in result.assets
        try:
            frames_out = []
            for t_sec in ordered_times:
                fv = person_frames[t_sec]
                landmarks = [{"x": float(xy["x"]), "y": float(xy["y"]), "z": None, "confidence": 1.0} for _, xy in fv.items()]
                frames_out.append({"timestamp_ms": int(t_sec * 1000), "landmarks": landmarks})

            # Determine bucket, uid, and basename
            bucket_name = os.getenv("GCS_BUCKET", "praxisforma-videos")
            user_id = None
            base = os.path.splitext(os.path.basename(video_uri_or_path))[0]
            if isinstance(video_uri_or_path, str) and video_uri_or_path.startswith("gs://"):
                try:
                    _, rest = video_uri_or_path.split("gs://", 1)
                    bkt, path = rest.split("/", 1)
                    bucket_name = bkt
                    parts = path.split("/")
                    if len(parts) >= 3:
                        user_id = parts[1]
                        base = os.path.splitext(parts[-1])[0]
                except Exception:
                    pass
            if not user_id:
                user_id = "unknown"

            landmarks_path = f"landmarks/{user_id}/{base}.landmarks.json"
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(landmarks_path)
            payload = json.dumps(frames_out).encode("utf-8")
            gz = gzip.compress(payload)
            blob.upload_from_string(gz, content_type="application/json")
            result.setdefault("assets", {})["landmarks_uri"] = f"gs://{bucket_name}/{landmarks_path}"
        except Exception:
            pass

        return result
    finally:
        # Cleanup temp file if created
        if 'temp_to_cleanup' in locals() and temp_to_cleanup and os.path.exists(temp_to_cleanup):
            try:
                os.remove(temp_to_cleanup)
            except Exception:
                pass
    
    def analyze_frame_biomechanics(self, landmarks):
        """Analyze biomechanics for a single frame"""
        insights = {}
        
        # Throwing arm analysis
        if (self.LANDMARKS['right_shoulder'] in landmarks and 
            self.LANDMARKS['right_elbow'] in landmarks and 
            self.LANDMARKS['right_wrist'] in landmarks):
            
            shoulder = landmarks[self.LANDMARKS['right_shoulder']]
            elbow = landmarks[self.LANDMARKS['right_elbow']]
            wrist = landmarks[self.LANDMARKS['right_wrist']]
            
            arm_angle = self.calculate_angle(shoulder, elbow, wrist)
            insights['throwing_arm_angle'] = arm_angle
            insights['arm_feedback'] = self.assess_arm_angle(arm_angle)
        
        # Shoulder balance
        if (self.LANDMARKS['left_shoulder'] in landmarks and 
            self.LANDMARKS['right_shoulder'] in landmarks):
            
            left_shoulder = landmarks[self.LANDMARKS['left_shoulder']]
            right_shoulder = landmarks[self.LANDMARKS['right_shoulder']]
            
            shoulder_tilt = math.degrees(math.atan2(
                right_shoulder['y'] - left_shoulder['y'],
                right_shoulder['x'] - left_shoulder['x']
            ))
            
            insights['shoulder_tilt'] = abs(shoulder_tilt)
            insights['shoulder_feedback'] = self.assess_shoulder_level(abs(shoulder_tilt))
        
        # Hip balance analysis
        if (self.LANDMARKS['left_hip'] in landmarks and 
            self.LANDMARKS['right_hip'] in landmarks):
            
            left_hip = landmarks[self.LANDMARKS['left_hip']]
            right_hip = landmarks[self.LANDMARKS['right_hip']]
            
            hip_tilt = math.degrees(math.atan2(
                right_hip['y'] - left_hip['y'],
                right_hip['x'] - left_hip['x']
            ))
            
            insights['hip_tilt'] = abs(hip_tilt)
            insights['hip_feedback'] = self.assess_hip_level(abs(hip_tilt))
        
        return insights
    
    def assess_arm_angle(self, angle):
        if angle < 120:
            return "Arm too bent - extend more for power"
        elif angle > 160:
            return "Arm too straight - allow slight bend"
        else:
            return "Good arm extension"
    
    def assess_shoulder_level(self, tilt):
        if tilt > 15:
            return "Shoulders uneven - work on balance"
        elif tilt > 5:
            return "Slight shoulder tilt - minor adjustment needed"
        else:
            return "Excellent shoulder level"
    
    def assess_hip_level(self, tilt):
        if tilt > 12:
            return "Hips uneven - check stance"
        elif tilt > 3:
            return "Minor hip imbalance"
        else:
            return "Good hip level"

# Main execution functions
def analyze_new_video(video_name):
    """Analyze a new video with full data capture"""
    analyzer = ComprehensiveDiscusAnalyzer()
    result_file = analyzer.analyze_video_with_full_output(video_name)
    return result_file

def analyze_existing_file(analysis_filename):
    """Analyze biomechanics from existing analysis file"""
    analyzer = ComprehensiveDiscusAnalyzer()
    results = analyzer.analyze_biomechanics_from_file(analysis_filename)
    return results

def list_available_videos():
    """List all videos in the bucket"""
    try:
        storage_client = storage.Client()
        bucket_name = "praxisforma-videos"
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs()
        
        videos = []
        for blob in blobs:
            if blob.name.endswith('.mp4'):
                # Reload blob to get current metadata
                blob.reload()
                
                if blob.size is not None:
                    size_mb = float(blob.size) / (1024.0 * 1024.0)
                    videos.append({
                        'name': blob.name,
                        'size_mb': size_mb,
                        'under_400mb': size_mb <= 400
                    })
                else:
                    print("Warning: Could not get size for " + blob.name)
        
        return videos
        
    except Exception as e:
        print("ERROR listing videos: " + str(e))
        return []

def list_existing_analysis_files():
    """List all analysis files in current directory"""
    analysis_files = glob.glob("*analysis*.txt")
    return analysis_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PraxisForma Discus Analyzer")
    parser.add_argument("--input", dest="input_path", help="Local file path or gs:// URI", required=False)
    args, _ = parser.parse_known_args()

    if args.input_path:
        out = analyze_video(args.input_path)
        base = os.path.splitext(os.path.basename(args.input_path))[0]
        json_name = f"{base}.pqs.json"
        with open(json_name, "w") as jf:
            json.dump(out, jf, indent=2)
        pqs = out.get("pqs", {})
        print(f"PQS={pqs.get('total', 0)} (R@{pqs.get('release_t_ms')}) [side={pqs.get('handedness','?')}]")
        print(f"Wrote {json_name}")
    else:
        print("=== PRAXISFORMA DISCUS ANALYZER ===")
    print("1. Analyze new video (single)")
    print("2. Analyze new video (select from bucket)")
    print("3. Analyze new video (process ALL videos under 400MB)")
    print("4. Analyze existing analysis file (select)")
    print("5. Analyze existing analysis file (process ALL analysis files)")
    
    choice = input("Enter choice (1-5): ")
    
    if choice == "1":
        video_name = input("Enter video name (e.g., 'videoplayback (2).mp4'): ")
        result_file = analyze_new_video(video_name)
        if result_file:
            print("Analysis complete! Now analyzing biomechanics...")
            analyze_existing_file(result_file)
    
    elif choice == "2":
        print("\nFetching available videos...")
        videos = list_available_videos()
        
        if not videos:
            print("No videos found in bucket!")
        else:
            print("\nAvailable videos:")
            for i, video in enumerate(videos):
                status = "✅" if video['under_400mb'] else "❌ TOO LARGE"
                print(str(i+1) + ". " + video['name'] + " (" + str(round(video['size_mb'], 1)) + " MB) " + status)
            
            try:
                selection = int(input("\nSelect video (1-" + str(len(videos)) + "): ")) - 1
                if 0 <= selection < len(videos):
                    selected_video = videos[selection]
                    if selected_video['under_400mb']:
                        print("Processing: " + selected_video['name'])
                        result_file = analyze_new_video(selected_video['name'])
                        if result_file:
                            print("Analysis complete! Now analyzing biomechanics...")
                            analyze_existing_file(result_file)
                    else:
                        print("Selected video is too large (over 400MB)")
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")
    
    elif choice == "3":
        print("\nFetching all videos...")
        videos = list_available_videos()
        processable_videos = [v for v in videos if v['under_400mb']]
        
        if not processable_videos:
            print("No videos under 400MB found!")
        else:
            print("Found " + str(len(processable_videos)) + " videos under 400MB:")
            for video in processable_videos:
                print("  - " + video['name'] + " (" + str(round(video['size_mb'], 1)) + " MB)")
            
            confirm = input("\nProcess all " + str(len(processable_videos)) + " videos? (y/n): ")
            if confirm.lower() == 'y':
                for i, video in enumerate(processable_videos):
                    print("\n=== PROCESSING " + str(i+1) + "/" + str(len(processable_videos)) + ": " + video['name'] + " ===")
                    result_file = analyze_new_video(video['name'])
                    if result_file:
                        print("Video analysis complete! Analyzing biomechanics...")
                        analyze_existing_file(result_file)
                        print("Completed " + video['name'])
                    else:
                        print("Failed to process " + video['name'])
                
                print("\n=== BATCH PROCESSING COMPLETE ===")
                print("Processed " + str(len(processable_videos)) + " videos")
            else:
                print("Batch processing cancelled")
    
    elif choice == "4":
        analysis_files = list_existing_analysis_files()
        
        if not analysis_files:
            print("No analysis files found!")
        else:
            print("\nExisting analysis files:")
            for i, filename in enumerate(analysis_files):
                print(str(i+1) + ". " + filename)
            
            try:
                selection = int(input("\nSelect file (1-" + str(len(analysis_files)) + "): ")) - 1
                if 0 <= selection < len(analysis_files):
                    selected_file = analysis_files[selection]
                    print("Processing: " + selected_file)
                    analyze_existing_file(selected_file)
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")
    
    elif choice == "5":
        analysis_files = list_existing_analysis_files()
        
        if not analysis_files:
            print("No analysis files found!")
        else:
            print("Found " + str(len(analysis_files)) + " analysis files:")
            for filename in analysis_files:
                print("  - " + filename)
            
            confirm = input("\nProcess all " + str(len(analysis_files)) + " analysis files? (y/n): ")
            if confirm.lower() == 'y':
                for i, filename in enumerate(analysis_files):
                    print("\n=== PROCESSING " + str(i+1) + "/" + str(len(analysis_files)) + ": " + filename + " ===")
                    analyze_existing_file(filename)
                    print("Completed " + filename)
                
                print("\n=== BATCH ANALYSIS COMPLETE ===")
                print("Processed " + str(len(analysis_files)) + " files")
            else:
                print("Batch analysis cancelled")
    
    else:
        print("Invalid choice. Exiting.")
