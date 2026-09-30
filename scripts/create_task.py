"""Create and inspect the source CVAT video task."""
from __future__ import annotations

from pathlib import Path

from common import (OUTPUT, create_video_task, cvat_client, find_label_id,
                    save_json, server_info, setup_logging, task_snapshot, write_state)


def create(name: str = "CVAT Mini Test - Source", role: str = "source") -> int:
    with cvat_client() as client:
        info = server_info(client)
        print(f"CVAT server: {info['about']}")
        task = create_video_task(client, name)
        snapshot = task_snapshot(task)
        label_id = find_label_id(snapshot)
        job_ids = [int(job["id"]) for job in snapshot["jobs"]]
        if not job_ids:
            raise RuntimeError(f"Task {task.id} has no jobs after ingestion")
        save_json(OUTPUT / f"{role}_task_metadata.json", snapshot)
        values = {f"{role}_task_id": task.id, f"{role}_job_ids": job_ids,
                  f"{role}_label_id": label_id, "cvat_about": info["about"]}
        if role == "source":
            values.update(round_trip_task_id=None, round_trip_job_ids=[],
                          round_trip_label_id=None, import_completed=False,
                          export_source_task_id=None, import_source_task_id=None,
                          validation_result=None)
        write_state(**values)
        print(f"Task {task.id}: {task.name}, {task.size} frames, label {label_id}, jobs {job_ids}")
        return task.id


if __name__ == "__main__":
    setup_logging()
    create()
