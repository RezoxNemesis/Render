# SPDX-License-Identifier: GPL-2.0-or-later
"""Host regression: viewport quality controls never inject code or alter render."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_viewport_fidelity_contract as F
import render_unified_contract as Studio

class ViewportPhase1ContractTests(unittest.TestCase):
    def test_complete_phase1_registry_is_native_and_bounded(self):
        definitions={x["operation"]:x for x in F.capabilities()}
        self.assertEqual(set(definitions),F.OPS)
        for operation in definitions:
            self.assertIn(operation,Studio.PROGRAM_OPS)
            self.assertFalse(definitions[operation]["full_geometry_repair_claimed"])
            self.assertFalse(definitions[operation]["scene_quality_changed"])
        self.assertTrue(F.MUTATING.isdisjoint(F.READ_ONLY))
        self.assertFalse(Studio.catalog()["concurrent_scene_edits"])

    def test_expensive_preview_explicit_opt_in_and_safe_presets(self):
        for preset in F.PROFILES:
            p={"profile":preset}
            if preset=="MATERIAL_REVIEW":
                with self.assertRaises(ValueError):F.validate("studio.preview.profile.apply",p)
                p["allow_expensive_shader_compile"]=True
            self.assertEqual(F.validate("studio.preview.profile.apply",p),p)
        for bad in (
            {"profile":"ZBRUSH_NANITE"},
            {"profile":"MATERIAL_REVIEW","allow_expensive_shader_compile":"yes"},
            {"profile":"DETAIL_INSPECT","precision_target_clipping":True},
            {"profile":"CLEAN_SOLID","object":"../../secret"},
            {"profile":"LOW_NOISE","viewport_index":-1},
            {"profile":"CLEAN_SOLID","viewport_index":123},
            {"profile":"DETAIL_INSPECT","expected_sha256":"fake"},
            {"profile":"CLEAN_SOLID","python":"exec(open('/sdcard'))"},
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                F.validate("studio.preview.profile.apply",bad)

    def test_finite_and_revision_guard(self):
        digest=F.digest({"x":1,"y":2})
        self.assertEqual(len(digest),64)
        self.assertEqual(F.digest({"y":2,"x":1}),digest)
        for bad in (float("inf"),float("nan"),None,"32"):
            with self.assertRaises(ValueError):F.number(bad,1,100)
        with self.assertRaises(ValueError):F.validate("studio.preview.diagnose",{"max_candidates":5000})
        with self.assertRaises(ValueError):F.validate("studio.preview.profile.restore",{"expected_sha256":"bad"})

    def test_global_antialiasing_requires_explicit_true(self):
        for bad in (
            {"allow_global_preferences":False,"level":"16"},
            {"allow_global_preferences":"true","level":"16"},
            {"allow_global_preferences":True,"level":"unknown"},
            {"allow_global_preferences":True,"restore":True,"level":"16"},
            {"allow_global_preferences":True,"restore":1},
        ):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                F.validate("studio.preview.aa.configure",bad)
        allowed={"allow_global_preferences":True,"level":"BEST_SUPPORTED"}
        self.assertEqual(F.validate("studio.preview.aa.configure",allowed),allowed)
        self.assertTrue(F.capabilities()[-1]["input_schema"]["additionalProperties"] is False)

    def test_exact_routing_and_original_native_engine_architecture(self):
        runtime=(ROOT/"tools/assemble_full_native.py").read_text()
        contract=(ROOT/"full-app/scripts/render_production_contract.py").read_text()
        binding=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        studio=(ROOT/"full-app/scripts/render_unified_workspace.py").read_text()
        session=(ROOT/"full-app/scripts/render_session_tools.py").read_text()
        for op in F.OPS:
            self.assertIn(op,contract)
            self.assertIn(op,binding)
            self.assertIn(op,studio)
        for name in ("render_viewport_fidelity_contract.py",
                     "render_viewport_fidelity.py","render_viewport_fidelity_ui.py"):
            self.assertIn(name,runtime)
        self.assertIn("render_viewport_fidelity_ui.install()",session)
        self.assertIn("global_viewport_aa_modified",session)
        self.assertNotIn("bpy.data.objects.remove(",(ROOT/"full-app/scripts/render_viewport_fidelity.py").read_text())

if __name__=="__main__":unittest.main()
