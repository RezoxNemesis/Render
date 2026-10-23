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

    def launch_fixture(self, **settings):
        files = Path(self.tmp.name) / "files"
        script = files / "blender/5.3/scripts/startup/render_agent_startup.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.touch()
        config = {"schema_version": 1, "target_package": "com.rezox.render",
                  "command_spool_enabled": True, "mobile_mode": "landscape"}
        config.update(settings)
        (files / "render_native_launch.json").write_text(json.dumps(config))
        return files, script

    def test_native_bridge_without_environment_uses_private_launch_handoff(self):
        files, script = self.launch_fixture()
        root, mode = self.module._launch_settings({}, script)
        self.assertEqual(str(files / "render_bpy_jobs"), root)
        self.assertEqual("landscape", mode)
        self.assertFalse((files / "render_bpy_jobs/ready").exists())

    def test_private_handoff_replaces_stale_environment_without_accepting_paths(self):
        files, script = self.launch_fixture(spool="/some/foreign/path")
        root, mode = self.module._launch_settings({"RENDER_AGENT_SPOOL": "/stale"}, script)
        self.assertEqual(str(files / "render_bpy_jobs"), root)

    def test_native_launch_rejects_wrong_package_and_bad_schema(self):
        for values in ({"target_package": "other.app"}, {"schema_version": 2},
                       {"command_spool_enabled": False}, {"mobile_mode": "invalid"}):
            with self.subTest(values=values):
                _, script = self.launch_fixture(**values)
                with self.assertRaisesRegex(ValueError, "INVALID_NATIVE_LAUNCH_CONFIGURATION"):
                    self.module._launch_settings({}, script)

    def test_native_launch_rejects_spool_symlink(self):
        files, script = self.launch_fixture()
        (files / "render_bpy_jobs").symlink_to(Path(self.tmp.name), target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "NATIVE_LAUNCH_SPOOL_SYMLINK"):
            self.module._launch_settings({}, script)

    def test_no_private_handoff_does_not_enable_host_command_executor(self):
        self.assertEqual(("", ""), self.module._launch_settings({}, MODULE))

    def test_native_bpy_cube_operation_and_postcondition(self):
        report = self.job("blender.object.add_cube",
                          {"name":"HeroCube", "size":2.0, "location":[3,1,5]})
        self.assertEqual("succeeded", report["state"])
        self.assertEqual("HeroCube", report["result"]["name"])
        self.assertEqual([3.0,1.0,5.0], report["result"]["location"])
        self.assertEqual(2, len(self.objects))

    def test_rejects_invalid_primitive_and_material_before_bpy(self):
        with self.assertRaisesRegex(ValueError,"INVALID_PRIMITIVE_KIND"):
            self.module._dispatch({"action":"blender.object.add_primitive",
                                   "args":{"kind":"python"}})
        with self.assertRaisesRegex(ValueError,"INVALID_OBJECT_NAME"):
            self.module._dispatch({"action":"blender.material.assign",
                                   "args":{"name":"../unauthorized"}})

    def test_unknown_action_cannot_run_arbitrary_python(self):
        report = self.job("python.eval", {"code":"import os; os.unlink('/tmp/project')"})
        self.assertEqual("failed", report["state"])
        self.assertEqual("NATIVE_BLENDER_ACTION_UNAVAILABLE", report["error"])
        self.assertEqual(1, len(self.objects))

    def test_blender_hud_completion_follows_durable_native_result(self):
        events=[]
        self.module._native_ui_event=lambda method,value:events.append((method,value))
        report=self.job("blender.object.add_cube",{"name":"HudCube"})
        self.assertEqual("succeeded",report["state"])
        self.assertEqual(["command_started","command_finished"],[method for method,value in events])
        result_path=Path(self.tmp.name)/"results"/(self.request_id+".json")
        self.assertTrue(result_path.is_file())
        self.assertEqual(report,events[-1][1])

    def test_unwritten_native_result_cannot_confirm_blender_arrow(self):
        events=[]
        self.module._native_ui_event=lambda method,value:events.append((method,value))
        def no_write(*args):raise OSError("test unavailable disk")
        self.module._write_result=no_write
        pending=Path(self.tmp.name)/"pending";pending.mkdir()
        (pending/(self.request_id+".json")).write_text(json.dumps(dict(
            id=self.request_id,action="blender.object.add_cube",args={"name":"Unconfirmed"},deadline=time.time()+60)))
        self.module._poll()
        self.assertEqual("recovery_required",events[-1][1]["state"])
        self.assertTrue((Path(self.tmp.name)/"working"/(self.request_id+".json")).is_file())

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
        self.assertFalse(landscape["focused"])
        portrait=self.module._dispatch({"action":"blender.ui.set_mode",
                                        "args":{"mode":"portrait"}})
        self.assertEqual(1.34,portrait["ui_scale"])
        self.assertTrue(portrait["focused"])
        restored=self.module._dispatch({"action":"blender.ui.set_mode",
                                        "args":{"mode":"landscape"}})
        self.assertFalse(restored["focused"])
        focused=self.module._dispatch({"action":"blender.ui.focus_viewport","args":{}})
        self.assertTrue(focused["preserves_other_editors"])
        self.assertTrue(focused["focused"])
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
