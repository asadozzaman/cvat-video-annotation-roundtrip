"""Upload a deterministic CVAT rectangle track through the native annotation API."""
from __future__ import annotations

from cvat_sdk.api_client import models

from common import (FIRST, LAST, OUTSIDE, OUTPUT, box, cvat_client, read_state,
                    save_json, setup_logging, task_snapshot)


def upload() -> None:
    state = read_state()
    task_id = int(state["source_task_id"])
    with cvat_client() as client:
        task = client.tasks.retrieve(task_id)
        label_id = int(state["source_label_id"])
        if label_id != next(int(v["id"]) for v in task_snapshot(task)["labels"] if v["name"] == "test_object"):
            raise RuntimeError("Source label ID changed")
        shapes = [models.TrackedShapeRequest(type="rectangle", frame=f, points=box(f),
                   outside=False, occluded=False, z_order=0, rotation=0.0)
                  for f in range(FIRST, LAST + 1)]
        shapes.append(models.TrackedShapeRequest(type="rectangle", frame=OUTSIDE,
                      points=box(OUTSIDE), outside=True, occluded=False, z_order=0, rotation=0.0))
        track = models.LabeledTrackRequest(label_id=label_id, frame=FIRST, shapes=shapes,
                                           group=0, source="manual")
        task.set_annotations(models.LabeledDataRequest(version=0, tags=[], shapes=[], tracks=[track]))
        fetched = task.get_annotations()
        data = fetched.to_dict()
        save_json(OUTPUT / "source_annotations_api.json", data)
        if len(data.get("tracks", [])) != 1:
            raise RuntimeError(f"CVAT returned {len(data.get('tracks', []))} tracks after upload")
        print(f"CVAT accepted 1 track, frames {FIRST}-{LAST}, outside at {OUTSIDE}")


if __name__ == "__main__":
    setup_logging()
    upload()
