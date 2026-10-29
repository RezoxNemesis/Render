# SPDX-License-Identifier: GPL-2.0-or-later
"""Cross-boundary registration and preservation tests for Animation Studio."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_animation_suite as Suite
import render_production_contract as Production
import render_unified_contract as Plans


class AnimationStudioIntegrationTests(unittest.TestCase):
    def test_every_typed_operation_crosses_android_native_plan_and_packaging(self):
        bridge = (ROOT / "app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        android = set(re.findall(r'"(studio\.[a-z.]+)"', bridge))
        self.assertTrue(set(Suite.OPS) <= android)
        self.assertTrue(set(Suite.OPS) <= Production.OPERATIONS)
        self.assertTrue(set(Suite.OPS) <= set(Plans.PROGRAM_OPS))
        self.assertTrue(Suite.READ_ONLY <= Plans.READ_ONLY)
        self.assertTrue(set(Suite.OPS) - Suite.READ_ONLY <= Plans.MUTATING)
        workspaces = {row[0] for row in Plans.WORKSPACES}
        self.assertTrue(set(Suite.OPS.values()) <= workspaces)
        packager = (ROOT / "tools/assemble_full_native.py").read_text()
        for contract, implementation in Suite.MODULES:
            for name in (contract, implementation):
                self.assertIn('"' + name + '.py"', packager)
        self.assertIn('"render_animation_ui.py"', packager)

    def test_descriptors_match_read_only_and_reject_unknown_payload_fields(self):
        descriptors = Suite.capabilities()
        self.assertEqual(len(descriptors), len(Suite.OPS))
        for row in descriptors:
            self.assertEqual(row["read_only"], row["operation"] in Suite.READ_ONLY)
            self.assertFalse(row["input_schema"]["additionalProperties"])
            with self.assertRaises(ValueError):
                Suite.validate(row["operation"], {"python": "no execution"})

    def test_typed_plan_accepts_new_workflow_and_preserves_original_motion_tools(self):
        plan = Plans.plan({"steps": [
            {"operation": "studio.animation.layer.create", "payload": {"name": "Foreground"}},
            {"operation": "studio.finish.inspect", "payload": {}}]})
        self.assertEqual(len(plan["steps"]), 2)
        for op in ("studio.motion.action.create", "studio.motion.nla.create",
                   "studio.create.model", "animation.clip.create", "studio.ik.create"):
            self.assertIn(op, Production.OPERATIONS)
            self.assertIn(op, Plans.PROGRAM_OPS)
        with self.assertRaises(ValueError):
            Production.validate_envelope({"operation": "studio.animation.execute_python"})


if __name__ == "__main__":
    unittest.main()
