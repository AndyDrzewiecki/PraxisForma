#!/usr/bin/env python3
"""
Simple parser for PraxisForma analysis results
Run this in your Cloud Shell to get your first biomechanical insights!
"""

import re
import math

def parse_person_data(filename):
    """Parse your analysis file and extract high-confidence detections"""
    print(f"Reading {filename}...")
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ File {filename} not found")
        return []
    
    persons = []
    lines = content.split('\n')
    current_person = None
    current_landmarks = {}
    
    for line in lines:
        # Look for person headers
        if line.startswith('PERSON '):
            # Save previous person if it was high confidence
            if current_person and current_person.get('confidence', 0) > 0.7:
                current_person['landmarks'] = current_landmarks
                persons.append(current_person)
            
            # Start new person
            person_match = re.match(r'PERSON (\d+):', line)
            if person_match:
                current_person = {'id': int(person_match.group(1))}
                current_landmarks = {}
        
        # Look for confidence
        elif line.startswith('Track confidence:'):
            conf_match = re.search(r'([\d.]+)', line)
            if conf_match and current_person:
                current_person['confidence'] = float(conf_match.group(1))
        
        # Look for landmarks
        elif 'Landmark' in line and 'x=' in line and 'y=' in line:
            landmark_match = re.search(r'Landmark (\d+): x=([\d.]+), y=([\d.]+)', line)
            if landmark_match:
                landmark_id = int(landmark_match.group(1))
                x = float(landmark_match.group(2))
                y = float(landmark_match.group(3))
                current_landmarks[landmark_id] = {'x': x, 'y': y}
    
    # Don't forget the last person
    if current_person and current_person.get('confidence', 0) > 0.7:
        current_person['landmarks'] = current_landmarks
        persons.append(current_person)
    
    return persons

def calculate_shoulder_tilt(landmarks):
    """Calculate shoulder tilt in degrees"""
    if 5 not in landmarks or 6 not in landmarks:
        return None
        
    left_shoulder = landmarks[5]
    right_shoulder = landmarks[6]
    
    height_diff = abs(left_shoulder['y'] - right_shoulder['y'])
    width = abs(left_shoulder['x'] - right_shoulder['x'])
    
    if width > 0:
        angle_rad = math.atan(height_diff / width)
        return math.degrees(angle_rad)
    return 0

def calculate_basic_alignment(landmarks):
    """Basic alignment check - are key joints stacked?"""
    try:
        # Check if ankle, knee, hip are roughly aligned
        ankle = landmarks[16]  # right ankle
        knee = landmarks[14]   # right knee  
        hip = landmarks[12]    # right hip
        
        ankle_knee_diff = abs(ankle['x'] - knee['x'])
        knee_hip_diff = abs(knee['x'] - hip['x'])
        
        # Simple alignment score (lower = better alignment)
        alignment_deviation = ankle_knee_diff + knee_hip_diff
        alignment_score = max(0, 100 - (alignment_deviation * 1000))
        
        return alignment_score
    except:
        return None

def analyze_discus_detection(person):
    """Analyze one person's pose for discus biomechanics"""
    landmarks = person['landmarks']
    
    # Check if we have the key landmarks we need
    required_landmarks = [5, 6, 11, 12, 14, 16]  # shoulders, hips, knee, ankle
    if not all(lm in landmarks for lm in required_landmarks):
        return None
    
    analysis = {}
    
    # Shoulder tilt
    shoulder_tilt = calculate_shoulder_tilt(landmarks)
    if shoulder_tilt is not None:
        analysis['shoulder_tilt'] = shoulder_tilt
    
    # Basic alignment
    alignment = calculate_basic_alignment(landmarks)
    if alignment is not None:
        analysis['alignment_score'] = alignment
    
    return analysis

def main():
    # Try both files, start with the smaller one
    filenames = [
        'analysis_videoplayback_1_20250804_144438.txt',
        'full_analysis_videoplayback_2_20250805_160715.txt'
    ]
    
    for filename in filenames:
        print(f"\n{'='*50}")
        print(f"ANALYZING: {filename}")
        print('='*50)
        
        persons = parse_person_data(filename)
        print(f"Found {len(persons)} high-confidence detections (>0.7)")
        
        if not persons:
            print("❌ No high-confidence detections found")
            continue
        
        # Analyze the top 5 best detections
        persons.sort(key=lambda x: x['confidence'], reverse=True)
        
        print("\n🥏 DISCUS BIOMECHANICAL ANALYSIS:")
        print("-" * 40)
        
        analyzed_count = 0
        for person in persons[:10]:  # Try top 10
            analysis = analyze_discus_detection(person)
            
            if analysis:
                analyzed_count += 1
                print(f"\nPerson {person['id']} (Confidence: {person['confidence']:.3f})")
                
                if 'shoulder_tilt' in analysis:
                    tilt = analysis['shoulder_tilt']
                    print(f"  Shoulder Tilt: {tilt:.1f}°", end="")
                    if tilt < 5:
                        print(" ✅ Excellent")
                    elif tilt < 15:
                        print(" ⚠️ Moderate tilt")
                    else:
                        print(" ❌ Significant tilt")
                
                if 'alignment_score' in analysis:
                    align = analysis['alignment_score']
                    print(f"  Alignment Score: {align:.1f}/100", end="")
                    if align > 80:
                        print(" ✅ Good")
                    elif align > 60:
                        print(" ⚠️ Fair")
                    else:
                        print(" ❌ Poor")
                
                if analyzed_count >= 5:  # Limit output
                    break
        
        if analyzed_count == 0:
            print("❌ Could not analyze any detections (missing required landmarks)")
        else:
            print(f"\n🎉 Successfully analyzed {analyzed_count} detections!")
            print("\n💡 NEXT STEPS:")
            print("- These are your first biomechanical insights!")
            print("- Shoulder tilt shows balance during rotation")
            print("- Alignment shows body stacking for power transfer")
            
        # Only analyze one file for now
        break

if __name__ == "__main__":
    main()
