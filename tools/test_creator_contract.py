# SPDX-License-Identifier: GPL-2.0-or-later
"""Adversarial, bpy-free checks for the public creator API."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_creator_contract as C


VALID = {
    "studio.create.catalog": {},
    "studio.create.model": {"name": "My Asset", "kind": "crate"},
    "studio.create.terrain": {"name": "Island"},
    "studio.create.scatter": {"name": "Forest", "source": "Tree", "count": 24},
    "studio.create.material": {"object": "Asset", "preset": "wood"},
    "studio.create.motion": {"object": "Asset", "preset": "turntable"},
    "studio.create.camera": {"target": "Asset", "preset": "hero"},
    "studio.create.rig": {"object": "Asset"},
}


class CreatorContractTests(unittest.TestCase):
    def test_normalizes_defaults_without_mutating_input(self):
        for op, p in VALID.items():
            before = copy.deepcopy(p)
            clean = C.validate(op, p)
            self.assertEqual(p, before)
            self.assertIsNot(clean, p)
            self.assertEqual(clean, C.validate(op, clean))
            json.dumps(clean, allow_nan=False)
        self.assertEqual(C.validate("studio.create.terrain", VALID["studio.create.terrain"]),
                         {"name": "Island", "size": 64., "resolution": 32, "height": 8.,
                          "seed": 0, "style": "island"})
        self.assertTrue(C.validate("studio.create.motion", VALID["studio.create.motion"])["loop"])

    def test_only_exact_operations_and_plain_json_objects(self):
        for op in (None, 2, True, [], "studio.create", "studio.create.python", "Studio.create.model"):
            with self.assertRaises(ValueError):
                C.validate(op, {})
        class DictSubclass(dict):
            pass
        for p in (None, True, [], (), "{}", DictSubclass()):
            with self.assertRaises(ValueError):
                C.validate("studio.create.catalog", p)

    def test_all_unknown_fields_rejected(self):
        for op, p in VALID.items():
            for key in ("python", "script", "filepath", "url", "dry_run", "__proto__", 3):
                with self.subTest(operation=op, key=key):
                    with self.assertRaises(ValueError):
                        C.validate(op, dict(p, **{key: "bad"}) if type(key) is str else {**p, key: 0})

    def test_required_fields_match_schema(self):
        for descriptor in C.capabilities():
            op = descriptor["operation"]
            for key in descriptor["input_schema"]["required"]:
                p = dict(VALID[op]); p.pop(key)
                with self.assertRaises(ValueError):
                    C.validate(op, p)

    def test_invalid_names_rejected_on_every_name_field(self):
        invalid = (None, False, 0, "", " leading", "Trailing ", "a"*65,
                   "../secret", "C:/file", "a/b", "a\\b", "A\nB", "Asset\x00", "3DModel", "étoile",
                   "bpy.ops.wm.read_homefile()", "$(touch file)")
        for descriptor in C.capabilities():
            op = descriptor["operation"]
            for key, spec in descriptor["input_schema"]["properties"].items():
                if "pattern" in spec:
                    for bad in invalid:
                        with self.subTest(operation=op, key=key, bad=repr(bad)):
                            with self.assertRaises(ValueError):
                                C.validate(op, {**VALID[op], key: bad})
        for good in ("A", "Crate.001", "My Asset-02", "A"*64):
            self.assertEqual(C.name(good), good)

    def test_numbers_reject_bools_nan_inf_strings_and_huge_ints(self):
        bad_numbers = (True, False, "1", None, [], {}, math.nan, math.inf, -math.inf, 10**1000)
        for descriptor in C.capabilities():
            op = descriptor["operation"]
            for key, spec in descriptor["input_schema"]["properties"].items():
                if spec["type"] in ("number", "integer"):
                    for bad in bad_numbers:
                        with self.subTest(operation=op, key=key, kind=type(bad).__name__):
                            with self.assertRaises(ValueError):
                                C.validate(op, {**VALID[op], key: bad})
                    if spec["type"] == "integer":
                        with self.assertRaises(ValueError):
                            C.validate(op, {**VALID[op], key: 2.0})

    def test_scalar_bounds(self):
        for descriptor in C.capabilities():
            op = descriptor["operation"]
            for key, spec in descriptor["input_schema"]["properties"].items():
                if spec["type"] in ("number", "integer"):
                    for bad in (spec["minimum"]-1, spec["maximum"]+1):
                        with self.subTest(operation=op, key=key, bad=bad):
                            with self.assertRaises(ValueError):
                                C.validate(op, {**VALID[op], key: bad})

    def test_all_enum_values_and_unknown_values(self):
        for descriptor in C.capabilities():
            op = descriptor["operation"]
            for key, spec in descriptor["input_schema"]["properties"].items():
                if "enum" in spec:
                    for value in spec["enum"]:
                        self.assertEqual(C.validate(op, {**VALID[op], key: value})[key], value)
                    for bad in ("UNKNOWN", "Wood", None, [], {}, True):
                        with self.assertRaises(ValueError):
                            C.validate(op, {**VALID[op], key: bad})

    def test_color_has_exact_shape_and_is_copied(self):
        op = "studio.create.material"
        for bad in ([0, 1], [0, 1, 0, 1], (0, 1, 0), [True, 0, 0], [math.nan, 0, 0],
                    [0, math.inf, 0], [-.1, 0, 0], [0, 1.01, 0], "#ffffff"):
            with self.assertRaises(ValueError):
                C.validate(op, {**VALID[op], "color": bad})
        color = [0, .5, 1]
        clean = C.validate(op, {**VALID[op], "color": color})
        clean["color"][0] = .1
        self.assertEqual(color, [0, .5, 1])

    def test_boolean_and_cross_field_constraints(self):
        motion = VALID["studio.create.motion"]
        for bad in (0, 1, "true", None):
            with self.assertRaises(ValueError):
                C.validate("studio.create.motion", {**motion, "loop": bad})
        for op in ("studio.create.motion", "studio.create.camera"):
            for start, end in ((20, 20), (21, 20), (1, 10002), (100000, 100000)):
                with self.assertRaises(ValueError):
                    C.validate(op, {**VALID[op], "start": start, "end": end})
            C.validate(op, {**VALID[op], "start": 90000, "end": 100000})
        with self.assertRaises(ValueError):
            C.validate("studio.create.scatter", {**VALID["studio.create.scatter"],
                       "min_scale": 2, "max_scale": 1})
        for op, fields in (("studio.create.scatter", {"name": "Tree"}),
                           ("studio.create.scatter", {"terrain": "Forest"}),
                           ("studio.create.camera", {"name": "Asset"}),
                           ("studio.create.rig", {"name": "Asset"})):
            with self.assertRaises(ValueError):
                C.validate(op, {**VALID[op], **fields})

    def test_schemas_are_independent_and_complete(self):
        descriptors = C.capabilities()
        self.assertEqual({x["operation"] for x in descriptors}, set(C.OPS))
        for entry in descriptors:
            op = entry["operation"]
            self.assertEqual(entry["workspace"], C.OPS[op])
            self.assertEqual(entry["read_only"], op in C.READ_ONLY)
            self.assertEqual(entry["checkpoint_before_change"], op not in C.READ_ONLY)
            self.assertFalse(entry["input_schema"]["additionalProperties"])
        descriptors[1]["input_schema"]["properties"]["kind"]["enum"].append("unsafe")
        self.assertNotIn("unsafe", C.capabilities()[1]["input_schema"]["properties"]["kind"]["enum"])
        json.dumps(C.catalog(), allow_nan=False)

    def test_catalog_is_truthful_and_budgeted(self):
        catalog = C.catalog()
        self.assertFalse(catalog["neural_3d_generation"])
        self.assertFalse(catalog["existing_animation_overwritten"])
        self.assertFalse(catalog["physical_device_performance_guaranteed"])
        self.assertIn("not humanoid", catalog["rig_scope"])
        self.assertEqual(catalog["limits"]["terrain_vertices"], 129**2)
        self.assertEqual(catalog["limits"]["scatter_instances"], 10000)
        for kind in C.MODEL_KINDS:
            for detail in (1, 2, 3):
                estimate = C.estimate_model(kind, detail)
                self.assertTrue(estimate["conservative_upper_bound"])
                self.assertLessEqual(estimate["triangles"]*180, C.MAX_SCATTER_TRIANGLES)


if __name__ == "__main__":
    unittest.main()
