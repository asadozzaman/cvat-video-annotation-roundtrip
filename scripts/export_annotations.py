"""Export CVAT for video 1.1 and parse the server-generated XML."""
from __future__ import annotations

from common import (EXPORT, FORMAT, OUTPUT, cvat_client, ensure_format, export_zip, extract_xml,
                    parse_xml, read_state, save_json, setup_logging, write_state)


def export() -> None:
    task_id = int(read_state()["source_task_id"])
    with cvat_client() as client:
        ensure_format(client)
        task = client.tasks.retrieve(task_id)
        export_zip(task, EXPORT)
    extract_xml()
    parsed = parse_xml()
    if len(parsed["tracks"]) != 1:
        raise RuntimeError(f"Exported XML contains {len(parsed['tracks'])} tracks")
    save_json(OUTPUT / "export_parsed.json", parsed)
    write_state(annotation_format=FORMAT, export_file=EXPORT.name,
                export_source_task_id=task_id)
    print(f"Parsed CVAT export version {parsed['version']}: "
          f"{len(parsed['tracks'])} track, {len(parsed['tracks'][0]['boxes'])} boxes")


if __name__ == "__main__":
    setup_logging()
    export()
