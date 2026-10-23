"""Host tests of Render's Blender-side HUD with explicit bpy/GPU doubles.

No Blender engine, Android device, scene render or actual screenshot is used.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'full-app/scripts/render_native_hud.py'


class NativeHudTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.env=patch.dict(os.environ,{'RENDER_AGENT_SPOOL':self.temp.name+'/render_bpy_jobs'})
        self.env.start();self.addCleanup(self.env.stop)
        self.handlers=[];self.removed=[];self.timers=[];self.redraw=[]
        self.bpy=types.SimpleNamespace(
            app=types.SimpleNamespace(background=False,timers=types.SimpleNamespace(
                register=lambda fn,**kw:self.timers.append(fn),
                is_registered=lambda fn:fn in self.timers,
                unregister=lambda fn:self.timers.remove(fn))),
            types=types.SimpleNamespace(SpaceView3D=types.SimpleNamespace(
                draw_handler_add=self.add_handler,
                draw_handler_remove=lambda handle,region:self.removed.append((handle,region)))),
            context=types.SimpleNamespace(
                region=types.SimpleNamespace(width=640,height=360),region_data=object(),
                scene=types.SimpleNamespace(objects={}),
                window_manager=types.SimpleNamespace(windows=[types.SimpleNamespace(screen=types.SimpleNamespace(
                    areas=[types.SimpleNamespace(type='VIEW_3D',tag_redraw=lambda:self.redraw.append('VIEW_3D'))]))])))
        self.mods=patch.dict(sys.modules,{'bpy':self.bpy});self.mods.start();self.addCleanup(self.mods.stop)
        spec=importlib.util.spec_from_file_location('render_native_hud_test',SCRIPT)
        self.hud=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.hud)
    def add_handler(self,fn,args,region,stage):
        self.handlers.append((fn,args,region,stage));return 'test-handler'
    def worker(self,**overrides):
        data=dict(state='running',action='Rendering animation',stage='Rendering frame 104',progress=60,
                  updated_at_epoch_ms=self.hud.time.time()*1000)
        data.update(overrides)
        path=Path(self.temp.name)/'Production/native_ui_status.json'
        path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(data));return path
    def test_registers_real_blender_post_pixel_hook_once(self):
        self.hud.install(lambda:None);self.hud.install(lambda:None)
        self.assertEqual(1,len(self.handlers));self.assertEqual(('WINDOW','POST_PIXEL'),self.handlers[0][2:])
        self.assertEqual(1,len(self.timers));self.assertTrue(self.hud.snapshot()['installed_in_blender_viewport'])
        self.hud.uninstall();self.assertEqual([('test-handler','WINDOW')],self.removed)
        self.assertFalse(self.hud.snapshot()['installed_in_blender_viewport'])
    def test_failed_timer_registration_removes_viewport_handler(self):
        self.bpy.app.timers.register=lambda *args,**kw:(_ for _ in ()).throw(RuntimeError('test timer failure'))
        with self.assertRaises(RuntimeError):self.hud.install(lambda:None)
        self.assertIsNone(self.hud._handle);self.assertEqual(1,len(self.removed))
    def test_background_mode_does_not_register_editor_ui(self):
        self.bpy.app.background=True;self.hud.install(lambda:None)
        self.assertEqual([],self.handlers)
    def test_native_frame_fraction_drives_bar_without_changing_scene(self):
        self.hud.install(lambda:dict(completed=3,total=5,job_id='a'*32))
        self.hud._refresh();value=self.hud.model();rects=[]
        self.hud.draw_card(value,640,360,lambda *p:rects.append(p),lambda *p:None,lambda *p:None)
        track,fill=rects[-2:];self.assertEqual(.6,fill[2]/track[2])
        self.assertEqual('3/5 checkpointed frames',value['progress_label'])
        self.assertEqual({},self.bpy.context.scene.objects);self.assertEqual(['VIEW_3D'],self.redraw)
    def test_unknown_or_invalid_progress_never_draws_full_bar(self):
        for value in [None,dict(completed=True,total=5),dict(completed=6,total=5),dict(completed=-1,total=5)]:
            self.hud._progress=value
            self.hud.command_started(dict(action='blender.object.add_cube',args={}))
            model=self.hud.model();rects=[]
            self.hud.draw_card(model,640,360,lambda *p:rects.append(p),lambda *p:None,lambda *p:None)
            self.assertIsNone(model['fraction']);self.assertEqual(1,len(rects))
    def test_android_pause_reason_appears_inside_blender_model(self):
        self.worker(state='paused',stage='Waiting for Android to cool')
        self.hud._refresh();value=self.hud.model()
        self.assertEqual('paused',value['state']);self.assertEqual('Waiting for Android to cool',value['stage'])
        self.assertEqual(.6,value['fraction'])
    def test_stale_running_file_is_recovery_not_continuing_work(self):
        self.worker(updated_at_epoch_ms=self.hud.time.time()*1000-40000)
        self.hud._refresh();self.assertEqual('recovery_required',self.hud.model()['state'])
    def test_readonly_status_never_follows_symlink(self):
        p=self.worker();outside=Path(self.temp.name)/'other.json';p.replace(outside);p.symlink_to(outside)
        self.assertIsNone(self.hud._read_worker())
    def test_object_arrow_waits_for_completed_native_receipt(self):
        self.hud.command_started(dict(action='mesh.create',args={}))
        self.assertIsNone(self.hud.model()['object'])
        self.hud.command_finished(dict(state='succeeded',result=dict(name='ArtistCube')))
        self.assertEqual('ArtistCube',self.hud.model()['object'])
        self.hud.command_started(dict(action='mesh.create',args={}))
        self.hud.command_finished(dict(state='recovery_required'))
        self.assertIsNone(self.hud.model()['object'])
    def test_failed_paused_or_path_result_has_no_object_arrow(self):
        for state,result in [('failed',dict(name='Cube')),('succeeded',dict(name='../Cube')),
                             ('succeeded',dict(name='Cube',paused=True))]:
            self.hud.command_started(dict(action='mesh.create',args={}))
            self.hud.command_finished(dict(state=state,result=result))
            self.assertIsNone(self.hud.model()['object'])
    def test_arrow_projects_actual_native_object_and_hides_offscreen(self):
        position=object();self.bpy.context.scene.objects['Cube']=types.SimpleNamespace(
            visible_get=lambda:True,matrix_world=types.SimpleNamespace(translation=position))
        seen=[]
        module=types.SimpleNamespace(location_3d_to_region_2d=lambda region,data,location:(seen.append(location) or (120,90)))
        with patch.dict(sys.modules,{'bpy_extras':types.SimpleNamespace(),'bpy_extras.view3d_utils':module}):
            self.assertEqual((120,90),self.hud._project_object('Cube'));self.assertEqual([position],seen)
            module.location_3d_to_region_2d=lambda *args:(900,90)
            self.assertIsNone(self.hud._project_object('Cube'))
            self.assertIsNone(self.hud._project_object('MissingObject'))
    def test_blender_statusbar_uses_native_layout_progress(self):
        self.hud._progress=dict(completed=3,total=5);calls=[]
        layout=types.SimpleNamespace(progress=lambda **p:calls.append(p),label=lambda **p:None)
        self.assertTrue(self.hud.draw_statusbar(layout));self.assertEqual(.6,calls[0]['factor'])


if __name__=='__main__':unittest.main()
