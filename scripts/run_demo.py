"""Run each real CVAT integration step in order and stop on failure."""
from __future__ import annotations

from create_task import create
from export_annotations import export
from generate_test_video import generate
from generate_visual_evidence import generate as generate_evidence
from reimport_annotations import reimport
from upload_annotations import upload
from validate_alignment import run as validate


def main() -> int:
    generate()
    create()
    upload()
    export()
    reimport()
    result = validate()
    if result == 0:
        generate_evidence()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
