# SPDX-License-Identifier: GPL-2.0-or-later
"""Guard ten external benchmark references from pretend workflow equivalence."""
import math
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_workflow_contract as W
import render_unified_contract as Studio
import render_agent_fastlane_contract as Fast

class ExternalBenchmarkContracts(unittest.TestCase):
    def test_exact_ten_owner_external_videos_and_nonparity(self):
        clips=[x[0] for x in W.BENCHMARKS]
        self.assertEqual(len(clips),10)
        self.assertEqual(len(set(clips)),10)
        self.assertIn("1000071923.mp4",clips)
        self.assertIn("1000071924.mp4",clips)
        self.assertIn("1000071906.mp4",clips)
        self.assertIn("1000071896.mp4",clips)
        self.assertIn("1000071925.mp4",clips)
        caps=W.capabilities()
        self.assertEqual(len(caps),len(W.OPS))
        for entry in caps:
            self.assertFalse(entry["guarantees_vendor_parity"])
            self.assertEqual(entry["operation"] in W.READ_ONLY,entry["read_only"])
            self.assertEqual(entry["operation"] in W.READ_ONLY,
                             not entry["checkpoint_before_change"])
            self.assertIn(entry["operation"],Studio.PROGRAM_OPS)
        self.assertFalse(Studio.catalog()["concurrent_scene_edits"])

    def test_no_arbitrary_code_remote_filepath_or_unbounded_geometry(self):
        valid={"object":"BridgeMesh","expected_vertices":16,
               "expected_polygons":8,
               "loops":[[0,1,2,3],[4,5,6,7]]}
        self.assertEqual(W.validate("studio.mesh.bridge_loops",valid),valid)
        for bad in (
           dict(valid,loops=[[0,1,2,3],[4,5,6]]),
           dict(valid,loops=[[0,1,2,3],[0,5,6,7]]),
           dict(valid,expected_vertices="16"),
           dict(valid,object="../../private"),
           dict(valid,extra_code="bpy.ops.wm.read_homefile()"),
           dict(valid,loops=[list(range(66)),list(range(66,132))]),
        ):
            with self.subTest(bad=str(bad)[:64]):
                with self.assertRaises(ValueError):W.validate("studio.mesh.bridge_loops",bad)

    def test_simulation_and_procedural_budgets(self):
        valid={"source":"Rock","name":"Forest","count":20,
               "min":[-5,-5,0],"max":[5,5,2],"seed":42}
        self.assertEqual(W.validate("studio.procedural.scatter",valid),valid)
        for bad in (
          dict(valid,count=1000),dict(valid,count=True),
          dict(valid,seed=-1),dict(valid,max=[-10,0,1]),
          dict(valid,min=[float("nan"),-1,0]),
          dict(valid,source="shell.exec()"),
          dict(valid,scale_min=5,scale_max=.1),
        ):
            with self.assertRaises(ValueError):W.validate("studio.procedural.scatter",bad)
        for bad in (
          {"object":"Sim","type":"NONE"},
          {"object":"Sim","mass":-1},
          {"object":"Sim","bounce":2},
          {"object":"Sim","dry_run":"true"}
        ):
            with self.assertRaises(ValueError):W.validate("studio.sim.rigidbody",bad)

    def test_animation_and_compositor_require_explicit_parameters(self):
        keys=[{"frame":1,"rotation_euler":[0,0,0]},
              {"frame":12,"rotation_euler":[0,.2,0]}]
        action={"name":"Walk","rig":"Character","bone":"Arm","keys":keys}
        self.assertEqual(W.validate("studio.motion.action.create",action),action)
        for bad in (dict(action,keys=keys[::-1]),
                    dict(action,keys=[keys[0]]),
                    dict(action,keys=[dict(keys[0],rotation_euler=[0,float("inf"),0]),keys[1]]),
                    dict(action,allow_existing_action="yes")):
            with self.assertRaises(ValueError):W.validate("studio.motion.action.create",bad)
        self.assertEqual(W.validate("studio.compositor.grade",{"name":"Final","activate":False})["name"],"Final")
        for bad in (
            {"name":"Final","activate":"true"},
            {"name":"Final","hue":math.nan},
            {"name":"Final","python":"bpy"},
        ):
            with self.assertRaises(ValueError):W.validate("studio.compositor.grade",bad)
        with self.assertRaises(ValueError):
            W.validate("studio.drawing.strokes",{
                "name":"Ink","strokes":[[[0,0],[1,1]]*70]})

    def test_fastlane_reads_no_mutating_tools(self):
        for op in W.READ_ONLY:self.assertIn(op,Fast.READS)
        for op in set(W.OPS)-W.READ_ONLY:self.assertNotIn(op,Fast.READS)
        self.assertEqual(len(Fast.batch({"reads":[
            {"operation":"studio.benchmark.catalog","payload":{}},
            {"operation":"studio.benchmark.audit","payload":{}},
            {"operation":"studio.compositor.inspect","payload":{}}
        ]})),3)
        with self.assertRaises(ValueError):
            Fast.batch({"reads":[{"operation":"studio.mesh.bridge_loops","payload":{}}]})

    def test_android_bridge_and_packaging_exact_names(self):
        java=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        contract=(ROOT/"full-app/scripts/render_production_contract.py").read_text()
        ui=(ROOT/"full-app/scripts/render_unified_workspace.py").read_text()
        pack=(ROOT/"tools/assemble_full_native.py").read_text()
        for op in W.OPS:
            self.assertIn(op,java)
            self.assertIn(op,contract)
            self.assertIn(op,ui if "benchmark" in op else java)
        for filename in ("render_workflow_contract.py","render_workflow_ops.py"):
            self.assertIn(filename,pack)

if __name__=="__main__":unittest.main()
