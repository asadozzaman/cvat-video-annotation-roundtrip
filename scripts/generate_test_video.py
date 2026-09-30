"""Produce and inspect a deterministic, visibly numbered MP4."""
from __future__ import annotations

import cv2
import numpy as np

from common import FPS, FRAMES, HEIGHT, VIDEO, WIDTH, box, setup_logging


def generate() -> None:
    VIDEO.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(VIDEO), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open the MP4 writer")
    try:
        for frame_id in range(FRAMES):
            frame = np.full((HEIGHT, WIDTH, 3), (28, 32, 38), dtype=np.uint8)
            x1, y1, x2, y2 = map(int, box(frame_id))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 180, 255), -1)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 255, 255), 2)
            cv2.putText(frame, f"VIDEO FRAME: {frame_id:03d}", (35, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, "SOURCE INDEX (ZERO BASED)", (35, 315),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (180, 210, 230), 2, cv2.LINE_AA)
            writer.write(frame)
    finally:
        writer.release()
    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        raise RuntimeError("Generated MP4 could not be reopened")
    actual = (int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS),
              int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    expected = (FRAMES, float(FPS), WIDTH, HEIGHT)
    if actual != expected:
        raise RuntimeError(f"Encoded video metadata {actual} differs from {expected}")
    print(f"Verified {VIDEO}: {FRAMES} frames, {FPS} FPS, {WIDTH}x{HEIGHT}, {FRAMES/FPS:.1f}s")


if __name__ == "__main__":
    setup_logging()
    generate()
