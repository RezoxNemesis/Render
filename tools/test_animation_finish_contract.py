# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure validation tests for the animation finishing interface."""
import copy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "full-app/scripts"))
import render_animation_finish_contract as C


VALID = {"studio.finish.inspect": {}, "studio.finish.preset": {"preset": "standard"},
         "studio.keyframes.inspect": {"action": "Walk.001"},
         "studio.keyframes.retime": {"action": "Walk.001", "expected_sha256": "a" * 64, "scale": 2}}


class FinishContractTests(unittest.TestCase):
    def test_defaults_are_idempotent_and_input_is_unchanged(self):
        for operation, payload in VALID.items():
            original = copy.deepcopy(payload)
            result = C.validate(operation, payload)
            self.assertEqual(original, payload)
            self.assertEqual(result, C.validate(operation, result))
        self.assertFalse(C.validate("studio.keyframes.retime", VALID["studio.keyframes.retime"])["allow_shared_action"])

    def test_unknown_operations_payload_shapes_and_fields_are_rejected(self):
        for operation in ("studio.finish.eval", [], None, 1):
            with self.assertRaises(ValueError):
                C.validate(operation, {})
        for operation, payload in VALID.items():
            for bad in (None, [], True, "{}"):
                with self.assertRaises(ValueError):
                    C.validate(operation, bad)
            for field in ("python", "filepath", "command", "url"):
                with self.assertRaises(ValueError):
                    C.validate(operation, {**payload, field: "something"})

    def test_required_fields_and_independent_schema_copies(self):
        for descriptor in C.capabilities():
            operation = descriptor["operation"]
            self.assertEqual(descriptor["read_only"], operation in C.READ_ONLY)
            self.assertEqual(descriptor["checkpoint_before_change"], operation not in C.READ_ONLY)
            for required in descriptor["input_schema"]["required"]:
                payload = dict(VALID[operation]); payload.pop(required)
                with self.assertRaises(ValueError):
                    C.validate(operation, payload)
        first = C.capabilities()
        first[1]["input_schema"]["properties"]["preset"]["enum"].append("unsafe")
        self.assertNotIn("unsafe", C.capabilities()[1]["input_schema"]["properties"]["preset"]["enum"])

    def test_dimensions_are_even_bounded_integers(self):
        for dimension in ("width", "height"):
            for value in (True, 2., -2, 0, 15, 17, 8194, math.inf, "1920"):
                with self.assertRaises(ValueError):
                    C.validate("studio.finish.preset", {"preset": "draft", dimension: value})
        C.validate("studio.finish.preset", {"preset": "final", "width": 8192, "height": 16})

    def test_timing_requires_ordered_bounded_frames(self):
        for payload in ({"start": 0}, {"end": 100001}, {"start": 4, "end": 3},
                        {"fps": 0}, {"fps": 121}, {"fps": True}):
            with self.assertRaises(ValueError):
                C.validate("studio.finish.preset", {"preset": "standard", **payload})
        C.validate("studio.finish.preset", {"preset": "standard", "start": 50, "end": 50})

    def test_retime_scale_is_positive_finite_and_bounded(self):
        operation = "studio.keyframes.retime"
        for scale in (True, 0, -.1, .049, 20.1, math.nan, math.inf, 10**1000):
            with self.assertRaises(ValueError):
                C.validate(operation, {**VALID[operation], "scale": scale})
        for field in ("offset", "pivot"):
            for value in (math.nan, math.inf, True, "1", 100001):
                with self.assertRaises(ValueError):
                    C.validate(operation, {**VALID[operation], field: value})

    def test_revision_and_shared_flags_are_strict(self):
        operation = "studio.keyframes.retime"
        for revision in ("a" * 63, "b" * 65, "X" * 64, None, True):
            with self.assertRaises(ValueError):
                C.validate(operation, {**VALID[operation], "expected_sha256": revision})
        for flag in (0, 1, "true", None):
            with self.assertRaises(ValueError):
                C.validate(operation, {**VALID[operation], "allow_shared_action": flag})

    def test_existing_action_names_allow_unicode_but_not_control_characters(self):
        for name in ("Walk Cycle.003", "歩行", "2D character"):
            self.assertEqual(C.validate("studio.keyframes.inspect", {"action": name})["action"], name)
        for name in ("", "a" * 129, "bad\nname", "bad\x00name", 1, None):
            with self.assertRaises(ValueError):
                C.validate("studio.keyframes.inspect", {"action": name})


if __name__ == "__main__":
    unittest.main()
