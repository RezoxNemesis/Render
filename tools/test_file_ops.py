"""Host adapter checks with attribute fixtures; no Blender/model/import/render execution."""
import importlib.util
from pathlib import Path
import json
import struct
import sys
import tempfile
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('file_ops_fixture',Path(__file__).resolve().parents[1]/'full-app/scripts/render_file_ops.py')
O=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{'bpy':N()}):spec.loader.exec_module(O)

class FileOpsTests(unittest.TestCase):
    def test_missing_native_operator_key_error_is_reported_unavailable(self):
        # Observed Android RNA response for the unbundled Collada importer.
        with patch.object(O,'_operator',side_effect=KeyError('WM_OT_collada_import')):
            self.assertFalse(O._available('wm.collada_import'))
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
    def glb(self,data):
        content=json.dumps(data).encode('utf8')
        content+=b' '*((-len(content))%4)
        return struct.pack('<4sII',b'glTF',2,20+len(content))+struct.pack('<I4s',len(content),b'JSON')+content
    def test_glb_external_dependencies_use_same_scope_checks_as_gltf(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory=root/'bundle';directory.mkdir()
            (directory/'models').mkdir();(directory/'textures').mkdir()
            (directory/'textures/data.bin').write_bytes(b'fixture')
            outside=root/'private.bin';outside.write_bytes(b'private fixture')
            (directory/'textures/link.bin').symlink_to(outside)
            model=directory/'models/scene.glb'
            for field in ('buffers','images'):
                model.write_bytes(self.glb({field:[{'uri':'../textures/data.bin'}]}))
                O._gltf_dependencies(model,directory)
                for uri in ('../../private.bin',str(outside),'%2e%2e/%2e%2e/private.bin',
                            '../textures/link.bin','https://example.com/remote.bin'):
                    with self.subTest(field=field,uri=uri):
                        model.write_bytes(self.glb({field:[{'uri':uri}]}))
                        with self.assertRaises(ValueError):O._gltf_dependencies(model,directory)
            self.assertEqual(b'private fixture',outside.read_bytes())
    def test_gltf_sniffs_format_like_native_importer_instead_of_trusting_suffix(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            malicious={'buffers':[{'uri':'../private.bin'}]}
            for suffix,data in (('.glb',json.dumps(malicious).encode()),('.gltf',self.glb(malicious))):
                model=root/('scene'+suffix);model.write_bytes(data)
                with self.assertRaises(ValueError):O._gltf_dependencies(model,root)
    def test_glb_embedded_buffers_and_images_need_no_external_files(self):
        with tempfile.TemporaryDirectory() as temp:
            model=Path(temp)/'embedded.glb'
            model.write_bytes(self.glb({'buffers':[{'byteLength':0}],
                'images':[{'uri':'data:image/png;base64,AA=='}]}))
            O._gltf_dependencies(model,Path(temp))
    def test_glb_bad_lengths_and_unbounded_json_fail_before_native_import(self):
        with tempfile.TemporaryDirectory() as temp:
            model=Path(temp)/'malformed.glb';valid=self.glb({'buffers':[]})
            for data in (b'glTF',valid[:-1],valid[:4]+struct.pack('<I',1)+valid[8:],
                         valid[:12]+struct.pack('<I4s',64*1024*1024+4,b'JSON')+valid[20:],
                         valid[:16]+b'BIN\0'+valid[20:]):
                with self.subTest(header=data[:20]):
                    model.write_bytes(data)
                    with self.assertRaises(ValueError):O._gltf_dependencies(model,Path(temp))
    def test_blend_selection_rejects_duplicates_non_names_and_unbounded_sets(self):
        for values in (['a','a'],[{}],[''],['a']*129):
            with self.assertRaises(ValueError):O._names({'objects':values},'objects')

if __name__=='__main__':unittest.main()
