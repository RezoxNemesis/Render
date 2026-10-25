# SPDX-License-Identifier: GPL-2.0-or-later
"""P01 host contracts: real native viewport data types via isolated bpy fixture."""
import importlib.util
from pathlib import Path
import types
import unittest

SOURCE=Path(__file__).resolve().parents[2]/"full-app/scripts/omega/phase01_engine.py"
spec=importlib.util.spec_from_file_location("render_omega_engine_p01",SOURCE)
p01=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p01)


class Element:
    def __init__(self, name="TestObj", mesh="SharedData", scale=(1,1,1)):
        self.name=name
        self.type="MESH"
        self.scale=scale
        self.data=types.SimpleNamespace(name=mesh)
        self.matrix_world=[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]


class Scene(dict):
    def __init__(self):
        super().__init__()
        self.name="NativeTest"
        self.render=types.SimpleNamespace(engine="CYCLES",resolution_x=3840,
            resolution_y=2160,resolution_percentage=100,fps=24,fps_base=1.0)
        self.objects=[Element("WheelA",scale=(1,1,.3)),Element("WheelB",scale=(1,1,1))]


def fake():
    scene=Scene()
    space=types.SimpleNamespace(clip_start=.001,clip_end=1000.,
        shading=types.SimpleNamespace(show_xray=True),
        overlay=types.SimpleNamespace(show_wireframes=True))
    area=types.SimpleNamespace(type="VIEW_3D",spaces=types.SimpleNamespace(active=space),
        tag_redraw=lambda:None)
    names=("OFF","FXAA","8","16","32")
    enumeration=types.SimpleNamespace(enum_items=[
        types.SimpleNamespace(identifier=n) for n in names])
    system=types.SimpleNamespace(viewport_aa="FXAA",
        bl_rna=types.SimpleNamespace(properties={"viewport_aa":enumeration}))
    context=types.SimpleNamespace(scene=scene,
        window=types.SimpleNamespace(screen=types.SimpleNamespace(areas=[area])),
        preferences=types.SimpleNamespace(system=system))
    bpy=types.SimpleNamespace(context=context,app=types.SimpleNamespace(
        background=False,version_string="5.3-native-double"))
    return {"scene":scene,"bpy":bpy},space,system


class EnginePhaseContracts(unittest.TestCase):
    def test_validate_denies_unsafe_config_and_bad_numbers(self):
        for args in [
            {"mode":"apply","clip_start":1.},
            {"mode":"apply","clip_start":1e-7,"clip_end":1e9},
            {"mode":"apply","xray":"false"},
            {"mode":"apply","anti_alias":"DROP_TABLE"},
            {"mode":"apply","clip_start":float("nan"),"clip_end":100},
            {"mode":"inspect","clip_start":1},
            {"mode":"restore","xray":False},
            {"mode":"apply"},
        ]:
            with self.assertRaises(ValueError):
                p01.validate("omega.engine.viewport_profile",args)
        with self.assertRaises(ValueError):
            p01.validate("omega.engine.diagnose",{"python":"exec(...)"})
        with self.assertRaises(ValueError):
            p01.validate("omega.engine.diagnose",{"max_objects":True})

    def test_viewport_apply_restore_no_final_render_change(self):
        context,space,system=fake()
        baseline=p01._renderer(context["scene"]).copy()
        before=p01.execute("omega.engine.viewport_profile",{"mode":"inspect"},context)
        self.assertEqual(before["viewports_after"][0]["clip_start"],.001)
        result=p01.execute("omega.engine.viewport_profile",{
            "mode":"apply","clip_start":.05,"clip_end":500.,
            "xray":False,"wire_overlay":False,"anti_alias":"8"},context)
        self.assertTrue(result["native_execution_verified"])
        self.assertTrue(result["render_quality_unchanged"])
        self.assertFalse(result["quality_reduced"])
        self.assertFalse(result["visual_quality_verified"])
        self.assertEqual(space.clip_start,.05)
        self.assertEqual(space.clip_end,500.)
        self.assertFalse(space.shading.show_xray)
        self.assertFalse(space.overlay.show_wireframes)
        self.assertEqual(system.viewport_aa,"8")
        self.assertIn("_omega_p01_viewport_before",context["scene"])
        self.assertEqual(baseline,p01._renderer(context["scene"]))
        with self.assertRaises(ValueError):
            p01.execute("omega.engine.viewport_profile",{"mode":"apply","xray":True},context)
        restored=p01.execute("omega.engine.viewport_profile",{"mode":"restore"},context)
        self.assertEqual(restored["viewports_after"][0]["clip_start"],.001)
        self.assertTrue(space.shading.show_xray)
        self.assertTrue(space.overlay.show_wireframes)
        self.assertEqual(system.viewport_aa,"FXAA")
        self.assertNotIn("_omega_p01_viewport_before",context["scene"])
        self.assertEqual(baseline,p01._renderer(context["scene"]))

    def test_engine_diagnostic_keeps_unproven_gpu_claims_false(self):
        context,space,_=fake()
        # Exact same shared Blender mesh datablock and world transform is only
        # a coincidence candidate; no invented driver or z-fighting diagnosis.
        context["scene"].objects[1].data.name="SharedData"
        status=p01.execute("omega.engine.diagnose",{"max_objects":32},context)
        self.assertTrue(status["native_bpy_present"])
        self.assertFalse(status["android_vulkan_driver_verified"])
        self.assertFalse(status["first_vulkan_pixel_observed"])
        self.assertFalse(status["visual_quality_verified"])
        self.assertEqual(1,len(status["mesh_warnings"]["identical_mesh_transform_candidates"]))
        self.assertIn("WheelA",status["mesh_warnings"]["nonuniform_scale_candidates"])
        self.assertEqual(3840,status["render"]["resolution_x"])

    def test_headless_inspection_is_read_only_but_not_a_window_success(self):
        context,_,_=fake()
        context["bpy"].context.window=None
        report=p01.execute("omega.engine.viewport_profile",{},context)
        self.assertFalse(report["native_viewport_available"])
        self.assertIn("NO_NATIVE_VIEW3D_WINDOW_IN_CURRENT_CONTEXT",report["warnings"])
        with self.assertRaisesRegex(ValueError,"NATIVE_VIEWPORT_NOT_OPEN"):
            p01.execute("omega.engine.viewport_profile",
                {"mode":"apply","xray":False},context)

if __name__=="__main__":
    unittest.main()
