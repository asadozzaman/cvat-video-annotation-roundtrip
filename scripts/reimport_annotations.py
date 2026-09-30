"""Import the exact CVAT export into a newly created video task."""
from __future__ import annotations

from common import (EXPORT, IMPORT_FORMAT, OUTPUT, create_video_task, cvat_client,
                    find_label_id, read_state, save_json, setup_logging,
                    task_snapshot, write_state)


def reimport() -> None:
    if not EXPORT.is_file():
        raise FileNotFoundError(f"Run export_annotations.py first: {EXPORT}")
    state = read_state()
    if state.get("export_source_task_id") != state.get("source_task_id"):
        raise RuntimeError("Export does not belong to the current source task")
    with cvat_client() as client:
        task = create_video_task(client, "CVAT Mini Test - Round Trip")
        snapshot = task_snapshot(task)
        label_id = find_label_id(snapshot)
        job_ids = [int(job["id"]) for job in snapshot["jobs"]]
        if not job_ids:
            raise RuntimeError(f"Round-trip task {task.id} has no jobs")
        save_json(OUTPUT / "round_trip_task_metadata.json", snapshot)
        write_state(round_trip_task_id=task.id, round_trip_job_ids=job_ids,
                    round_trip_label_id=label_id, import_completed=False,
                    import_source_task_id=None)
        task.import_annotations(IMPORT_FORMAT, EXPORT, status_check_period=3)
        data = task.get_annotations().to_dict()
        save_json(OUTPUT / "round_trip_annotations_api.json", data)
        if len(data.get("tracks", [])) != 1:
            raise RuntimeError(f"Round-trip task has {len(data.get('tracks', []))} tracks")
        write_state(import_completed=True, import_source_task_id=state["source_task_id"])
        print(f"Imported {EXPORT.name} into task {task.id}, jobs {job_ids}; retrieved 1 track")


if __name__ == "__main__":
    setup_logging()
    reimport()
