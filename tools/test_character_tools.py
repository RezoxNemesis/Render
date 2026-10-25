"""Host admission checks; no Blender geometry or render is generated here."""
import importlib.util
import pathlib
import unittest

P=pathlib.Path(__file__).resolve().parents[1]/'full-app/scripts/render_character_tools.py'
spec=importlib.util.spec_from_file_location('character_tools',P)
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)


class CharacterAdmissionTests(unittest.TestCase):
    def test_front_review_uses_explicit_portrait_aspect_without_quality_changes(self):
        result=T.review_options({'view':'FRONT','aspect':.75,'margin':1.15})
        self.assertEqual(('FRONT',.75,1.15),result)
        for invalid in ({'view':'FRONT','aspect':float('nan')},{'view':'UNKNOWN'},
                        {'view':'FRONT','margin':True},{'view':'FRONT','aspect':0}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):T.review_options(invalid)

    def test_voxel_budget_refuses_finer_surface_instead_of_changing_resolution(self):
        bounds=[.5,.4,1.65]
        p=T.sculpt_plan(bounds,1.0,.005,8_000_000,2_000_000_000)
        self.assertEqual(.005,p['voxel_size_scene_units'])
        self.assertLess(p['estimated_voxel_cells'],8_000_000)
        with self.assertRaisesRegex(ValueError,'VOXEL_BUDGET'):
            T.sculpt_plan(bounds,1.0,.0005,8_000_000,2_000_000_000)

    def test_centimetre_scene_preserves_requested_physical_voxel_size(self):
        p=T.sculpt_plan([50,40,165],.01,.005,8_000_000,2_000_000_000)
        self.assertEqual(.5,p['voxel_size_scene_units'])

    def test_memory_gate_uses_available_bytes_and_retains_the_requested_resolution(self):
        with self.assertRaisesRegex(ValueError,'MEMORY_PRESSURE'):
            T.sculpt_plan([.5,.4,1.65],1,.005,8_000_000,128*1024*1024)
        for bad in (True,0,-1,float('nan')):
            with self.subTest(value=bad),self.assertRaises(ValueError):
                T.sculpt_plan([.5,.4,1.65],1,bad,8_000_000,2_000_000_000)

    def test_topology_components_are_measured_instead_of_assuming_union(self):
        self.assertEqual(1,T.mesh_components(4,[(0,1),(1,2),(2,3)]))
        self.assertEqual(2,T.mesh_components(4,[(0,1),(2,3)]))
        self.assertEqual(3,T.mesh_components(3,[]))


if __name__=='__main__':unittest.main()
