# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure P09 input/cache safety tests; no Blender installation is required.

Run from the repository root:
  python -m unittest discover -s tools/omega -p 'test_phase09_*.py' -v
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "full-app/scripts/omega/phase09_vfx.py"
spec = importlib.util.spec_from_file_location("omega_phase09_vfx", FILE)
vfx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vfx)


class GradeContractTests(unittest.TestCase):
    def test_pure_import_and_exact_operations(self):
        self.assertEqual(vfx.CONTRACT_VERSION, "RENDER-OMEGA-1")
        self.assertEqual(vfx.OPERATION_NAMES, ("omega.vfx.create_grade", "omega.vfx.cache_inspect"))
        result = vfx.validate("omega.vfx.create_grade", {"object": "Cube"})
        self.assertEqual(result["mode"], "FINAL")
        self.assertEqual(result["object"], "Cube")
        self.assertEqual(result["base_color"], [0.55, 0.4, 0.25])

    def test_reject_invalid_payloads_without_bpy(self):
        invalid = (
            {}, {"object": "x", "code": "__import__('os')"},
            {"object": "../../secrets"}, {"object": "Cube", "gamma": float("nan")},
            {"object": "Cube", "contrast": float("inf")},
            {"object": "Cube", "roughness": -1},
            {"object": "Cube", "bump_strength": 2},
            {"object": "Cube", "replace_first_slot": 1},
            {"object": "Cube", "mode": "PREVIEW"},
            {"object": "Cube", "base_color": [0.1, 0.2, True]},
            {"object": "Cube", "expected_scene_revision": "garbage"},
            {"object": "Cube", "view_layer": "View Layer/../../"},
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                vfx.validate("omega.vfx.create_grade", payload)
        with self.assertRaisesRegex(ValueError, "INVALID_ARGUMENTS"):
            vfx.validate("omega.vfx.pretend_blender", {})

    def test_cache_payload_limits(self):
        p = vfx.validate("omega.vfx.cache_inspect", {"cache_id": "Water01", "frame_start": 11, "frame_end": 14})
        self.assertEqual((p["frame_start"], p["frame_end"]), (11, 14))
        for payload in ({"cache_id": "../../etc"}, {"cache_id": "ab", "path": "/tmp/evil"},
                        {"cache_id": "C", "frame_start": 101, "frame_end": 100},
                        {"cache_id": "C", "frame_start": 1, "frame_end": 242},
                        {"cache_id": "C", "frame_start": True}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                vfx.validate("omega.vfx.cache_inspect", payload)

    def test_native_fail_closed_without_scene(self):
        with self.assertRaisesRegex(ValueError, "native scene required"):
            vfx.execute("omega.vfx.create_grade", {"object": "Cube"}, {})
        with self.assertRaisesRegex(ValueError, "native scene required"):
            vfx.audit("omega.vfx.create_grade", {"object": "Cube"}, {})


class NativeCacheInterchangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Production"
        self.folder = self.root / "omega_vfx_caches" / "WaterA"
        self.folder.mkdir(parents=True)
        self.framebytes = b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n"
        self.sha = hashlib.sha256(self.framebytes).hexdigest()
        self.frames = []
        for number in (1, 2, 3):
            filename = "frame_%06d.obj" % number
            (self.folder / filename).write_bytes(self.framebytes)
            self.frames.append({"frame": number, "filename": filename, "sha256": self.sha,
                                "bytes": len(self.framebytes), "kind": "mesh"})
        self.manifest = {"cache_id": "WaterA", "source_revision": "c" * 64, "frames": self.frames}
        self.write_manifest()
        self.payload = {"cache_id": "WaterA", "frame_start": 1, "frame_end": 3}
        self.context = {"production_root": self.root}

    def write_manifest(self):
        (self.folder / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def test_verified_cache_explicitly_not_a_simulation_or_import(self):
        receipt = vfx.execute("omega.vfx.cache_inspect", self.payload, self.context)
        self.assertEqual(receipt["state"], "succeeded")
        self.assertFalse(receipt["native_execution_verified"])
        self.assertFalse(receipt["quality_reduced"])
        self.assertEqual(receipt["details"]["verified_frames"], 3)
        self.assertFalse(receipt["details"]["native_simulation_executed"])
        self.assertFalse(receipt["details"]["cache_imported_into_blender"])
        self.assertEqual(receipt["details"]["frames"][1]["sha256"], self.sha)

    def test_hash_mismatch_is_not_completed(self):
        (self.folder / "frame_000002.obj").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_CONFLICT"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)

    def test_missing_frame_and_duplicate_manifest_entry(self):
        self.frames.pop()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "MISSING_REFERENCE"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)
        self.frames.append(dict(self.frames[0]))
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate cache frame"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)

    def test_wrong_revision_or_dangerous_filenames_rejected(self):
        self.manifest["source_revision"] = "unsigned"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_CONFLICT"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)
        self.manifest["source_revision"] = "c" * 64
        self.frames[0]["filename"] = "../../secret.obj"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "unsafe cache filename"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)

    def test_symlink_cannot_escape_owner_root(self):
        import os
        outside = Path(self.temp.name) / "evil"
        outside.write_bytes(self.framebytes)
        target = self.folder / "frame_000001.obj"
        target.unlink()
        try:
            os.symlink(outside, target)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(ValueError, "MISSING_REFERENCE"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)

    def test_manifest_oversize_rejected_before_json_parse(self):
        (self.folder / "manifest.json").write_bytes(b" " * ((1 << 20) + 1))
        with self.assertRaisesRegex(ValueError, "MISSING_REFERENCE"):
            vfx.audit("omega.vfx.cache_inspect", self.payload, self.context)


if __name__ == "__main__":
    unittest.main()
