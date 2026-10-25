# SPDX-License-Identifier: GPL-2.0-or-later
"""Executable, real filesystem regressions for native Render continuity.

Mocks Blender only at the UI boundary: no claim of Android GPU testing.
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

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "full-app/scripts/render_session_tools.py"

class FakeBlender:
    def __init__(self):
        self.saved_paths=[]
        self.loaded_paths=[]
        self.data=types.SimpleNamespace(filepath="/safe/original.blend",is_dirty=True)
        self.app=types.SimpleNamespace(background=False,is_job_running=lambda job: False)
        self.scene=types.SimpleNamespace(name="CarScene",frame_start=101,frame_end=105,
            cycles=types.SimpleNamespace(samples=48),
            render=types.SimpleNamespace(resolution_x=800,resolution_y=450,
                resolution_percentage=100, fps=24, engine="CYCLES"),
            objects=[])
        self.context=types.SimpleNamespace(scene=self.scene,window=None)
        def save_as_mainfile(filepath,**kwargs):
            assert kwargs["copy"] is True
            assert kwargs["compress"] is True
            p=Path(filepath)
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(b"BLENDER" + b"x"*500)
            self.saved_paths.append(filepath)
            return {"FINISHED"}
        def open_mainfile(filepath,**kwargs):
            assert Path(filepath).is_file()
            self.loaded_paths.append(filepath)
            self.data.filepath=filepath
            return {"FINISHED"}
        self.ops=types.SimpleNamespace(wm=types.SimpleNamespace(
            save_as_mainfile=save_as_mainfile,open_mainfile=open_mainfile))
        self.types=types.SimpleNamespace(Operator=object)

class RenderSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old_env=os.environ.get("RENDER_AGENT_SPOOL")
        os.environ["RENDER_AGENT_SPOOL"]=str(Path(self.tmp.name)/"render_bpy_jobs")
        self.addCleanup(self.restore_env)
        self.fake=FakeBlender()
        self.old_bpy=sys.modules.get("bpy")
        sys.modules["bpy"]=self.fake
        self.addCleanup(self.restore_bpy)
        spec=importlib.util.spec_from_file_location("session_tools_test",SCRIPT)
        self.module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
    def restore_env(self):
        if self.old_env is None:os.environ.pop("RENDER_AGENT_SPOOL",None)
        else:os.environ["RENDER_AGENT_SPOOL"]=self.old_env
    def restore_bpy(self):
        if self.old_bpy is None:sys.modules.pop("bpy",None)
        else:sys.modules["bpy"]=self.old_bpy

    def test_copy_preserves_original_and_restores_verified_blend(self):
        saved=self.module.save_session()
        self.assertTrue(saved["saved"])
        self.assertTrue(saved["source_project_unchanged"])
        self.assertEqual("/safe/original.blend",self.fake.data.filepath)
        folder=Path(self.tmp.name)/"Production/Projects"
        self.assertTrue((folder/"CurrentSession.blend").read_bytes().startswith(b"BLENDER"))
        self.assertEqual(saved["sha256"],json.loads((folder/"CurrentSession.json").read_text())["sha256"])
        self.fake.data.filepath=""
        self.fake.data.is_dirty=False
        self.assertTrue(self.module.restore_session()["restored"])
        self.assertEqual(1,len(self.fake.loaded_paths))

    def test_interrupted_native_copy_does_not_replace_a_valid_checkpoint(self):
        path=Path(self.tmp.name)/'Production/Projects/ArtistCheckpoint.blend'
        path.parent.mkdir(parents=True);original=b'BLENDER'+b'original'*100
        path.write_bytes(original)
        def interrupted(filepath,**kwargs):
            Path(filepath).write_bytes(b'BLENDER'+b'partial'*100)
            return {'CANCELLED'}
        self.fake.ops.wm.save_as_mainfile=interrupted
        with self.assertRaisesRegex(RuntimeError,'CHECKPOINT_INCOMPLETE'):
            self.module.save_copy_atomic(path)
        self.assertEqual(original,path.read_bytes())
        self.assertEqual([],list(path.parent.glob('.render-copy-*.blend')))

    def test_failed_storage_sync_does_not_publish_a_checkpoint(self):
        path=Path(self.tmp.name)/'Production/Projects/ArtistCheckpoint.blend'
        with patch.object(self.module.os,'fsync',side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):self.module.save_copy_atomic(path)
        self.assertFalse(path.exists())
        self.assertEqual('/safe/original.blend',self.fake.data.filepath)

    def test_atomic_checkpoint_receipt_matches_only_the_published_copy(self):
        path=Path(self.tmp.name)/'Production/Projects/ArtistCheckpoint.blend'
        receipt=self.module.save_copy_atomic(path)
        self.assertEqual(self.module._sha(path),receipt['sha256'])
        self.assertEqual(path.stat().st_size,receipt['bytes'])
        self.assertTrue(receipt['atomically_published'])
        self.assertTrue(receipt['file_fsync_completed'])
        self.assertTrue(receipt['directory_fsync_completed'])
        self.assertEqual([path],list(path.parent.glob('*.blend')))

    def test_checkpoint_rename_preserves_remapped_relative_dependencies(self):
        path=Path(self.tmp.name)/'Production/Projects/ArtistCheckpoint.blend'
        asset=Path(self.tmp.name)/'ArtistTextures/texture.bin'
        asset.parent.mkdir();asset.write_bytes(b'original texture')
        def save_with_relative_asset(filepath,**kwargs):
            saved=Path(filepath)
            relative=os.path.relpath(asset,saved.parent)
            saved.write_bytes(b'BLENDER'+relative.encode()+b'\n'+b'x'*500)
            return {'FINISHED'}
        self.fake.ops.wm.save_as_mainfile=save_with_relative_asset
        self.module.save_copy_atomic(path)
        relative=path.read_bytes()[7:].split(b'\n')[0].decode()
        self.assertEqual(asset,(path.parent/relative).resolve())

    def test_corrupt_latest_restores_last_valid_backup(self):
        self.module.save_session()
        self.module.save_session()
        folder=Path(self.tmp.name)/"Production/Projects"
        self.assertTrue((folder/"CurrentSession.previous.blend").is_file())
        (folder/"CurrentSession.blend").write_bytes(b"broken")
        self.assertEqual("CurrentSession.previous.blend",self.module._recoverable_session().name)

    def test_dirty_active_project_is_not_replaced_silently(self):
        self.module.save_session()
        self.assertEqual("CURRENT_PROJECT_ALREADY_OPEN",self.module.restore_session()["reason"])
        self.assertEqual([],self.fake.loaded_paths)

    def test_native_render_keeps_absolute_101_to_105_frames_and_pixel_size(self):
        self.assertEqual(dict(width=800,height=450,start=101,end=105,
            fps=24,samples=48,engine="CYCLES",bitrate=16000000,output_kind="ANIMATION"),
            self.module._render_spec(self.fake.scene))
        def execute(args,spool,command_id):
            self.assertEqual("render.plan",args["operation"])
            self.assertEqual(101,args["payload"]["start"])
            self.assertEqual(105,args["payload"]["end"])
            return {"job_id":"e"*32}
        old=sys.modules.get("render_production")
        sys.modules["render_production"]=types.SimpleNamespace(execute=execute)
        self.addCleanup(lambda: sys.modules.pop("render_production",None)
                        if old is None else sys.modules.__setitem__("render_production",old))
        receipt=self.module.queue_manual_render()
        self.assertTrue(receipt["queued"])
        request=json.loads((Path(self.tmp.name)/"Production/manual_render_request.json").read_text())
        self.assertEqual("e"*32,request["job_id"])
        with self.assertRaisesRegex(RuntimeError,"RENDER_REQUEST_ALREADY_PENDING"):
            self.module.queue_manual_render()

    def test_viewport_stabilize_does_not_modify_geometry_or_render(self):
        size=(self.fake.scene.render.resolution_x,self.fake.scene.render.resolution_y)
        audit=self.module.stabilize_viewport()
        self.assertFalse(audit["mesh_geometry_modified"])
        self.assertFalse(audit["final_render_samples_modified"])
        self.assertEqual(size,(self.fake.scene.render.resolution_x,self.fake.scene.render.resolution_y))

if __name__=="__main__":
    unittest.main()
