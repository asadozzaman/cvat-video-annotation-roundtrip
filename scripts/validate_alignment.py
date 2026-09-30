"""Validate video, live CVAT tasks, CVAT XML, and the clean-task round trip."""
from __future__ import annotations

import platform
import sys
from pathlib import Path

import cv2
import numpy as np

from common import (EXPORT, FIRST, FORMAT, FPS, FRAMES, HEIGHT, LABEL, LAST,
                    OUTSIDE, OUTPUT, ROUND_EXPORT, ROUND_XML, VIDEO, WIDTH, box, cvat_client, export_zip, extract_xml,
                    parse_xml, read_state, save_json, setup_logging, task_snapshot,
                    write_state)


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"{name}: {'PASS' if condition else 'FAIL'}{f' - {detail}' if detail else ''}")
    return bool(condition)


def read_video() -> tuple[list[np.ndarray], dict]:
    cap = cv2.VideoCapture(str(VIDEO))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open {VIDEO}")
    meta = {"frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames, meta


def normalized_track(data: dict) -> list[dict]:
    tracks = data.get("tracks", [])
    if len(tracks) != 1:
        return []
    return [{"frame": int(shape["frame"]),
             "type": shape["type"],
             "outside": bool(shape.get("outside", False)),
             "occluded": bool(shape.get("occluded", False)),
             "keyframe": shape.get("keyframe"),
             "points": [float(v) for v in shape["points"]]}
            for shape in tracks[0].get("shapes", [])]


def geometry_ok(shapes: list[dict]) -> bool:
    if [s["frame"] for s in shapes] != list(range(FIRST, OUTSIDE + 1)):
        return False
    for shape in shapes:
        frame = shape["frame"]
        if shape.get("type", "rectangle") != "rectangle":
            return False
        if not np.allclose(shape["points"], box(frame), atol=0.01, rtol=0):
            return False
        if shape["outside"] != (frame == OUTSIDE) or shape["occluded"]:
            return False
    return True


def xml_shapes(parsed: dict) -> list[dict]:
    return parsed["tracks"][0]["boxes"] if len(parsed["tracks"]) == 1 else []


def closest_source_frame(cvat_frame: np.ndarray, source_frames: list[np.ndarray]) -> tuple[int, float]:
    # Resize for comparison; CVAT may recompress the video, so exact bytes are not expected.
    target = cv2.resize(cvat_frame, (160, 90)).astype(np.int32)
    errors = []
    for frame in source_frames:
        source = cv2.resize(frame, (160, 90)).astype(np.int32)
        errors.append(float(np.mean((target - source) ** 2)))
    index = int(np.argmin(errors))
    return index, errors[index]


def run() -> int:
    results: dict[str, bool] = {}
    state = read_state()
    try:
        results["VIDEO OPEN"] = check("VIDEO OPEN", VIDEO.is_file())
        frames, video = read_video()
        results["VIDEO FRAME COUNT"] = check("VIDEO FRAME COUNT", video["frames"] == FRAMES and len(frames) == FRAMES)
        results["VIDEO FPS"] = check("VIDEO FPS", abs(video["fps"] - FPS) < 0.01)
        results["VIDEO WIDTH"] = check("VIDEO WIDTH", video["width"] == WIDTH)
        results["VIDEO HEIGHT"] = check("VIDEO HEIGHT", video["height"] == HEIGHT)
        results["VIDEO DURATION"] = check("VIDEO DURATION", abs(len(frames) / video["fps"] - 6.0) < 0.01)
        results["EXPORT EXISTS"] = check("EXPORT EXISTS", EXPORT.is_file() and EXPORT.stat().st_size > 0)
        results["EXPORT TASK ID"] = check("EXPORT TASK ID", state.get("export_source_task_id") == state.get("source_task_id"))
        parsed = parse_xml(extract_xml())
        results["EXPORT PARSE"] = check("EXPORT PARSE", parsed["version"] == "1.1" and parsed["size"] == str(FRAMES) and len(parsed["tracks"]) == 1)
        xml = xml_shapes(parsed)
        results["EXPORTED FRAME IDS"] = check("EXPORTED FRAME IDS", [s["frame"] for s in xml] == list(range(FIRST, OUTSIDE + 1)))
        results["EXPORTED COORDINATES"] = check("EXPORTED COORDINATES", geometry_ok(xml))
        results["EXPORTED LABEL"] = check("EXPORTED LABEL", parsed["tracks"][0]["label"] == LABEL and LABEL in parsed["labels"])
        results["EXPORTED KEYFRAMES"] = check("EXPORTED KEYFRAMES", all(s["keyframe"] for s in xml))
        with cvat_client() as client:
            source_id = int(state["source_task_id"])
            round_id = int(state["round_trip_task_id"])
            source = client.tasks.retrieve(source_id)
            round_trip = client.tasks.retrieve(round_id)
            source_meta = task_snapshot(source)
            round_meta = task_snapshot(round_trip)
            source_data = source.get_annotations().to_dict()
            round_data = round_trip.get_annotations().to_dict()
            export_zip(round_trip, ROUND_EXPORT)
            round_parsed = parse_xml(extract_xml(ROUND_EXPORT, ROUND_XML))
            round_xml = xml_shapes(round_parsed)
            source_shapes = normalized_track(source_data)
            round_shapes = normalized_track(round_data)
            results["SOURCE TASK FRAME COUNT"] = check("SOURCE TASK FRAME COUNT", source.size == FRAMES and int(source_meta["data_meta"]["size"]) == FRAMES)
            results["ROUND TRIP TASK FRAME COUNT"] = check("ROUND TRIP TASK FRAME COUNT", round_trip.size == FRAMES and int(round_meta["data_meta"]["size"]) == FRAMES)
            results["SOURCE TASK STATUS"] = check("SOURCE TASK STATUS", source_meta["task"]["status"] == "annotation" and source_meta["task"]["mode"] == "interpolation")
            results["ROUND TRIP TASK STATUS"] = check("ROUND TRIP TASK STATUS", round_meta["task"]["status"] == "annotation" and round_meta["task"]["mode"] == "interpolation")
            results["SOURCE FRAME SIZE"] = check("SOURCE FRAME SIZE", all(f["width"] == WIDTH and f["height"] == HEIGHT for f in source_meta["data_meta"]["frames"]))
            results["ROUND TRIP FRAME SIZE"] = check("ROUND TRIP FRAME SIZE", all(f["width"] == WIDTH and f["height"] == HEIGHT for f in round_meta["data_meta"]["frames"]))
            results["SOURCE JOB"] = check("SOURCE JOB", bool(source_meta["jobs"]) and [j["id"] for j in source_meta["jobs"]] == state["source_job_ids"] and source_meta["jobs"][0]["start_frame"] == 0 and source_meta["jobs"][0]["stop_frame"] == FRAMES - 1)
            results["ROUND TRIP JOB"] = check("ROUND TRIP JOB", bool(round_meta["jobs"]) and [j["id"] for j in round_meta["jobs"]] == state["round_trip_job_ids"] and round_meta["jobs"][0]["start_frame"] == 0 and round_meta["jobs"][0]["stop_frame"] == FRAMES - 1)
            results["SOURCE LABEL"] = check("SOURCE LABEL", any(x["name"] == LABEL and x["id"] == state["source_label_id"] for x in source_meta["labels"]))
            results["ROUND TRIP LABEL"] = check("ROUND TRIP LABEL", any(x["name"] == LABEL and x["id"] == state["round_trip_label_id"] for x in round_meta["labels"]))
            results["SOURCE TRACK COUNT"] = check("SOURCE TRACK COUNT", len(source_data.get("tracks", [])) == 1)
            results["SOURCE TRACK LABEL"] = check("SOURCE TRACK LABEL", len(source_data.get("tracks", [])) == 1 and source_data["tracks"][0]["label_id"] == state["source_label_id"])
            results["SOURCE TRACK GEOMETRY"] = check("SOURCE TRACK GEOMETRY", geometry_ok(source_shapes))
            results["ROUND TRIP IMPORT"] = check("ROUND TRIP IMPORT", state.get("import_completed") is True and state.get("import_source_task_id") == source_id and len(round_data.get("tracks", [])) == 1)
            results["ROUND TRIP TRACK LABEL"] = check("ROUND TRIP TRACK LABEL", len(round_data.get("tracks", [])) == 1 and round_data["tracks"][0]["label_id"] == state["round_trip_label_id"])
            results["ROUND TRIP FRAME IDS"] = check("ROUND TRIP FRAME IDS", [s["frame"] for s in round_shapes] == [s["frame"] for s in source_shapes] == [s["frame"] for s in xml])
            results["ROUND TRIP COORDINATES"] = check("ROUND TRIP COORDINATES", geometry_ok(round_shapes) and all(np.allclose(a["points"], b["points"], atol=0.01, rtol=0) for a, b in zip(source_shapes, round_shapes)))
            results["ROUND TRIP EXPORTED KEYFRAMES"] = check("ROUND TRIP EXPORTED KEYFRAMES", len(round_xml) == len(xml) and all(s["keyframe"] for s in round_xml) and all(a["frame"] == b["frame"] and a["outside"] == b["outside"] and np.allclose(a["points"], b["points"], atol=0.01, rtol=0) for a, b in zip(xml, round_xml)))
            mappings = {}
            for index in (5, 10, 20):
                content = source.get_frame(index, quality="original").read()
                cvat_frame = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
                if cvat_frame is None:
                    raise RuntimeError(f"CVAT frame {index} could not be decoded")
                nearest, error = closest_source_frame(cvat_frame, frames)
                mappings[str(index)] = {"cvat_api_frame": index, "closest_source_frame": nearest,
                                        "mean_squared_error": error}
                results[f"FRAME {index} MAPPING"] = check(f"FRAME {index} MAPPING", nearest == index and error < 10 and cvat_frame.shape[:2] == (HEIGHT, WIDTH) and any(s["frame"] == index and not s["outside"] for s in source_shapes), f"closest source frame {nearest}")
            results["FRAME INDEXING"] = check("FRAME INDEXING", all(m["cvat_api_frame"] == m["closest_source_frame"] for m in mappings.values()) and all(s["frame"] == s2["frame"] for s, s2 in zip(source_shapes, xml)))
            about = state.get("cvat_about", {})
            summary = {"cvat_version": about.get("version"), "python_version": platform.python_version(),
                       "source_task_id": source_id, "source_job_ids": state["source_job_ids"],
                       "round_trip_task_id": round_id, "round_trip_job_ids": state["round_trip_job_ids"],
                       "video": {**video, "duration_seconds": len(frames) / video["fps"]},
                       "annotation_format": FORMAT, "track_count": len(source_data.get("tracks", [])),
                       "first_annotation_frame": FIRST, "last_annotation_frame": LAST,
                       "outside_frame": OUTSIDE, "frame_mapping": mappings, "checks": results}
    except Exception as exc:
        print(f"VALIDATION ERROR: {type(exc).__name__}: {exc}")
        results["VALIDATION ERROR"] = False
        summary = {"checks": results, "error": f"{type(exc).__name__}: {exc}"}
    passed = bool(results) and all(results.values())
    summary["validation_result"] = "PASS" if passed else "FAIL"
    save_json(OUTPUT / "test_summary.json", summary)
    write_state(validation_result=summary["validation_result"])
    print(f"FINAL RESULT: {summary['validation_result']}")
    return 0 if passed else 1


if __name__ == "__main__":
    setup_logging()
    sys.exit(run())
