# SPDX-License-Identifier: GPL-2.0-or-later
"""IK/FK contracts: explicitly named target, no script evaluation or path access."""
import sys
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_ik_contract as C
import render_unified_contract as Unified

class IKContractTests(unittest.TestCase):
    def test_create_real_ik_chain_contract(self):
        request={"rig":"ActorRig","bone":"Shin.L","controller":"FootIK.L",
                 "chain_length":2,"pole":"KneePole.L",
                 "pole_offset":[0,-1,0],"pole_angle":.25}
        self.assertEqual(C.check("studio.ik.create",request),request)
        for change in [
            {"rig":"../../private"},
            {"controller":"FootIK.L","pole":"FootIK.L"},
            {"chain_length":1},
            {"chain_length":20},
            {"pole_angle":2e50},
            {"pole_offset":[0,float("nan"),0]},
            {"executable_python":"import os"},
        ]:
            bad=dict(request,**change)
            with self.subTest(changed=list(change)):
                with self.assertRaises(ValueError):C.check("studio.ik.create",bad)
    def test_keyed_target_revision_and_frame_validation(self):
        good={"rig":"ActorRig","bone":"Shin.L","frame":17,
              "location_world":[1.0,0.0,1.0],
              "expected_sha256":"a"*64}
        self.assertEqual(C.check("studio.ik.target",good),good)
        for bad in [
            dict(good,location_world=[0,float("inf"),0]),
            dict(good,frame=0),
            dict(good,frame="17"),
            dict(good,expected_sha256="not a revision"),
            dict(good,control="REMOTE_MOUSE_TAP"),
            dict(good,dry_run="True"),
            dict(good,source_path="/sdcard/Movies/"),
        ]:
            with self.assertRaises(ValueError):C.check("studio.ik.target",bad)
    def test_ik_fk_blend_rejects_unsafe_parameters(self):
        base={"rig":"Rig","bone":"Elbow","frame":20,
              "influence":0.5,"expected_sha256":"b"*64}
        self.assertEqual(C.check("studio.ik.blend",base),base)
        for value in (-.2,1.2,None,float("nan"),"1"):
            with self.assertRaises(ValueError):
                C.check("studio.ik.blend",dict(base,influence=value))
    def test_exact_native_tool_discovery_and_serial_plan(self):
        ops={x["operation"]:x for x in C.capabilities()}
        self.assertEqual(len(ops),4)
        self.assertTrue(ops["studio.ik.create"]["checkpoint_before_change"])
        self.assertTrue(ops["studio.ik.inspect"]["read_only"])
        self.assertIn("expected_sha256",
                      ops["studio.ik.target"]["input_schema"]["required"])
        for op in ops:
            self.assertIn(op,Unified.PROGRAM_OPS)
        self.assertFalse(Unified.catalog()["concurrent_scene_edits"])
        denied={"name":"Arbitrary unsafe","steps":[
            {"operation":"bpy.ops.pose.ik_add",
             "payload":{"python":"__import__('os')"}}]}
        with self.assertRaises(ValueError):Unified.plan(denied)
    def test_real_runtime_packaged_and_binder_allowlisted(self):
        pack=(ROOT/"tools/assemble_full_native.py").read_text()
        bridge=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        runtime=(ROOT/"full-app/scripts/render_production_contract.py").read_text()
        prod=(ROOT/"full-app/scripts/render_production.py").read_text()
        studio=(ROOT/"full-app/scripts/render_unified_workspace.py").read_text()
        for op in C.OPS:
            self.assertIn(op,bridge)
            self.assertIn(op,runtime)
            self.assertIn(op,studio)
        self.assertIn('"render_ik_control.py"',pack)
        self.assertIn('"render_ik_contract.py"',pack)
        self.assertIn('"studio.ik.create"',prod)
        self.assertNotIn('subprocess.Popen(',studio)

if __name__=="__main__":unittest.main()
