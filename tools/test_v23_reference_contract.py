# Regression tests for the exact reference/viewport/connection contracts.
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/'full-app/scripts/render_studio_contract.py'
SPEC=importlib.util.spec_from_file_location('studio_reference_contract',FILE)
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)

class V23ReferenceTests(unittest.TestCase):
    def test_photo_landmarks_are_metric_not_identity(self):
        first={'left_eye':[.37,.45],'right_eye':[.63,.45],'nose':[.50,.60],'mouth':[.50,.71]}
        same=C.landmark_error(first,first)
        self.assertEqual(same['rms_normalized_image_error'],0)
        self.assertFalse(same['identity_verified'])
        self.assertNotIn('likeness_percent',same)
        moved={k:[v[0]+.02,v[1]] for k,v in first.items()}
        self.assertAlmostEqual(C.landmark_error(first,moved)['rms_normalized_image_error'],.02)
    def test_crop_validation_no_unbounded_pixels(self):
        self.assertEqual(C.crop_rect([0,0,1,1]),[0,0,1,1])
        for bad in ([0,0,0,1],[-1,0,1,1],[.9,.2,.1,.5],[0,.2,1,float('nan')],[0,0,1]):
            with self.assertRaises(ValueError):C.crop_rect(bad)
    def test_reference_hash_no_arbitrary_paths(self):
        self.assertEqual(C.asset_name('c'*64,'jpg'),'c'*64+'.jpg')
        for ext in ('../png','exe','blend','html'):
            with self.assertRaises(ValueError):C.asset_name('c'*64,ext)
        with self.assertRaises(ValueError):C.asset_name('x/../../../escape','mp4')
    def test_bounded_depth_precision_does_not_change_render(self):
        for r,d in [(.001,.003),(.3,.7),(2,3),(5,15),(10000,20000)]:
            out=C.clip_plan(r,d)
            self.assertLess(out['precision_ratio'],100000)
            self.assertGreaterEqual(out['clip_end'],d+r)
            self.assertFalse(out['render_settings_changed'])
            self.assertFalse(out['geometry_decimated'])
    def test_long_film_is_planned_not_claimed_rendered(self):
        result=C.long_render_plan(300,24,1920,1080)
        self.assertEqual(result['frames'],7200)
        self.assertFalse(result['phone_hardware_verified'])
        self.assertIsNone(result['estimated_wall_seconds'])
        self.assertFalse(result['quality_reduced'])
        self.assertFalse(C.render_complete(100,149,149))
        self.assertTrue(C.render_complete(100,149,150))
        self.assertEqual(C.first_missing_frame(100,103,{100,102,103}),101)
    def test_schema_does_not_allow_arbitrary_code(self):
        required=['reference.bind','reference.landmarks','viewport.inspect','viewport.configure',
                  'viewport.focus','object.geometry','operator.describe','operator.execute','ui.state']
        self.assertTrue(set(required).issubset(C.SCHEMAS))
        for name in ['python.eval','shell','gallery.list','any_blender_operator']:
            self.assertNotIn(name,C.SCHEMAS)
    def test_native_adapter_wires_bounded_gallery_free_operation(self):
        s=(ROOT/'tools/prepare_v23_reference.py').read_text()
        for symbol in ['StudioReferenceInbox','StudioLiveHandOverlay','reference.bind','reference.video_frame',
                       'render_studio_ops.py','expected_next_frame','end_frame','versionCode = 25']:
            self.assertIn(symbol,s)
        self.assertNotIn('android.permission.READ_MEDIA_IMAGES',s)
        self.assertNotIn('subprocess.Popen',s)

if __name__=='__main__':unittest.main()
