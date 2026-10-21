"""Pure host tests of the Android-only Blender startup adapter using bpy doubles.

A real bpy smoke test will remain necessary for Android device parity.
"""
import importlib.util
import contextlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest

MODULE = Path(__file__).resolve().parents[1] / "full-app/scripts/render_agent_startup.py"

class BlenderBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("RENDER_AGENT_SPOOL")
        os.environ["RENDER_AGENT_SPOOL"] = self.tmp.name
        self.objects = [types.SimpleNamespace(name="Starter", type="MESH")]
        self.scene = types.SimpleNamespace(name="Scene", objects=self.objects,
                                           frame_current=3, render=types.SimpleNamespace(engine="CYCLES"))
        self.context = types.SimpleNamespace(scene=self.scene, object=None)
        self.context.preferences=types.SimpleNamespace(
            view=types.SimpleNamespace(ui_scale=1.0))
        self.context.window=types.SimpleNamespace(
            screen=types.SimpleNamespace(areas=[
                types.SimpleNamespace(type="VIEW_3D")]))
        self.context.temp_override=lambda **kwargs: contextlib.nullcontext()

        def add_cube(size, location):
            ob = types.SimpleNamespace(name="Cube", type="MESH", location=list(location))
            self.objects.append(ob)
            self.context.object = ob
        fake = types.SimpleNamespace(context=self.context,
            app=types.SimpleNamespace(version_string="5.3-test", timers=types.SimpleNamespace(register=lambda *a, **k: None)),
            ops=types.SimpleNamespace(
                mesh=types.SimpleNamespace(primitive_cube_add=add_cube),
                screen=types.SimpleNamespace(
                    screen_full_area=lambda use_hide_panels=False: {"FINISHED"})))
        self.old_bpy = sys.modules.get("bpy")
        sys.modules["bpy"] = fake
        spec = importlib.util.spec_from_file_location("render_agent_native_test", MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.request_id = "0123456789abcdef0123456789abcdef"

    def tearDown(self):
        if self.old_bpy is None: sys.modules.pop("bpy", None)
        else: sys.modules["bpy"] = self.old_bpy
        if self.previous is None: os.environ.pop("RENDER_AGENT_SPOOL", None)
        else: os.environ["RENDER_AGENT_SPOOL"] = self.previous
        self.tmp.cleanup()

    def job(self, action, args, deadline=None):
        pending = Path(self.tmp.name) / "pending"
        pending.mkdir(parents=True, exist_ok=True)
        item = {"id": self.request_id, "action": action, "args": args,
                "deadline": deadline if deadline is not None else time.time()+30}
        (pending / (self.request_id+".json")).write_text(json.dumps(item))
        self.module._poll()
        return json.loads((Path(self.tmp.name)/"results"/(self.request_id+".json")).read_text())

    def test_scene_summary_uses_bpy_context(self):
        report = self.job("blender.scene.summary", {})
        self.assertEqual("succeeded", report["state"])
        self.assertEqual("CYCLES", report["result"]["render_engine"])
        self.assertEqual("Starter", report["result"]["sample_objects"][0]["name"])
        self.assertEqual(1, report["result"]["total_objects"])

    def test_native_bpy_cube_operation_and_postcondition(self):
        report = self.job("blender.object.add_cube",
                          {"name":"HeroCube", "size":2.0, "location":[3,1,5]})
        self.assertEqual("succeeded", report["state"])
        self.assertEqual("HeroCube", report["result"]["name"])
        self.assertEqual([3.0,1.0,5.0], report["result"]["location"])
        self.assertEqual(2, len(self.objects))

    def test_unknown_action_cannot_run_arbitrary_python(self):
        report = self.job("python.eval", {"code":"import os; os.unlink('/tmp/project')"})
        self.assertEqual("failed", report["state"])
        self.assertEqual("NATIVE_BLENDER_ACTION_UNAVAILABLE", report["error"])
        self.assertEqual(1, len(self.objects))

    def test_expired_mutation_never_executes(self):
        report = self.job("blender.object.add_cube", {"name":"TooLate"}, time.time()-5)
        self.assertEqual("failed", report["state"])
        self.assertEqual("COMMAND_EXPIRED", report["error"])
        self.assertEqual(1, len(self.objects))

    def test_mobile_ui_scale_does_not_touch_scene_or_render_quality(self):
        self.assertEqual(1.0,self.context.preferences.view.ui_scale)
        x=self.module._dispatch({"action":"blender.ui.adjust_scale",
                                "args":{"delta":.15}})
        self.assertEqual(1.15,x["ui_scale"])
        self.assertTrue(x["render_quality_unchanged"])
        landscape=self.module._dispatch({"action":"blender.ui.set_mode",
                                         "args":{"mode":"landscape"}})
        self.assertEqual("landscape",landscape["orientation"])
        self.assertEqual(1.18,landscape["ui_scale"])
        portrait=self.module._dispatch({"action":"blender.ui.set_mode",
                                        "args":{"mode":"portrait"}})
        self.assertEqual(1.34,portrait["ui_scale"])
        focused=self.module._dispatch({"action":"blender.ui.focus_viewport","args":{}})
        self.assertTrue(focused["preserves_other_editors"])
        self.assertEqual("CYCLES",self.scene.render.engine)
        self.assertEqual(1,len(self.objects))

    def test_mobile_touch_actions_reject_injection(self):
        for action,args in [
            ("blender.ui.adjust_scale",{"delta":100}),
            ("blender.ui.set_mode",{"mode":"arbitrary"}),
            ("blender.ui.focus_viewport",{"script":"import os"}),
        ]:
            with self.assertRaises(ValueError):
                self.module._dispatch({"action":action,"args":args})

    def test_rejects_nonfinite_and_wrong_type(self):
        for location in [[float('inf'),0,0],["0",0,0],[True,0,0]]:
            with self.assertRaisesRegex(ValueError,"INVALID_CUBE_LOCATION"):
                self.module._dispatch({"action":"blender.object.add_cube",
                                       "args":{"location":location}})

if __name__ == "__main__":
    unittest.main()
