import importlib.util
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'full-app/scripts/render_precision_contract.py'

class PrecisionContractTests(unittest.TestCase):
    def contract(self):
        self.assertTrue(PATH.is_file(),'Reference precision contract is not implemented')
        spec=importlib.util.spec_from_file_location('precision_under_test',PATH)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_nonzero_frame_range_is_not_confused_with_frame_count(self):
        c=self.contract()
        self.assertFalse(c.render_complete({'start':101,'end':150,'frame_count':50},101))
        self.assertFalse(c.render_complete({'start':101,'end':150,'frame_count':50},150))
        self.assertTrue(c.render_complete({'start':101,'end':150,'frame_count':50},151))
        self.assertFalse(c.render_complete({'start':1,'end':7200,'frame_count':7200},7199))
    def test_stale_exact_frame_never_advances(self):
        c=self.contract();self.assertEqual(c.expected_frame({'expected_frame':40},40),40)
        with self.assertRaisesRegex(ValueError,'FRAME_REVISION_CONFLICT'):c.expected_frame({'expected_frame':39},40)
        for n in (True,40.2,'40'):
            with self.assertRaises(ValueError):c.expected_frame({'expected_frame':n},40)
    def test_top_left_crop_maps_to_bottom_left_uv_without_stretching(self):
        c=self.contract();r=c.reference_geometry(1000,2000,[0.1,0.2,0.9,0.8],2.0)
        self.assertAlmostEqual(r['height'],3.0)
        self.assertEqual(r['crop_pixels'],[100,400,900,1600])
        self.assertEqual(r['uv'],[[0.1,0.2],[0.9,0.2],[0.9,0.8],[0.1,0.8]])
    def test_invalid_crops_and_nonfinite_inputs_are_refused(self):
        c=self.contract()
        for crop in ([0,0,0,1],[-1,0,1,1],[0,0,1,2],[0,float('nan'),1,1],[True,0,1,1]):
            with self.assertRaises(ValueError):c.reference_geometry(1000,1000,crop,1.0)
        with self.assertRaises(ValueError):c.reference_geometry(0,1000,[0,0,1,1],1.0)
    def test_landmark_metrics_are_not_identity_percentages(self):
        c=self.contract();r=c.landmark_metrics([[0,0],[1,1]],[[0,0],[1,1]])
        self.assertEqual(r['normalized_rmse'],0)
        self.assertFalse(r['proves_identity_likeness']);self.assertNotIn('likeness_percent',r)
        with self.assertRaises(ValueError):c.landmark_metrics([[0,0]],[[float('inf'),0]])
    def test_projection_and_clipping_bounds_are_validated(self):
        c=self.contract();self.assertEqual(c.clipping(0.01,100.0),[0.01,100.0])
        for near,far in ((0,10),(10,1),(True,10),(0.01,float('inf'))):
            with self.assertRaises(ValueError):c.clipping(near,far)
    def test_media_names_are_owned_content_ids(self):
        c=self.contract();name='a'*64+'.png';self.assertEqual(c.asset_name(name),name)
        for name in ('../a.png','photo.png','https://example.com/image.jpg','a'*64+'.py'):
            with self.assertRaises(ValueError):c.asset_name(name)

if __name__=='__main__':unittest.main()
