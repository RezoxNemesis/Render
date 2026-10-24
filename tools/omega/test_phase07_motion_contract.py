# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure Phase 07 security, math, schema and import regression suite.

Run: python -m unittest discover -s tools/omega -p 'test_phase07_*.py' -v
These tests are NOT evidence of real Blender execution; see the bpy fixture.
"""
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "omega_phase07_motion", ROOT / "full-app/scripts/omega/phase07_motion.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class Phase07Contract(unittest.TestCase):
    def test_frozen_operations(self):
        self.assertEqual(M.CONTRACT_VERSION, "RENDER-OMEGA-1")
        self.assertEqual(M.OPERATION_NAMES,
                         ("omega.motion.create_actions", "omega.motion.audit"))
        self.assertTrue(callable(M.execute) and callable(M.audit))

    def test_validated_walk_defaults_and_no_native_import_on_load(self):
        p = M.validate("omega.motion.create_actions", {"rig": "SyntheticRig", "clip": "Walk01"})
        self.assertEqual((p["frames"], p["start"], p["kind"]), (25, 1, "walk"))
        self.assertEqual(p["retime_scale"], 1.0)
        self.assertEqual(M.validate("omega.motion.audit", {"rig": "SyntheticRig", "clip": "Walk01"}),
                         {"rig": "SyntheticRig", "clip": "Walk01"})

    def test_retime_is_separate_from_immutable_action_curves(self):
        self.assertEqual(M.validate("omega.motion.create_actions", {
            "rig": "SyntheticRig", "clip": "Walk01", "kind": "retime",
            "retime_scale": 1.75})["retime_scale"], 1.75)
        with self.assertRaisesRegex(ValueError, "INVALID_ARGUMENTS"):
            M.validate("omega.motion.create_actions", {
                "rig": "SyntheticRig", "clip": "Walk01", "kind": "retime", "stride": .22})

    def test_malicious_or_unbounded_schema_rejected(self):
        malformed = [
            {"rig": "R", "clip": "ok", "python": "exec('code')"},
            {"rig": "../other_scene", "clip": "ok"},
            {"rig": "R", "clip": "../../escape"},
            {"rig": "R", "clip": "ok", "start": True},
            {"rig": "R", "clip": "ok", "frames": 100001},
            {"rig": "R", "clip": "ok", "frames": 28},
            {"rig": "R", "clip": "ok", "stride": float("nan")},
            {"rig": "R", "clip": "ok", "stride": float("inf")},
            {"rig": "R", "clip": "ok", "clearance": -.2},
            {"rig": "R", "clip": "ok", "retime_scale": 0},
            {"rig": "R", "clip": "ok", "contact_z": "NaN"},
            {"rig": "R", "clip": "ok", "bones": {"root": "Root"}},
            {"rig": "R", "clip": "ok", "bones": {key: "Root" for key in M._CHANNELS}},
        ]
        for payload in malformed:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    M.validate("omega.motion.create_actions", payload)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_NATIVE_FEATURE"):
            M.validate("omega.motion.create_actions", {"rig": "R", "clip": "ok", "kind": "hook"})
        with self.assertRaisesRegex(ValueError, "INVALID_ARGUMENTS"):
            M.validate("python.eval", {"rig": "R", "clip": "ok"})

    def test_contact_math_reconstructs_true_world_target(self):
        for forward in (-.13, -.07, 0, .07, .13):
            for height in (.08, .12, .16):
                thigh, knee = M._solve_leg(1.0, .5, .5, forward, 0, height)
                self.assertAlmostEqual(.5*math.sin(thigh)+.5*math.sin(thigh+knee), forward, places=7)
                self.assertAlmostEqual(1.0-.5*math.cos(thigh)-.5*math.cos(thigh+knee), height, places=7)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_NATIVE_FEATURE"):
            M._solve_leg(1., .5, .5, 5., 0, 0.)

    def test_context_cancellation_and_dry_run_are_non_mutating(self):
        M._guard_context({"dry_run": False, "cancellation_requested": False})
        with self.assertRaisesRegex(ValueError, "CANCELLED_BY_OWNER"):
            M._guard_context({"cancellation_requested": lambda: True})
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_NATIVE_FEATURE"):
            M._guard_context({"dry_run": True})

    def test_identity_and_signature_are_replay_stable(self):
        p = M.validate("omega.motion.create_actions", {"rig": "Rig", "clip": "Walk"})
        names = dict(M._DEFAULT_BONES)
        self.assertEqual(M._signature(p, names, "revision"), M._signature(dict(p), dict(names), "revision"))
        self.assertNotEqual(M._signature(p, names, "revision"), M._signature(p, names, "different"))
        self.assertNotEqual(M._action_name("Rig", "Walk"), M._action_name("Rig2", "Walk"))
        self.assertLessEqual(len(M._action_name("Rig", "Walk")), 63)

    def test_execute_cannot_claim_native_without_bpy(self):
        if importlib.util.find_spec("bpy") is not None:
            self.skipTest("bpy installed: native fixture tests genuine execution")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_NATIVE_FEATURE"):
            M.execute("omega.motion.create_actions", {"rig": "Rig", "clip": "Walk"}, {"scene": None})


if __name__ == "__main__":
    unittest.main()
