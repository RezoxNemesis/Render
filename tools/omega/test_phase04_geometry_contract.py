# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure contract tests, runnable without bpy or an Android device.

Real BMesh assertions live in native-tests/omega/phase04/real_blender_fixture.py.
"""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[2] / "full-app/scripts/omega/phase04_geometry.py"
spec = importlib.util.spec_from_file_location("phase04_geometry", MODULE)
phase04 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase04)
REV = "a" * 64


class Phase04ContractTests(unittest.TestCase):
    def assertCode(self, code, fn, *args):
        with self.assertRaises(ValueError) as raised:
            fn(*args)
        self.assertEqual(str(raised.exception), code)

    def bridge(self, **updates):
        value = {
            "object": "GeometryArch", "expected_revision": REV,
            "loops": [[0, 1, 2, 3], [4, 5, 6, 7]],
            "closed": True, "smooth": False, "require_manifold": True,
        }
        value.update(updates)
        return value

    def test_interface_and_import_without_blender(self):
        self.assertEqual(phase04.CONTRACT_VERSION, "RENDER-OMEGA-1")
        self.assertEqual(phase04.OPERATION_NAMES,
                         ("omega.geometry.bridge_loops", "omega.geometry.inspect"))
        self.assertEqual(phase04.validate("omega.geometry.inspect", {"object": "GeometryArch"}),
                         {"object": "GeometryArch"})
        self.assertCode("UNSUPPORTED_NATIVE_FEATURE", phase04.validate,
                        "omega.blender.exec", {"command": "bpy.ops.wm.quit_blender()"})

    def test_bridge_validation(self):
        result = phase04.validate("omega.geometry.bridge_loops", self.bridge())
        self.assertEqual(len(result["loops"]), 2)
        self.assertTrue(result["closed"])
        self.assertCode("INVALID_ARGUMENTS", phase04.validate, "omega.geometry.bridge_loops",
                        self.bridge(command="bpy.ops.mesh.delete"))
        self.assertCode("INVALID_EDGE_LOOPS", phase04.validate, "omega.geometry.bridge_loops",
                        self.bridge(loops=[[0, 1, 1], [3, 4, 5]]))
        self.assertCode("INVALID_EDGE_LOOPS", phase04.validate, "omega.geometry.bridge_loops",
                        self.bridge(loops=[[0, True, 2], [3, 4, 5]]))
        self.assertCode("LOOP_VERTEX_COUNT_MISMATCH", phase04.validate,
                        "omega.geometry.bridge_loops", self.bridge(loops=[[0, 1, 2, 3], [4, 5, 6]]))
        self.assertCode("INVALID_EDGE_LOOPS", phase04.validate, "omega.geometry.bridge_loops",
                        self.bridge(loops=[list(range(257)), list(range(300, 557))]))
        self.assertCode("INVALID_EDGE_LOOPS", phase04.validate, "omega.geometry.bridge_loops",
                        self.bridge(loops=[[0, 1, 2], [3, 4, 2]]))
        self.assertCode("INVALID_SOURCE_REVISION", phase04.validate,
                        "omega.geometry.bridge_loops", self.bridge(expected_revision="none"))
        self.assertCode("INVALID_OBJECT_NAME", phase04.validate,
                        "omega.geometry.bridge_loops", self.bridge(object="../Projects/user.blend"))
        self.assertCode("INVALID_ARGUMENTS", phase04.validate,
                        "omega.geometry.bridge_loops", self.bridge(smooth="true"))

    def test_open_rings_and_restore_schema(self):
        result = phase04.validate("omega.geometry.bridge_loops",
                                  self.bridge(closed=False, loops=[[0, 1], [2, 3]]))
        self.assertFalse(result["closed"])
        restore = phase04.validate("omega.geometry.bridge_loops", {
            "object": "GeometryArch", "action": "restore", "expected_revision": REV,
        })
        self.assertEqual(restore["action"], "restore")
        self.assertCode("INVALID_ARGUMENTS", phase04.validate,
                        "omega.geometry.bridge_loops", self.bridge(action="restore"))
        self.assertCode("INVALID_ARGUMENTS", phase04.validate,
                        "omega.geometry.bridge_loops", self.bridge(action="python"))

    def test_revision_digest_and_budget(self):
        a = phase04.validate("omega.geometry.bridge_loops", self.bridge())
        b = phase04.validate("omega.geometry.bridge_loops", self.bridge(smooth=True))
        self.assertNotEqual(phase04._fingerprint(a), phase04._fingerprint(b))
        self.assertEqual(phase04._fingerprint(a), phase04._fingerprint(dict(a)))
        self.assertCode("OUT_OF_MEMORY_PAUSED", phase04._check_budget,
                        {"available_memory_bytes": 1024}, 100, 100)
        self.assertCode("INVALID_CONTEXT", phase04._check_budget,
                        {"available_memory_bytes": "infinite"}, 100, 100)
        phase04._check_budget({"available_memory_bytes": 1_000_000_000}, 100, 100)
        self.assertCode("INVALID_JOB_ID", phase04._job, {"job_id": None})
        self.assertEqual(phase04._job({"job_id": "b" * 32}), "b" * 32)

    def test_no_fake_native_execution(self):
        # Native functions cannot be claimed as successful in a plain CPython test.
        self.assertCode("UNSUPPORTED_NATIVE_FEATURE", phase04.execute,
                        "omega.geometry.inspect", {"object": "GeometryArch"}, {"scene": None})
        self.assertCode("UNSUPPORTED_NATIVE_FEATURE", phase04.audit,
                        "omega.geometry.inspect", {"object": "GeometryArch"}, {"scene": None})


if __name__ == "__main__":
    unittest.main()
