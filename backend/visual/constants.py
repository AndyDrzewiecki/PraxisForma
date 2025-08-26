FONT_SCALE = 0.6
FONT_THICKNESS = 2
LINE_THICKNESS = 2
COLOR_TEXT = (255, 255, 255)      # white
COLOR_BANNER = (32, 86, 171)      # deep blue
COLOR_SKELETON = (57, 197, 187)   # teal
COLOR_RELEASE = (255, 200, 0)     # yellow
COLOR_BAR_BG = (230, 230, 230)
COLOR_BAR_FG = (22, 163, 74)      # green
PADDING = 10
ENDCARD_SECS = 2.5
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

# Skeleton pairs (by landmark names)
SKELETON_EDGES = [
    ("left_shoulder", "right_shoulder"),
    ("left_hip", "right_hip"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]


