"""Pure settings boundary tests with scene doubles, never Blender rendering."""
import importlib.util
from pathlib import Path
import types
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'full-app/scripts/render_execution_settings.py'
spec=importlib.util.spec_from_file_location('execution_settings_under_test',SCRIPT)
E=importlib.util.module_from_spec(spec);spec.loader.exec_module(E)

class Scene(dict):
    def __init__(self):
        super().__init__();self.frame_start=101;self.frame_end=105
        self.render=types.SimpleNamespace(engine='CYCLES',resolution_x=3840,resolution_y=2160,
            resolution_percentage=100,fps=24,fps_base=1.001,film_transparent=False,
            use_persistent_data=False,threads_mode='AUTO',threads=8)
        self.cycles=types.SimpleNamespace(samples=512,use_denoising=True)
        self.eevee=types.SimpleNamespace(taa_render_samples=128)

class ExecutionSettingsTests(unittest.TestCase):
    def test_preview_profile_cannot_change_final_or_active_scene_settings(self):
        scene=Scene();before=E.inspect(scene)
        E.profiles(scene,{'profile':'preview','settings':{'percentage':50,'samples':32,'fps_base':1.25}},True)
        preview,name,overrides=E.profile_plan(scene,{'profile':'preview'})
        final,final_name,final_overrides=E.profile_plan(scene,{})
        self.assertEqual((1920,1080,32),(preview['width'],preview['height'],preview['samples']))
        self.assertEqual(1.25,overrides['fps_base'])
        self.assertEqual((3840,2160,512),(final['width'],final['height'],final['samples']))
        self.assertEqual('final',final_name);self.assertEqual({},final_overrides)
        self.assertEqual(before,E.inspect(scene))

    def test_profile_updates_preserve_unspecified_artist_overrides(self):
        scene=Scene()
        E.profiles(scene,{'profile':'final','settings':{'samples':1024,'fps_base':1.001}},True)
        E.profiles(scene,{'profile':'final','settings':{'width':4096}},True)
        profile=E.profiles(scene,{})['profiles']['final']
        self.assertEqual({'samples':1024,'fps_base':1.001,'width':4096},profile)
        self.assertEqual(512,scene.cycles.samples)

    def test_performance_controls_preserve_every_quality_field(self):
        scene=Scene();before=E.inspect(scene)
        result=E.configure(scene,{'persistent_data':True,'threads_mode':'FIXED','threads':4},True)
        for field in ('engine','width','height','percentage','fps','fps_base','samples','denoising','film_transparent'):
            self.assertEqual(before[field],result['after'][field])
        self.assertFalse(result['quality_settings_changed']);self.assertTrue(scene.render.use_persistent_data)

    def test_minimal_render_plan_preserves_artist_settings_and_frame_range(self):
        scene=Scene();result=E.plan_payload(scene,{})
        self.assertEqual({'width':3840,'height':2160,'engine':'CYCLES','samples':512,
                          'fps':24,'start':101,'end':105},result)
        self.assertEqual(256,E.plan_payload(scene,{'samples':256})['samples'])

    def test_invalid_or_cross_category_settings_change_nothing(self):
        for p,performance in (({'threads':True},True),({'width':1920},True),
                              ({'samples':0},False),({'fps_base':float('nan')},False)):
            scene=Scene();before=E.inspect(scene)
            with self.assertRaises(ValueError):E.configure(scene,p,performance)
            self.assertEqual(before,E.inspect(scene))

    def test_failed_engine_specific_setting_rolls_back_prior_valid_changes(self):
        scene=Scene();before=E.inspect(scene)
        with self.assertRaisesRegex(ValueError,'DENOISING_SETTING_REQUIRES_CYCLES'):
            E.configure(scene,{'engine':'BLENDER_EEVEE_NEXT','width':1920,'denoising':True})
        self.assertEqual(before,E.inspect(scene))

    def test_frozen_snapshot_is_immutable(self):
        scene=Scene();scene['production_frozen_job']='a'*32
        with self.assertRaisesRegex(ValueError,'RENDER_SNAPSHOT_IMMUTABLE'):
            E.configure(scene,{'persistent_data':True},True)

    def test_rna_clamping_is_rejected_and_rolled_back(self):
        class Clamp:
            def __init__(self):self._value=512
            @property
            def samples(self):return self._value
            @samples.setter
            def samples(self,v):self._value=min(v,512)
            use_denoising=True
        scene=Scene();scene.cycles=Clamp()
        with self.assertRaisesRegex(ValueError,'NATIVE_RENDER_SETTING_WAS_CLAMPED'):
            E.configure(scene,{'width':1920,'samples':1024})
        self.assertEqual(3840,scene.render.resolution_x);self.assertEqual(512,scene.cycles.samples)

if __name__=='__main__':unittest.main()
