# SPDX-License-Identifier: GPL-2.0-or-later
"""P06 pure host tests. Run real deformation separately under Blender's bpy."""
import importlib.util
import math
from pathlib import Path
import unittest

MODULE = (Path(__file__).resolve().parents[2] /
          "full-app/scripts/omega/phase06_rig.py")
spec = importlib.util.spec_from_file_location("phase06_rig", MODULE)
rig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rig)


class RigContractTests(unittest.TestCase):
    def test_no_bpy_import_side_effects(self):
        self.assertEqual("RENDER-OMEGA-1", rig.CONTRACT_VERSION)
        self.assertEqual(("omega.rig.bind", "omega.rig.audit"), rig.OPERATION_NAMES)
        self.assertIsInstance(rig.default_landmarks(), dict)

    def test_rejects_unbounded_or_executable_payloads(self):
        bad = (
            {"object_name": "../external"},
            {"object_name": "Hero", "script": "__import__('os')"},
            {"object_name": "Hero", "template": "quadruped"},
            {"object_name": "Hero", "enable_leg_ik": "true"},
            {"object_name": "Hero", "rig_name": "../../escape"},
            {"object_name": "Hero", "expected_revision": "not_a_sha"},
            {"object_name": "Hero", "landmarks": {"pelvis": [0, 0, 1]}},
        )
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                rig.validate("omega.rig.bind", payload)
        with self.assertRaises(ValueError):
            rig.validate("python.eval", {"object_name": "Hero"})

    def test_rejects_nan_infinity_and_reversed_sides(self):
        for coordinate in (math.nan, math.inf, -math.inf, 10001):
            points = rig.default_landmarks()
            points["knee.L"] = [coordinate, 0, .5]
            with self.assertRaises(ValueError):
                rig.validate("omega.rig.bind", {"object_name": "Hero", "landmarks": points})
        points = rig.default_landmarks()
        points["shoulder.L"] = (-.2, 0, 1.5)
        with self.assertRaisesRegex(ValueError, "reversed"):
            rig.validate("omega.rig.bind", {"object_name": "Hero", "landmarks": points})

    def test_landmark_chain_and_controller_hierarchy(self):
        p = rig.default_landmarks()
        bones, chains = rig._hierarchy(p)
        self.assertGreaterEqual(len(bones), 20)
        self.assertEqual(5, len(chains))
        self.assertEqual(("hips", "spine", "chest", "neck", "head"), chains["core"])
        for side in ("L", "R"):
            self.assertIn("shin." + side, chains["leg." + side])
            self.assertIn("forearm." + side, chains["arm." + side])
        for _, head, tail, _, deform in bones:
            self.assertGreater(rig._distance_squared(p[head], p[tail]), 1e-8)
            self.assertIn(deform, (True, False))

    def test_normalized_local_weights_without_opposite_side_bleed(self):
        p = rig.default_landmarks()
        bones, chains = rig._hierarchy(p)
        segments = {name: (p[a], p[b]) for name, a, b, _, deform in bones if deform}
        for side in ("L", "R"):
            for part in ("elbow", "wrist", "knee", "ankle"):
                coord = p[part + "." + side]
                weights = rig._weights_for_vertex(coord, segments, chains)
                self.assertAlmostEqual(1.0, sum(weights.values()), places=12)
                self.assertGreater(len(weights), 1)
                self.assertTrue(all(0 < w <= 1 for w in weights.values()))
                self.assertTrue(all(not n.endswith(".R" if side == "L" else ".L")
                                    for n in weights))
        # Midpoint of a bone stays near its own limb, not an opposite limb.
        for side in ("L", "R"):
            coord = p["wrist."+side]
            weights = rig._weights_for_vertex(coord, segments, chains)
            self.assertIn("forearm."+side, weights)

    def test_identical_payload_uses_deterministic_normalized_contract(self):
        a = rig.validate("omega.rig.bind", {"object_name": "Hero", "enable_leg_ik": True})
        b = rig.validate("omega.rig.bind", {"object_name": "Hero", "enable_leg_ik": True})
        self.assertEqual(a, b)
        self.assertEqual("OmegaRig.Hero", a["rig_name"])
        self.assertEqual("default_neutral_humanoid", a["landmark_origin"])
        audit = rig.validate("omega.rig.audit", {"object_name": "Hero"})
        self.assertEqual({"object_name": "Hero", "expected_revision": None}, audit)

    def test_pure_validator_requires_no_blender_runtime(self):
        self.assertEqual("Hero", rig.validate("omega.rig.audit", {"object_name": "Hero"})["object_name"])
        try:
            import bpy  # noqa: F401
        except ImportError:
            with self.assertRaisesRegex(RuntimeError, "bpy runtime is absent"):
                rig.execute("omega.rig.bind", {"object_name": "Hero"}, {})


if __name__ == "__main__":
    unittest.main()
