"""Offline regression checks for the published experiment; no live CVAT claim."""
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "sample" / "output"


def read_json(name):
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


class RecordedEvidenceTests(unittest.TestCase):
    def test_summary_matches_run_and_site(self):
        summary = read_json("test_summary.json")
        state = read_json("run_state.json")
        self.assertEqual(summary["validation_result"], "PASS")
        self.assertEqual(state["validation_result"], "PASS")
        self.assertEqual(len(summary["checks"]), 35)
        self.assertTrue(all(value is True for value in summary["checks"].values()))
        for key in ("source_task_id", "round_trip_task_id"):
            self.assertEqual(summary[key], state[key])
        site_text = (ROOT / "docs/assets/data.js").read_text(encoding="utf-8")
        site = json.loads(site_text.removeprefix("window.CVAT_DEMO = ").strip().removesuffix(";"))
        self.assertEqual(site["checks"], summary["checks"])
        self.assertEqual(site["sourceTaskId"], summary["source_task_id"])
        self.assertEqual(site["roundTripTaskId"], summary["round_trip_task_id"])
        self.assertEqual(site["video"], summary["video"])

    def test_api_and_xml_geometry_agree(self):
        for prefix in ("source", "round_trip"):
            with self.subTest(prefix=prefix):
                api = read_json(f"{prefix}_annotations_api.json")
                self.assertEqual(len(api["tracks"]), 1)
                shapes = api["tracks"][0]["shapes"]
                tree = ET.parse(OUTPUT / f"{prefix}_annotations.xml")
                tracks = tree.findall("track")
                self.assertEqual(len(tracks), 1)
                self.assertEqual(tracks[0].get("label"), "test_object")
                boxes = tracks[0].findall("box")
                self.assertEqual([s["frame"] for s in shapes], list(range(5, 22)))
                self.assertEqual([int(b.get("frame")) for b in boxes], list(range(5, 22)))
                for shape, box in zip(shapes, boxes):
                    frame = shape["frame"]
                    expected = [80 + 4 * frame, 120, 170 + 4 * frame, 180]
                    self.assertEqual(shape["points"], expected)
                    self.assertEqual([float(box.get(k)) for k in ("xtl", "ytl", "xbr", "ybr")], expected)
                    self.assertEqual(shape["outside"], frame == 21)
                    self.assertEqual(box.get("outside"), "1" if frame == 21 else "0")
                    self.assertFalse(shape["occluded"])
                    self.assertEqual(box.get("occluded"), "0")
                    self.assertEqual(box.get("keyframe"), "1")

    def test_metadata_and_label_identity(self):
        summary = read_json("test_summary.json")
        for prefix in ("source", "round_trip"):
            meta = read_json(f"{prefix}_task_metadata.json")
            api = read_json(f"{prefix}_annotations_api.json")
            self.assertEqual(meta["task"]["id"], summary[f"{prefix}_task_id"])
            self.assertEqual(meta["task"]["size"], 60)
            self.assertEqual(meta["data_meta"]["start_frame"], 0)
            self.assertEqual(meta["data_meta"]["stop_frame"], 59)
            self.assertEqual(meta["labels"][0]["name"], "test_object")
            self.assertEqual(api["tracks"][0]["label_id"], meta["labels"][0]["id"])

    def test_frame_mapping_and_published_images(self):
        summary = read_json("test_summary.json")
        self.assertEqual(set(summary["frame_mapping"]), {"5", "10", "20"})
        for frame in (5, 10, 20):
            mapping = summary["frame_mapping"][str(frame)]
            self.assertEqual(mapping["cvat_api_frame"], frame)
            self.assertEqual(mapping["closest_source_frame"], frame)
            name = f"evidence_frame_{frame:03d}.jpg"
            self.assertEqual((OUTPUT / name).read_bytes(), (ROOT / "docs/assets" / name).read_bytes())
            self.assertGreater((ROOT / "docs/assets" / f"source_frame_{frame:03d}.jpg").stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
