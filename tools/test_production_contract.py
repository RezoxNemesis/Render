import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'full-app/scripts/render_production_contract.py'
spec=importlib.util.spec_from_file_location('production_contract',MODULE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ProductionContractTests(unittest.TestCase):
    def test_safe_names_and_symlinks(self):
        for name in ('../a','/a','a/b','x\\y',''):
            with self.assertRaises(ValueError):m.safe_name(name)
        self.assertEqual(m.safe_name('human-head_2'),'human-head_2')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'artifacts';root.mkdir();outside=Path(d)/'outside';outside.write_text('private');(root/'link.png').symlink_to(outside)
            with self.assertRaises(ValueError):m.owned_path(root,'link.png')
    def test_exact_ten_million_instances_are_not_ten_million_objects(self):
        p=m.instance_plan({'counts':[1000,1000,10],'spacing':[1,1,1]},8*1024**3)
        self.assertEqual(p['instance_count'],10_000_000);self.assertEqual(p['node_levels'],3)
        self.assertFalse(p['realize_instances']);self.assertFalse(p['hardware_verified']);self.assertTrue(p['admitted']);self.assertFalse(p['quality_reduced'])
    def test_memory_pressure_and_bad_counts(self):
        self.assertFalse(m.instance_plan({'counts':[1000,1000,10],'spacing':[1,1,1]},64*1024**2)['admitted'])
        for c in ([True,1,1],[0,1,1],[10000,10000,10],[2.1,2,2],[1,1]):
            with self.assertRaises(ValueError):m.instance_plan({'counts':c,'spacing':[1,1,1]},8*1024**3)
    def test_no_silent_quality_change(self):
        p=m.render_spec({'width':1920,'height':1080,'fps':24,'start':1,'end':240,'samples':64,'engine':'CYCLES'})
        self.assertEqual((p['width'],p['height'],p['fps'],p['samples']),(1920,1080,24,64));self.assertEqual(p['frame_count'],240)
        for data in ({'width':1919},{'fps':False},{'end':0},{'samples':float('nan')},{'script':'evil'}):
            with self.assertRaises(ValueError):m.render_spec(data)
    def test_fingerprint_is_canonical_and_revision_bound(self):
        self.assertEqual(m.fingerprint({'b':2,'a':1}),m.fingerprint({'a':1,'b':2}))
        self.assertNotEqual(m.fingerprint({'a':1}),m.fingerprint({'a':2}))
        with self.assertRaises(ValueError):m.fingerprint({'a':float('nan')})
    def test_no_arbitrary_code_gallery_or_paths(self):
        for op in ('python.eval','shell.exec','gallery.list','bpy.ops.wm.open_mainfile'):
            with self.assertRaises(ValueError):m.validate_envelope({'operation':op,'payload':{}})
        with self.assertRaises(ValueError):m.validate_envelope({'operation':'project.create','payload':{},'code':'x'})
        self.assertEqual(m.validate_envelope({'operation':'project.create','payload':{'name':'NewScene'}})[0],'project.create')
    def test_resume_only_unchanged_frames(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);f=root/'frame_000001.png';f.write_bytes(b'PNG_test_payload');receipt=m.file_receipt(f)
            self.assertTrue(m.frame_matches(root,receipt));f.write_bytes(b'changed');self.assertFalse(m.frame_matches(root,receipt))
            self.assertFalse(m.frame_matches(root,dict(receipt,filename='../outside')))
    def test_topology_validation(self):
        p={'name':'Face','vertices':[[0,0,0],[1,0,0],[0,1,0]],'faces':[[0,1,2]]}
        self.assertEqual(m.mesh_spec(p)['faces'],[[0,1,2]])
        with self.assertRaises(ValueError):m.mesh_spec(dict(p,faces=[[0,1,3]]))
        with self.assertRaises(ValueError):m.mesh_spec(dict(p,vertices=[[0,0,float('inf')]]))
    def test_detail_controls_are_bounded(self):
        self.assertEqual(m.mesh_spec({'name':'Head','kind':'UV_SPHERE','segments':96,'rings':64})['segments'],96)
        for data in ({'name':'Head','kind':'PYTHON'},{'name':'Head','segments':10000},{'name':'Head','scale':[0,1,1]}):
            with self.assertRaises(ValueError):m.mesh_spec(data)
    def test_operation_payload_size_is_bounded(self):
        with self.assertRaises(ValueError):m.validate_envelope({'operation':'mesh.create','payload':{'padding':'x'*140000}})

if __name__=='__main__':unittest.main()
