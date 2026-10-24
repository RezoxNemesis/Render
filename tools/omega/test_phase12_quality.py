# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure, dependency-free quality contracts; NO mocked result is native bpy proof.

python3 -m unittest discover -s tools/omega -p 'test_phase12_*.py' -v
"""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[2] / "full-app/scripts/omega/phase12_quality.py"
spec = importlib.util.spec_from_file_location("phase12_quality", SOURCE)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def fixture(shoulder=0.95, head=0.18, neck_gap=True):
    levels = ((0.45, 0.36), (1.18, 0.40), (1.65, shoulder),
              (1.91, 0.15), (2.24, head), (2.54, head))
    verts = []
    for z, half in levels:
        verts.extend(((-half, -0.16, z), (half, -0.16, z),
                      (half, 0.16, z), (-half, 0.16, z)))
    faces = []
    for ring in range(len(levels) - 1):
        if neck_gap and ring == 2:
            continue
        a, b = ring * 4, (ring + 1) * 4
        faces.extend((a + i, a + (i + 1) % 4, b + (i + 1) % 4, b + i)
                     for i in range(4))
    landmarks = dict(shoulder_L=8, shoulder_R=9, neck_L=12, neck_R=13,
                     head_L=16, head_R=17)
    reference = dict(measurement="shoulder_width_over_head_width",
                     min=1.8, max=2.5, provenance="synthetic_fixture")
    return verts, faces, landmarks, reference


def request(operation="omega.quality.inspect", **kwargs):
    verts, faces, landmarks, ref = fixture()
    return {"target_object": "CharacterBody", "landmarks": landmarks,
            "reference_target": ref, "scene_scale": 1.0, **kwargs}


class ContractTests(unittest.TestCase):
    def test_import_does_not_load_blender(self):
        old = sys.modules.get("bpy")
        try:
            sys.modules.pop("bpy", None)
            spec.loader.exec_module(importlib.util.module_from_spec(spec))
            self.assertNotIn("bpy", sys.modules)
        finally:
            if old is not None:
                sys.modules["bpy"] = old

    def test_known_operations_and_json_serializable_receipts(self):
        self.assertEqual(quality.OPERATION_NAMES,
                         ("omega.quality.inspect", "omega.quality.revise_plan"))
        validated = quality.validate("omega.quality.inspect", request())
        self.assertEqual(json.dumps(validated), json.dumps(request()))
        self.assertIsNot(validated, request())

    def test_bad_and_good_ratios_are_measured_not_inferred(self):
        v, f, m, ref = fixture()
        bad = quality._measure(v, f, m, ref)
        self.assertEqual(bad["face_components"], 2)
        self.assertGreater(bad["shoulder_width_over_head_width"], 5)
        self.assertFalse(bad["reference_passed"])
        v2, f2, m2, ref2 = fixture(shoulder=0.44, head=0.20, neck_gap=False)
        good = quality._measure(v2, f2, m2, ref2)
        self.assertEqual(good["face_components"], 1)
        self.assertAlmostEqual(good["shoulder_width_over_head_width"], 2.2)
        self.assertTrue(good["reference_passed"])
        self.assertGreater(good["mesh_face_count"], bad["mesh_face_count"])

    def test_explicit_regions_prevent_unannotated_destructive_repair(self):
        v, f, marks, bounds = fixture()
        result = quality._measure(v, f, marks, bounds)
        receipt = {"target_object": "CharacterBody", "source_revision": "0" * 64,
                   "metrics": result, "protected_geometry_sha256": "c" * 64}
        no_region = quality._plan(copy.deepcopy(receipt),
                                  quality.validate("omega.quality.revise_plan", request()), {})
        self.assertEqual(no_region["stopped_reason"], "SHOULDER_REGION_ANNOTATION_REQUIRED")
        self.assertEqual(no_region["proposals"], [])
        region_request = quality.validate("omega.quality.revise_plan", request(
            shoulder_region_vertices=[8, 9, 10, 11], max_iterations=2,
            checkpoint_sha256="a" * 64))
        planned = quality._plan(copy.deepcopy(receipt), region_request, {})
        self.assertEqual(len(planned["proposals"]), 1)
        proposal = planned["proposals"][0]
        self.assertEqual(proposal["repair"]["operation"], "omega.artist.execute_tool")
        self.assertEqual(proposal["repair"]["tool"], "mesh.adjust_region")
        self.assertAlmostEqual(proposal["repair"]["parameters"]["scale_factor"],
                               2.15 / (1.9 / 0.36))
        self.assertEqual(proposal["rollback_checkpoint_sha256"], "a" * 64)
        self.assertFalse(proposal["approved_for_auto_execution"])
        self.assertFalse(planned["revision_engine_executed_edits"])
        self.assertFalse(planned["checkpoint_verified"])

    def test_corresponding_region_change_improves_metric_preserves_unrelated_vertices(self):
        v, f, marks, bounds = fixture()
        unchanged = copy.deepcopy(v)
        old = quality._measure(v, f, marks, bounds)
        factor = bounds["max"] / old["shoulder_width_over_head_width"]
        v = [list(p) for p in v]
        for i in [8, 9, 10, 11]:
            v[i][0] *= factor
        corrected = quality._measure(v, f, marks, bounds)
        self.assertTrue(corrected["reference_passed"])
        self.assertAlmostEqual(corrected["head_width"], old["head_width"])
        self.assertEqual([tuple(v[i]) for i in range(len(v)) if i not in (8, 9, 10, 11)],
                         [unchanged[i] for i in range(len(v)) if i not in (8, 9, 10, 11)])
        self.assertEqual(corrected["face_components"], 2,
                         "ratio fix must not magically claim a missing neck joint was repaired")
        f += [(8+i, 8+(i+1)%4, 12+(i+1)%4, 12+i) for i in range(4)]
        repaired_topology = quality._measure(v, f, marks, bounds)
        self.assertEqual(repaired_topology["face_components"], 1)

    def test_iteration_budget_stale_revision_and_regression_stops(self):
        v, f, m, bounds = fixture()
        base = {"target_object": "CharacterBody", "source_revision": "a" * 64,
                "metrics": quality._measure(v, f, m, bounds),
                "protected_geometry_sha256": "c" * 64}
        fields = dict(shoulder_region_vertices=[8, 9, 10, 11], attempts_used=1,
                      previous_source_revision="a" * 64,
                      previous_guard_sha256="c" * 64, previous_metric=5.8)
        stale = quality._plan(copy.deepcopy(base), quality.validate(
            "omega.quality.revise_plan", request(**fields)), {})
        self.assertEqual(stale["stopped_reason"], "NO_NATIVE_REVISION")
        fields["previous_source_revision"] = "b" * 64
        fields["previous_metric"] = 4.1
        worse = quality._plan(copy.deepcopy(base), quality.validate(
            "omega.quality.revise_plan", request(**fields)), {})
        self.assertEqual(worse["stopped_reason"], "NO_MEASURABLE_IMPROVEMENT")
        fields["previous_guard_sha256"] = "d" * 64
        changed = quality._plan(copy.deepcopy(base), quality.validate(
            "omega.quality.revise_plan", request(**fields)), {})
        self.assertEqual(changed["stopped_reason"], "NON_TARGET_GEOMETRY_CHANGED")
        fields["attempts_used"] = 2
        done = quality._plan(copy.deepcopy(base), quality.validate(
            "omega.quality.revise_plan", request(**fields)), {})
        self.assertEqual(done["stopped_reason"], "ITERATION_LIMIT_REACHED")
        self.assertEqual(done["proposals"], [])

    def test_invalid_and_malicious_payloads_fail_before_blender(self):
        bad = [
            dict(target_object="../../media", landmarks=request()["landmarks"]),
            request(source_revision="wrong"),
            request(image_name="/tmp/secret.png"),
            request(unknown="eval(os.system())"),
            request(reference_target=dict(measurement="shoulder_width_over_head_width",
                                          min=2.5, max=1.8, provenance="owner_measured")),
            request(landmarks={"shoulder_L": 1}),
            request(landmarks=dict(request()["landmarks"], head_L=True)),
            request(shoulder_region_vertices=[8, 8, 9]),
            request(shoulder_region_vertices=[12, 13]),
            request(scene_scale=float("nan")),
            request(shoulder_region_vertices=list(range(4096))),
        ]
        for value in bad:
            with self.subTest(payload=str(value)[:90]), self.assertRaises(ValueError):
                quality.validate("omega.quality.inspect", value)
        for invalid in ("omega.quality.custom_python", "python.exec", ""):
            with self.assertRaises(ValueError):
                quality.validate(invalid, {})
        for kwargs in ({"max_iterations": 100}, {"attempts_used": True},
                       {"attempts_used": 1}, {"checkpoint_sha256": "/data/secrets"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                quality.validate("omega.quality.revise_plan", request(**kwargs))

    def test_no_blender_does_not_return_fake_success(self):
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_NATIVE_FEATURE"):
            quality.execute("omega.quality.inspect", request(), {})

    def test_mesh_budget_invalid_face_and_isolated_components(self):
        with self.assertRaisesRegex(ValueError, "INSPECTION_BUDGET_EXCEEDED"):
            quality._measure([], [], None)
        with self.assertRaisesRegex(ValueError, "INVALID_NATIVE_TOPOLOGY"):
            quality._measure([(0.,0.,0.), (1.,0.,0.), (1.,1.,0.)], [(0, 1, 99)], None)
        measured = quality._measure([(0.,0.,0.),(1.,0.,0.),(1.,1.,0.),(3.,3.,3.)],
                                    [(0,1,2)], None)
        self.assertEqual(measured["isolated_vertices"], 1)
        self.assertEqual(measured["boundary_edges"], 3)
        self.assertEqual(measured["anatomical_landmarks"], "INSPECTION_UNAVAILABLE")

if __name__ == "__main__":
    unittest.main()
