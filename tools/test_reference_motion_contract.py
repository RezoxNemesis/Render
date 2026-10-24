# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-only security and input-contract regressions. No bpy/device claims."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/"full-app/scripts/render_reference_motion_contract.py"
spec=importlib.util.spec_from_file_location("render_reference_motion_contract",source)
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)

class ReferenceMotionContracts(unittest.TestCase):
    def test_scoped_image_video_assets_and_split_bounds(self):
        good="a"*64+".png"
        self.assertEqual(C.workspace({"asset":good})["mode"],"SPLIT")
        self.assertEqual(C.workspace({"asset":"b"*64+".mp4","mode":"CAMERA","frame":30})["frame"],30)
        self.assertEqual(C.workspace({"asset":"b"*64+".mp4","preview_asset":good})["preview_asset"],good)
        for invalid in [
            {"asset":good,"preview_asset":"b"*64+".jpg"},
            {"asset":"b"*64+".mp4","preview_asset":"a"*64+".mp4"},
            {"asset":"b"*64+".mp4","preview_asset":"../outside.jpg"},
        ]:
            with self.assertRaises(ValueError):C.workspace(invalid)
        for asset in ("../../Gallery/picture.png","/storage/emulated/0/a.mp4","c"*64+".exe","a"*64+"xpng"):
            with self.assertRaises(ValueError):C.workspace({"asset":asset})
        for factor in (0.0,.15,.8,1.0,float("nan")):
            with self.assertRaises(ValueError):C.workspace({"asset":good,"split_factor":factor})
        with self.assertRaises(ValueError):C.workspace({"asset":good,"arbitrary_python":"import os"})
    def test_multiview_requires_measurable_bounded_correspondence(self):
        one={"camera":"Front","reference":{"eye":[.3,.4],"nose":[.5,.5]},
             "model":{"eye":1,"nose":3}}
        self.assertEqual(len(C.multiview({"object":"Figure","views":[one]})["views"]),1)
        with self.assertRaises(ValueError):
            C.multiview({"object":"Figure","views":[one,one]})
        with self.assertRaises(ValueError):
            C.multiview({"object":"Figure","views":[dict(one,model={"eye":1})]})
        with self.assertRaises(ValueError):
            C.multiview({"object":"Figure","views":[dict(one,camera="../outside")]})
    def test_landmark_fit_requires_vertex_revision_and_safe_strength(self):
        valid={"object":"Body","camera":"Front","expected_vertices":100,
               "reference":{"left":[.2,.3],"right":[.8,.3]},
               "model":{"left":10,"right":11},
               "strength":.7,"max_displacement":.12,"dry_run":True}
        self.assertEqual(C.fit(valid)["expected_vertices"],100)
        invalid=[
            dict(valid,strength=1.5),
            dict(valid,max_displacement=100),
            dict(valid,model={"left":10,"right":10}),
            dict(valid,expected_vertices=11),
            dict(valid,reference={"left":[0,0]}),
            dict(valid,dry_run="True"),
        ]
        for test in invalid:
            with self.subTest(bad=test):
                with self.assertRaises(ValueError):C.fit(test)

    def test_real_clip_channels_bounded_and_non_overlapping(self):
        clip={"rig":"BodyRig","name":"LookAndBlink","interpolation":"BEZIER","nla":True,
            "poses":[
              {"frame":1,"bones":[{"bone":"Head","rotation_euler":[0,0,0],"location":[0,0,0]}],
               "shapes":[{"object":"Face","key":"Blink","value":0.0}]},
              {"frame":13,"bones":[{"bone":"Head","rotation_euler":[0,0.3,0.1]}],
               "shapes":[{"object":"Face","key":"Blink","value":1.0}]}]}
        self.assertEqual(C.clip(clip)["name"],"LookAndBlink")
        for change in [
          {"poses":[dict(clip["poses"][0]),dict(clip["poses"][0])]},
          {"interpolation":"unsafe_script"},
          {"poses":clip["poses"][:1]},
          {"poses":[dict(clip["poses"][0],bones=[{"bone":"Head","rotation_euler":[0,0,float("nan")]}]),clip["poses"][1]]},
          {"poses":[dict(clip["poses"][0],bones=[{"bone":"Head","rotation_quaternion":[0,1,1,1]}]),clip["poses"][1]]},
        ]:
            invalid=dict(clip,**change)
            with self.subTest(change=list(change)):
                with self.assertRaises(ValueError):C.clip(invalid)
    def test_motion_sample_frames_strict(self):
        good={"rig":"BodyRig","bones":["Head","Hand"],"frames":[1,5,10]}
        self.assertEqual(C.audit(good)["frames"],[1,5,10])
        for frames in ([1,1],[10,8],[],[1,2.5],[1,100001]):
            with self.assertRaises(ValueError):C.audit(dict(good,frames=frames))
    def test_dispatch_and_engine_packaging_use_explicit_allowlist(self):
        py=(ROOT/"full-app/scripts/render_production_contract.py").read_text()
        dispatch=(ROOT/"full-app/scripts/render_production.py").read_text()
        android=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        pack=(ROOT/"tools/assemble_full_native.py").read_text()
        for action in ("reference.workspace.open","reference.workspace.inspect","reference.fit.landmarks",
                       "reference.compare.multiview","animation.clip.create",
                       "animation.clip.inspect","animation.motion.audit"):
            self.assertIn(action,py);self.assertIn(action,dispatch);self.assertIn(action,android)
        self.assertIn('"render_reference_motion.py"',pack)
        self.assertIn('"render_reference_motion_contract.py"',pack)
        self.assertNotIn('android.permission.READ_MEDIA_IMAGES',android)
        self.assertNotIn('eval(', (ROOT/"full-app/scripts/render_reference_motion.py").read_text())

if __name__=="__main__":unittest.main()
