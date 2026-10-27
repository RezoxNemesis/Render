"""Deterministic runtime-ZIP staging tests; synthetic ZIP is not an Android APK."""
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import zipimport

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from assemble_full_native import attach_bpy_agent


class OmegaPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.script = self.root / "render_agent_startup.py"
        # Give the archive adapter a complete source tree. The behavior under
        # test is registry uniqueness and refusing unowned Omega phases; an
        # unrelated newly shipped startup module must not break that fixture.
        for source in (ROOT / "full-app/scripts").glob("*.py"):
            (self.root / source.name).write_text("# test-only synthetic module\n")
        (self.root / "omega").mkdir()
        (self.root / "omega/__init__.py").write_text("# init\n")
        (self.root / "omega/phase04_geometry.py").write_text("# phase test fixture\n")

    def tearDown(self):
        self.temp.cleanup()

    def package(self, filename):
        runtime = self.root / filename
        with zipfile.ZipFile(runtime, "w") as stream:
            stream.writestr("scripts/startup/bl_ui_test.py", "# native upstream placeholder")
        attach_bpy_agent(runtime, self.script, self.root / "render_lively_scene.py",
                         self.root / "render_batch_assembly.py")
        with zipfile.ZipFile(runtime) as stream:
            names = stream.namelist()
            self.assertEqual(len(names), len(set(names)), "duplicate scripts")
            self.assertIn("scripts/startup/render_agent_startup.py", names)
            self.assertIn("scripts/startup/omega_registry.py", names)
            self.assertIn("scripts/startup/omega/__init__.py", names)
            self.assertIn("scripts/startup/omega/phase04_geometry.py", names)
            self.assertIn("scripts/startup/bl_ui_test.py", names)
        return runtime

    def test_packaging_twice_has_exactly_one_registry(self):
        first = self.package("first.zip")
        second = self.package("second.zip")
        with zipfile.ZipFile(first) as x, zipfile.ZipFile(second) as y:
            self.assertEqual(x.namelist(), y.namelist())
        # Python's zipimport can find the registry from Blender's startup subtree.
        importer = zipimport.zipimporter(str(first) + "/scripts/startup")
        self.assertIsNotNone(importer.get_code("omega_registry"))

    def test_refuses_unknown_phase_module(self):
        (self.root / "omega/phase99_fake.py").write_text("# unowned\n")
        with self.assertRaisesRegex(ValueError, "UNRECOGNIZED_OMEGA_MODULE"):
            self.package("invalid.zip")


if __name__ == "__main__":
    unittest.main()
