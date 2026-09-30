"""Shared configuration, geometry, CVAT access, and artifact helpers."""
from __future__ import annotations

import json
import logging
import os
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.request import urlopen
from xml.etree import ElementTree as ET

from cvat_sdk import make_client
from cvat_sdk.api_client import models
from cvat_sdk.core.client import Client
from dotenv import load_dotenv
from urllib3 import Timeout

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / "sample/input/synthetic_tracking.mp4"
OUTPUT = ROOT / "sample/output"
STATE = OUTPUT / "run_state.json"
EXPORT = OUTPUT / "source_annotations.zip"
XML = OUTPUT / "source_annotations.xml"
ROUND_EXPORT = OUTPUT / "round_trip_annotations.zip"
ROUND_XML = OUTPUT / "round_trip_annotations.xml"
WIDTH, HEIGHT, FPS, FRAMES = 640, 360, 10, 60
FIRST, LAST, OUTSIDE = 5, 20, 21
LABEL = "test_object"
FORMAT = "CVAT for video 1.1"
IMPORT_FORMAT = "CVAT 1.1"
LOG = logging.getLogger("cvat_mini_test")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def box(frame: int) -> list[float]:
    """Visible rectangle, with CVAT's [xtl, ytl, xbr, ybr] geometry."""
    x, y, w, h = 80 + frame * 4, 120, 90, 60
    return [float(x), float(y), float(x + w), float(y + h)]


def read_state() -> dict[str, Any]:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def write_state(**values: Any) -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    state = read_state()
    state.update(values)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state


def export_zip(task: Any, destination: Path) -> None:
    """Download to a task-owned temporary path, then replace an older export."""
    temporary = destination.with_suffix(destination.suffix + ".download")
    temporary.unlink(missing_ok=True)
    try:
        task.export_dataset(FORMAT, temporary, include_images=False, status_check_period=3)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError(f"CVAT export was not downloaded: {temporary}")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def save_json(path: Path, data: Any) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def model_dict(model: Any) -> dict[str, Any]:
    return model.to_dict() if hasattr(model, "to_dict") else dict(model)


@contextmanager
def cvat_client() -> Iterator[Client]:
    load_dotenv(ROOT / ".env")
    host = os.getenv("CVAT_BASE_URL", "http://localhost:8080").rstrip("/")
    token = os.getenv("CVAT_TOKEN", "").strip()
    username = os.getenv("CVAT_USERNAME", "").strip()
    password = os.getenv("CVAT_PASSWORD", "")
    if not token and not (username and password):
        raise RuntimeError("Set CVAT_TOKEN or CVAT_USERNAME and CVAT_PASSWORD in .env")
    try:
        with urlopen(f"{host}/api/server/about", timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"CVAT returned HTTP {response.status} before login")
    except Exception as exc:
        raise RuntimeError(f"CVAT is unavailable at {host}: {exc}") from exc
    kwargs = {"access_token": token} if token else {"credentials": (username, password)}
    with make_client(host, **kwargs) as client:
        pool = client.api_client.rest_client.pool_manager
        pool.connection_pool_kw["timeout"] = Timeout(connect=10, read=120)
        pool.clear()
        if os.getenv("CVAT_ORGANIZATION", "").strip():
            client.organization_slug = os.environ["CVAT_ORGANIZATION"].strip()
        # The SDK's default background-request waiter has no deadline. Replace it
        # with a bounded poller while retaining the SDK upload/download machinery.
        def wait_bounded(rq_id: str, *, status_check_period: int | None = None,
                         log_prefix: str | None = None):
            deadline = time.monotonic() + 600
            period = status_check_period or 3
            while time.monotonic() < deadline:
                request, response = client.api_client.requests_api.retrieve(rq_id, _request_timeout=30)
                status = str(request.status.value).lower()
                LOG.info("%s: %s", log_prefix or f"Request {rq_id}", status)
                if status == "finished":
                    return request, response
                if status == "failed":
                    raise RuntimeError(f"CVAT request {rq_id} failed: {request.message}")
                time.sleep(period)
            raise TimeoutError(f"CVAT request {rq_id} exceeded 600 seconds")
        client.wait_for_completion = wait_bounded
        yield client


def server_info(client: Client) -> dict[str, Any]:
    about, _ = client.api_client.server_api.retrieve_about(_request_timeout=30)
    formats, _ = client.api_client.server_api.retrieve_annotation_formats(_request_timeout=30)
    about_data = model_dict(about)
    formats_data = model_dict(formats)
    return {"about": about_data, "formats": formats_data}


def ensure_format(client: Client) -> None:
    data = server_info(client)["formats"]
    exporters = {entry["name"] for entry in data["exporters"]}
    importers = {entry["name"] for entry in data["importers"]}
    if FORMAT not in exporters or IMPORT_FORMAT not in importers:
        raise RuntimeError(f"Required format missing: export {FORMAT in exporters}, import {IMPORT_FORMAT in importers}")


def create_video_task(client: Client, name: str):
    if not VIDEO.exists():
        raise FileNotFoundError(f"Generate video first: {VIDEO}")
    task = client.tasks.create_from_data(
        spec=models.TaskWriteRequest(name=name, labels=[models.PatchedLabelRequest(name=LABEL)]),
        resources=[VIDEO], data_params={"image_quality": 90}, status_check_period=3,
    )
    if task.size != FRAMES:
        raise RuntimeError(f"Task {task.id} has {task.size} frames; expected {FRAMES}")
    return task


def task_snapshot(task) -> dict[str, Any]:
    task.fetch()
    task_data = model_dict(task._model)
    meta = model_dict(task.get_meta())
    jobs = [model_dict(job._model) for job in task.get_jobs()]
    labels = [model_dict(label) for label in task.get_labels()]
    task_fields = ("id", "name", "size", "status", "mode", "dimension", "media_type")
    job_fields = ("id", "task_id", "start_frame", "stop_frame", "frame_count", "type", "status")
    label_fields = ("id", "name", "type")
    meta_fields = ("size", "start_frame", "stop_frame", "frame_filter", "frames")
    return {
        "task": {key: task_data.get(key) for key in task_fields},
        "data_meta": {key: meta.get(key) for key in meta_fields},
        "jobs": [{key: job.get(key) for key in job_fields} for job in jobs],
        "labels": [{key: label.get(key) for key in label_fields} for label in labels],
    }


def find_label_id(snapshot: dict[str, Any]) -> int:
    matches = [entry["id"] for entry in snapshot["labels"] if entry["name"] == LABEL]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {LABEL} label, found {len(matches)}")
    return int(matches[0])


def annotations_dict(task) -> dict[str, Any]:
    return model_dict(task.get_annotations())


def parse_xml(path: Path = XML) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    if root.tag != "annotations":
        raise ValueError(f"Unexpected XML root: {root.tag}")
    tracks = []
    for track in root.findall("track"):
        tracks.append({
            "id": int(track.attrib["id"]),
            "label": track.attrib["label"],
            "boxes": [{"frame": int(box.attrib["frame"]),
                       "outside": box.attrib.get("outside") == "1",
                       "keyframe": box.attrib.get("keyframe") == "1",
                       "occluded": box.attrib.get("occluded") == "1",
                       "points": [float(box.attrib[k]) for k in ("xtl", "ytl", "xbr", "ybr")]}
                      for box in track.findall("box")],
        })
    return {"version": root.findtext("version"),
            "task_name": root.findtext("meta/task/name"),
            "size": root.findtext("meta/task/size"),
            "labels": [e.text for e in root.findall("meta/task/labels/label/name")],
            "tracks": tracks}


def extract_xml(archive: Path = EXPORT, destination: Path = XML) -> Path:
    if not zipfile.is_zipfile(archive):
        raise ValueError(f"CVAT export is not a ZIP archive: {archive}")
    with zipfile.ZipFile(archive) as zf:
        xml_names = [name for name in zf.namelist() if name.endswith(".xml")]
        if len(xml_names) != 1:
            raise ValueError(f"Expected one XML file in CVAT export, found {xml_names}")
        destination.write_bytes(zf.read(xml_names[0]))
    return destination
