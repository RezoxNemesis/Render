# SPDX-License-Identifier: GPL-2.0-or-later
import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "full-app/scripts"))
import render_motion_lab_contract as C

VALID = {"studio.motion.rig.create": {"name": "Actor"},
         "studio.motion.clip.create": {"rig": "Actor", "preset": "walk"},
         "studio.motion.audit": {"rig": "Actor", "contacts": [{"bone": "foot.L", "start": 1, "end": 24}],
             "joints": [{"parent": "thigh.L", "child": "shin.L"}]}}


class MotionContractTests(unittest.TestCase):
    def test_normalization_is_nonmutating_and_idempotent(self):
        for op, payload in VALID.items():
            before = copy.deepcopy(payload)
            normalized = C.validate(op, payload)
            self.assertEqual(payload, before)
            self.assertEqual(normalized, C.validate(op, normalized))
            json.dumps(normalized, allow_nan=False)

    def test_operation_and_unknown_fields_fail_closed(self):
        for operation in (None, True, [], "studio.motion.python"):
            with self.assertRaises(ValueError):
                C.validate(operation, {})
        for operation, payload in VALID.items():
            for field in ("code", "path", "url", "overwrite", "allow_existing_action"):
                with self.assertRaises(ValueError):
                    C.validate(operation, {**payload, field: "value"})

    def test_rejects_nonfinite_and_boolean_numbers(self):
        for value in (True, False, math.nan, math.inf, -math.inf, 10**1000, "1", None):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.rig.create", {"name": "Actor", "height": value})
            with self.assertRaises(ValueError):
                C.validate("studio.motion.audit", {"rig": "Actor", "max_distance_per_frame": value})

    def test_bad_names_and_origin(self):
        for name in ("", "../file", " A", "A ", "A"*49, "A\nB", "A/b", "bpy.exec()", "3Actor"):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.rig.create", {"name": name})
        for origin in (None, (0, 0, 0), [0, 0], [0, 0, math.nan], [0, 0, True]):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.rig.create", {"name": "Actor", "origin": origin})

    def test_clip_rejects_undersampled_and_excessive_cycles(self):
        for change in ({"end": 12}, {"end": 242}, {"cycles": 3, "end": 49}, {"cycles": 5}, {"stride": .7}):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.clip.create", {"rig": "Actor", "preset": "walk", **change})
        self.assertEqual(C.validate("studio.motion.clip.create", {"rig": "Actor", "preset": "squat", "cycles": 4, "end": 97})["cycles"], 4)

    def test_sample_budget_and_contact_boundaries(self):
        with self.assertRaisesRegex(ValueError, "BUDGET"):
            C.validate("studio.motion.audit", {"rig": "Actor", "end": 2401})
        data = C.validate("studio.motion.audit", {"rig": "Actor", "end": 100, "step": 10,
                         "contacts": [{"bone": "foot.L", "start": 4, "end": 8}]})
        frames = C.sample_frames(data["start"], data["end"], data["step"], data["contacts"])
        self.assertTrue({1, 4, 8, 100}.issubset(frames))

    def test_invalid_contacts_and_joint_limits(self):
        for contact in ({"bone": "foot.L", "start": 2, "end": 2}, {"bone": "foot.L", "start": 0, "end": 5},
                        {"bone": "foot.L", "start": 1, "end": 50}, {"bone": "foot.L", "start": 1, "end": 5, "max_drift": -1}):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.audit", {"rig": "Actor", "contacts": [contact]})
        for joint in ({"parent": "bone", "child": "bone"}, {"parent": "a", "child": "b", "min_degrees": 90, "max_degrees": 20},
                      {"parent": "a", "child": "b", "max_degrees": math.nan}):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.audit", {"rig": "Actor", "joints": [joint]})

    def test_duplicate_and_unbounded_mappings_rejected(self):
        contact = {"bone": "foot.L", "start": 1, "end": 5}
        for contacts in ([contact, contact], [contact]*33, None, {}):
            with self.assertRaises(ValueError):
                C.validate("studio.motion.audit", {"rig": "Actor", "contacts": contacts})

    def test_omitted_and_empty_audit_maps_remain_distinct(self):
        self.assertNotIn("contacts", C.validate("studio.motion.audit", {"rig": "Actor"}))
        self.assertEqual(C.validate("studio.motion.audit", {"rig": "Actor", "contacts": []})["contacts"], [])

    def test_schema_required_and_access_flags(self):
        for descriptor in C.capabilities():
            op = descriptor["operation"]
            self.assertEqual(descriptor["read_only"], op in C.READ_ONLY)
            self.assertFalse(descriptor["input_schema"]["additionalProperties"])
            for required in descriptor["input_schema"]["required"]:
                payload = copy.deepcopy(VALID[op]); del payload[required]
                with self.assertRaises(ValueError):
                    C.validate(op, payload)


if __name__ == "__main__":
    unittest.main()
