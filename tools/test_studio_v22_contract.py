import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'full-app/scripts/render_studio_contract.py'

class StudioContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module=None
        if FILE.is_file():
            spec=importlib.util.spec_from_file_location('studio_contract_test',FILE)
            cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)
    def api(self):
        self.assertIsNotNone(self.module,'Reference/viewport contract is not implemented yet')
        return self.module
    def test_reference_landmark_error_is_not_fake_similarity(self):
        c=self.api();a={'left_eye':[.3,.4],'right_eye':[.7,.4],'mouth':[.5,.65]}
        exact=c.landmark_error(a,a)
        self.assertEqual(exact['rms_normalized_image_error'],0)
        self.assertNotIn('likeness_percent',exact)
        shifted=c.landmark_error(a,{k:[x+.1,y] for k,(x,y) in a.items()})
        self.assertAlmostEqual(shifted['rms_normalized_image_error'],.1)
        self.assertFalse(shifted['visual_likeness_verified'])
    def test_bad_landmarks_and_missing_pairs_rejected(self):
        c=self.api()
        for a,b in [({},{}),({'a':[0,0]},{'b':[0,0]}),({'a':[float('nan'),0]},{'a':[0,0]})]:
            with self.assertRaises(ValueError):c.landmark_error(a,b)
    def test_scene_scale_clip_range_keeps_precision_without_render_changes(self):
        c=self.api();p=c.clip_plan(2.0,3.0)
        self.assertGreater(p['clip_start'],0)
        self.assertGreater(p['clip_end'],p['clip_start'])
        self.assertLessEqual(p['clip_end']/p['clip_start'],100000)
        self.assertFalse(p['render_settings_changed'])
        self.assertFalse(p['geometry_decimated'])
    def test_clip_plan_handles_tiny_and_large_assets(self):
        c=self.api()
        for radius,distance in [(0.002,.005),(2,3),(10000,20000)]:
            p=c.clip_plan(radius,distance)
            self.assertGreaterEqual(p['clip_end'],distance+radius)
        for radius in (0,-1,float('inf')):
            with self.assertRaises(ValueError):c.clip_plan(radius,2)
    def test_non_one_start_range_is_not_treated_as_already_complete(self):
        c=self.api();self.assertFalse(c.render_complete(100,149,100))
        self.assertFalse(c.render_complete(100,149,149))
        self.assertTrue(c.render_complete(100,149,150))
        self.assertEqual(c.long_render_plan(300,24)['frames'],7200)
        self.assertEqual(c.long_render_plan(300,30)['frames'],9000)
    def test_schema_distinguishes_native_operations_from_ui_events(self):
        c=self.api();self.assertIn('ui.state',c.SCHEMAS)
        self.assertIn('reference.bind',c.SCHEMAS)
        self.assertIn('viewport.configure',c.SCHEMAS)
        self.assertIn('operator.describe',c.SCHEMAS)
        self.assertIn('operator.execute',c.SCHEMAS)
        for op in ('python.eval','shell.exec','gallery.list'):
            self.assertNotIn(op,c.SCHEMAS)
    def test_import_names_are_content_hashes_not_paths(self):
        c=self.api();self.assertEqual(c.asset_name('a'*64,'png'),'a'*64+'.png')
        for ext in ('../png','blend','py',''):
            with self.assertRaises(ValueError):c.asset_name('a'*64,ext)
        with self.assertRaises(ValueError):c.asset_name('../a','png')
    def test_recovery_identifies_first_missing_frame(self):
        c=self.api()
        self.assertEqual(c.first_missing_frame(100,104,{100,101,103}),102)
        self.assertEqual(c.first_missing_frame(100,104,set(range(100,105))),105)
    def test_evidence_cannot_claim_exact_unseen_views(self):
        c=self.api();p=c.reference_provenance('a'*64,'front',False)
        self.assertEqual(p['unseen_geometry'],'inferred')
        self.assertFalse(p['automatic_reconstruction'])
        self.assertFalse(p['exact_likeness_verified'])

if __name__=='__main__':unittest.main()
