import cv2


def blur_faces_in_video(input_path: str, output_path: str) -> None:
    cap = cv2.VideoCapture(input_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        boxes = face.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5)
        if len(boxes) == 0:
            # Conservative top-band blur if no detection
            band_h = max(1, height // 6)
            roi = frame[0:band_h, 0:width]
            roi = cv2.GaussianBlur(roi, (31, 31), 0)
            frame[0:band_h, 0:width] = roi
        else:
            for (x, y, w, h) in boxes:
                pad = int(0.15 * max(w, h))
                x0 = max(0, x - pad)
                y0 = max(0, y - pad)
                x1 = min(width, x + w + pad)
                y1 = min(height, y + h + pad)
                roi = frame[y0:y1, x0:x1]
                roi = cv2.GaussianBlur(roi, (31, 31), 0)
                frame[y0:y1, x0:x1] = roi
        writer.write(frame)

    cap.release()
    writer.release()


