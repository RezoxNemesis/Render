"""Host-only pure plan validation. Run: python -m unittest discover -s tools/omega -p 'test_phase03_agent.py' -v"""
import importlib.util
from pathlib import Path
import unittest

FILE = Path(__file__).resolve().parents[2] / "full-app" / "scripts" / "omega" / "phase03_agent.py"
spec = importlib.util.spec_from_file_location("phase03_agent", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

PROJECT = "a" * 64
REVISION = "b" * 64
PLAN = "c" * 32


def fixture():
    return {"project_id": PROJECT, "source_revision": REVISION, "plan_id": PLAN,
            "stages": [
                {"id": "plan", "kind": "PLAN", "operation": "omega.agent.plan_validate", "args": {},
                 "depends_on": [], "expected_scene_revision": REVISION},
                {"id": "create", "kind": "CREATE", "operation": "blender.object.add_cube",
                 "args": {"name": "NativeCube", "size": 2}, "depends_on": ["plan"],
                 "expected_scene_revision": REVISION},
                {"id": "inspect", "kind": "VALIDATE", "operation": "blender.scene.summary",
                 "args": {}, "depends_on": ["create"], "expected_scene_revision": REVISION}
            ]}


class TestPhase03Plan(unittest.TestCase):
    def test_deterministic_bounded_dag(self):
        first = mod.validate("omega.agent.plan_validate", fixture())
        self.assertEqual(first, mod.validate("omega.agent.plan_validate", fixture()))
        self.assertEqual(len(first["stages"]), 3)
        self.assertEqual(len({s["idempotency_key"] for s in first["stages"]}), 3)
        self.assertEqual(len(first["plan_digest"]), 64)

    def test_no_remote_code_or_filesystem(self):
        for bad in ("python", "shell", "filepath", "command", "url"):
            with self.subTest(key=bad):
                plan = fixture()
                plan["stages"][1]["args"][bad] = "dangerous"
                with self.assertRaisesRegex(ValueError, "UNSAFE_STAGE_ARGUMENT"):
                    mod.validate("omega.agent.plan_validate", plan)

    def test_no_cycles_or_unknown_operation(self):
        plan = fixture()
        plan["stages"][1]["depends_on"] = ["inspect"]
        with self.assertRaisesRegex(ValueError, "INVALID_STAGE_DEPENDENCIES"):
            mod.validate("omega.agent.plan_validate", plan)
        plan = fixture()
        plan["stages"][1]["operation"] = "bpy.ops.wm.open_mainfile"
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_STAGE_OPERATION"):
            mod.validate("omega.agent.plan_validate", plan)

    def test_project_revision_scope(self):
        plan = fixture()
        plan["stages"][2]["expected_scene_revision"] = "d"*64
        with self.assertRaisesRegex(ValueError, "CHECKPOINT_CONFLICT"):
            mod.validate("omega.agent.plan_validate", plan)
        plan = fixture()
        plan["project_id"] = "../project"
        with self.assertRaisesRegex(ValueError, "INVALID_PROJECT_ID"):
            mod.validate("omega.agent.plan_validate", plan)

    def test_no_mock_native_success(self):
        with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
            mod.execute("omega.agent.plan_validate", fixture(), {"scene": object()})
        with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
            mod.audit("omega.agent.journal_status", {"project_id": PROJECT,
                      "plan_id": PLAN, "source_revision": REVISION}, {"scene": object()})

    def test_validation_edge_cases(self):
        cases = [({"max_retries": True}, "INVALID_STAGE_RETRIES"),
                 ({"max_retries": 3}, "INVALID_STAGE_RETRIES"),
                 ({"args": {"size": float("nan")}}, "INVALID_ARGUMENTS"),
                 ({"args": {"name": "Bad Name"}}, "INVALID_OBJECT_NAME")]
        for changes, code in cases:
            with self.subTest(changes=changes):
                plan = fixture()
                plan["stages"][1].update(changes)
                with self.assertRaisesRegex(ValueError, code):
                    mod.validate("omega.agent.plan_validate", plan)


if __name__ == "__main__":
    unittest.main()
