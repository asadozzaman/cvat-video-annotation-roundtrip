"""Overlay annotations retrieved from the round-trip CVAT task on source frames."""
from __future__ import annotations

import cv2

from common import LABEL, OUTPUT, VIDEO, cvat_client, read_state, setup_logging


def generate() -> None:
    state = read_state()
    with cvat_client() as client:
        task = client.tasks.retrieve(int(state["round_trip_task_id"]))
        tracks = task.get_annotations().to_dict().get("tracks", [])
        if len(tracks) != 1:
            raise RuntimeError(f"Expected one imported track, found {len(tracks)}")
        track = tracks[0]
        shapes = {int(shape["frame"]): shape for shape in track["shapes"]}
        cap = cv2.VideoCapture(str(VIDEO))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open source video {VIDEO}")
        try:
            for index in (5, 10, 20):
                cap.set(cv2.CAP_PROP_POS_FRAMES, index)
                ok, frame = cap.read()
                if not ok or index not in shapes or shapes[index]["outside"]:
                    raise RuntimeError(f"Missing visible round-trip annotation at frame {index}")
                points = [int(round(v)) for v in shapes[index]["points"]]
                cv2.rectangle(frame, (points[0], points[1]), (points[2], points[3]), (0, 255, 0), 3)
                cv2.putText(frame, f"SOURCE FRAME: {index}  CVAT FRAME: {index}", (25, 225),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, f"TRACK: {track['id']}  LABEL: {LABEL}", (25, 255),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
                output = OUTPUT / f"evidence_frame_{index:03d}.jpg"
                if not cv2.imwrite(str(output), frame):
                    raise RuntimeError(f"Cannot write {output}")
                print(f"Wrote {output}")
        finally:
            cap.release()


if __name__ == "__main__":
    setup_logging()
    generate()
