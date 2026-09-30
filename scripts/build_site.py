"""Build the static showcase from verified CVAT outputs."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2

from common import OUTPUT, ROOT, VIDEO

ASSETS = ROOT / "docs" / "assets"
EVIDENCE_FRAMES = (5, 10, 20)


def build() -> None:
    summary = json.loads((OUTPUT / "test_summary.json").read_text(encoding="utf-8"))
    state = json.loads((OUTPUT / "run_state.json").read_text(encoding="utf-8"))
    imported = json.loads((OUTPUT / "round_trip_annotations_api.json").read_text(encoding="utf-8"))
    if summary.get("validation_result") != "PASS" or not all(summary.get("checks", {}).values()):
        raise RuntimeError("A passing live CVAT validation is required before building the site")
    if (
        state.get("validation_result") != "PASS"
        or state.get("source_task_id") != summary.get("source_task_id")
        or state.get("round_trip_task_id") != summary.get("round_trip_task_id")
    ):
        raise RuntimeError("The run state does not match the passing validation summary")
    tracks = imported.get("tracks", [])
    if len(tracks) != 1:
        raise RuntimeError("Expected one imported CVAT track")
    track = tracks[0]
    shapes = {int(shape["frame"]): shape for shape in track["shapes"]}
    ASSETS.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open {VIDEO}")
    evidence = []
    try:
        for frame_id in EVIDENCE_FRAMES:
            annotated = OUTPUT / f"evidence_frame_{frame_id:03d}.jpg"
            if not annotated.is_file() or frame_id not in shapes or shapes[frame_id]["outside"]:
                raise RuntimeError(f"CVAT evidence is missing at frame {frame_id}")
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            success, raw = capture.read()
            if not success:
                raise RuntimeError(f"Cannot decode source frame {frame_id}")
            raw_name = f"source_frame_{frame_id:03d}.jpg"
            if not cv2.imwrite(str(ASSETS / raw_name), raw):
                raise RuntimeError(f"Cannot write {raw_name}")
            shutil.copyfile(annotated, ASSETS / annotated.name)
            evidence.append({
                "frame": frame_id,
                "raw": f"assets/{raw_name}",
                "annotated": f"assets/{annotated.name}",
                "points": [round(float(v), 2) for v in shapes[frame_id]["points"]],
                "mapping": summary["frame_mapping"][str(frame_id)],
            })
    finally:
        capture.release()
    data = {
        "cvatVersion": summary["cvat_version"],
        "pythonVersion": summary["python_version"],
        "sourceTaskId": summary["source_task_id"],
        "sourceJobIds": summary["source_job_ids"],
        "roundTripTaskId": summary["round_trip_task_id"],
        "roundTripJobIds": summary["round_trip_job_ids"],
        "video": summary["video"],
        "annotation": {
            "label": "test_object",
            "trackId": track["id"],
            "trackCount": summary["track_count"],
            "firstFrame": summary["first_annotation_frame"],
            "lastFrame": summary["last_annotation_frame"],
            "outsideFrame": summary["outside_frame"],
            "exportFormat": summary["annotation_format"],
            "importFormat": "CVAT 1.1",
        },
        "checks": summary["checks"],
        "evidence": evidence,
    }
    (ASSETS / "data.js").write_text(
        "window.CVAT_DEMO = " + json.dumps(data, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Built site evidence for CVAT tasks {data['sourceTaskId']} and {data['roundTripTaskId']}")


if __name__ == "__main__":
    build()
