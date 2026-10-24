"""Host adapter checks with attribute fixtures; no Blender/model/import/render execution."""
import importlib.util
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('file_ops_fixture',Path(__file__).resolve().parents[1]/'full-app/scripts/render_file_ops.py')
O=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{'bpy':N()}):spec.loader.exec_module(O)

class FileOpsTests(unittest.TestCase):
    def test_importer_changes_and_failures_preserve_artist_settings(self):
        world=object();camera=object()
        scene=N(render=N(engine='CYCLES',resolution_x=2048,resolution_y=2048,fps=24,image_settings=N(file_format='PNG')),
                unit_settings=N(system='METRIC',scale_length=1),view_settings=N(exposure=1.25),
                frame_start=1,frame_end=48,camera=camera,world=world,frame_current=12,frame_subframe=0)
        scene.frame_set=lambda value,subframe=0:(setattr(scene,'frame_current',value),setattr(scene,'frame_subframe',subframe))
        with self.assertRaisesRegex(RuntimeError,'import failed'):
            with O._preserve_settings(scene,'MODEL'):
                scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.fps=30;scene.render.resolution_x=256
                scene.frame_end=200;scene.camera=None;scene.world=None;scene.view_settings.exposure=0
                scene.frame_set(1);raise RuntimeError('import failed')
        self.assertEqual(('CYCLES',24,2048), (scene.render.engine,scene.render.fps,scene.render.resolution_x))
        self.assertEqual((48,12,1.25),(scene.frame_end,scene.frame_current,scene.view_settings.exposure))
        self.assertIs(camera,scene.camera);self.assertIs(world,scene.world)
    def test_gltf_sibling_dependencies_are_allowed_but_missing_and_outside_paths_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'models').mkdir();(root/'textures').mkdir();(root/'textures/data.bin').write_bytes(b'fixture')
            model=root/'models/scene.gltf';model.write_text(json.dumps({'buffers':[{'uri':'../textures/data.bin'}]}))
            O._gltf_dependencies(model,root)
            for uri in ('../../outside','/private','https://example.com/a','../textures/missing.bin'):
                model.write_text(json.dumps({'buffers':[{'uri':uri}]}))
                with self.assertRaises(ValueError):O._gltf_dependencies(model,root)
    def test_blend_selection_rejects_duplicates_non_names_and_unbounded_sets(self):
        for values in (['a','a'],[{}],[''],['a']*129):
            with self.assertRaises(ValueError):O._names({'objects':values},'objects')

if __name__=='__main__':unittest.main()
