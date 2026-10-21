# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise Render's saved-scene recovery with bpy doubles, not cloud Blender."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "full-app/scripts/render_lively_scene.py"
FILENAME = "Render_" + "a" * 32 + ".blend"


class FakeBlenderLibrary:
    def __init__(self, scene):
        self.scene = scene
        self.src = types.SimpleNamespace(scenes=["SavedScene"])
        self.dst = types.SimpleNamespace(scenes=[])

    def __enter__(self):
        return (self.src, self.dst)

    def __exit__(self, *_):
        self.dst.scenes = [self.scene]


class RestoreSceneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.spool = self.root / "render_bpy_jobs"
        self.spool.mkdir()
        self.projects = self.root / "Projects"
        self.projects.mkdir()
        self.previous = types.SimpleNamespace(name="PriorScene", objects=[object()])
        self.restored = types.SimpleNamespace(name="SavedScene", objects=[object(), object()])
        self.window = types.SimpleNamespace(scene=self.previous)
        fake_bpy = types.ModuleType("bpy")
        fake_mathutils = types.ModuleType("mathutils")
        fake_mathutils.Vector = object
        fake_bpy.context = types.SimpleNamespace(scene=self.previous, window=self.window)
        fake_bpy.data = types.SimpleNamespace(
            scenes=[self.previous, self.restored],
            libraries=types.SimpleNamespace(
                load=lambda path, link=False: FakeBlenderLibrary(self.restored)))
        self.fake_bpy = fake_bpy
        with patch.dict(sys.modules, {"bpy": fake_bpy, "mathutils": fake_mathutils}):
            spec = importlib.util.spec_from_file_location(
                "render_lively_scene_under_test", MODULE)
            self.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.module)

    def tearDown(self):
        self.temp.cleanup()

    def test_restores_owned_saved_scene_and_preserves_existing(self):
        (self.projects / FILENAME).write_bytes(b"BLENDER" + b"0" * 1024)
        result = self.module.restore_scene({"filename": FILENAME}, str(self.spool))
        self.assertEqual(result["objects"], 2)
        self.assertEqual(result["source_file"], FILENAME)
        self.assertTrue(result["previous_scene_preserved"])
        self.assertIs(self.window.scene, self.restored)
        self.assertIn(self.previous, self.fake_bpy.data.scenes)

    def test_rejects_paths_and_non_owned_names(self):
        for name in ("../x.blend", "/tmp/x.blend", "Building.blend",
                     "Render_" + "x" * 32 + ".blend", FILENAME + ".bak"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError,
                                            "INVALID_SAVED_PROJECT_FILENAME"):
                    self.module.restore_scene({"filename": name}, str(self.spool))
        self.assertIs(self.window.scene, self.previous)

    def test_missing_or_symlinked_snapshot_is_refused(self):
        with self.assertRaisesRegex(ValueError, "SAVED_PROJECT_NOT_FOUND"):
            self.module.restore_scene({"filename": FILENAME}, str(self.spool))
        outside = self.root / "private.blend"
        outside.write_bytes(b"BLENDER" + b"0" * 512)
        (self.projects / FILENAME).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "SAVED_PROJECT_NOT_FOUND"):
            self.module.restore_scene({"filename": FILENAME}, str(self.spool))
        self.assertIs(self.window.scene, self.previous)

    def test_refuses_unexpected_fields_before_modifying_scene(self):
        (self.projects / FILENAME).write_bytes(b"BLENDER" + b"0" * 512)
        with self.assertRaisesRegex(ValueError, "INVALID_RESTORE_ARGUMENTS"):
            self.module.restore_scene({"filename": FILENAME, "arbitrary_path": "x"},
                                      str(self.spool))
        self.assertIs(self.window.scene, self.previous)


if __name__ == "__main__":
    unittest.main()
