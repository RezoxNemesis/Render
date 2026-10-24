# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure host verification: python -m unittest discover -s tools/omega -p 'test_phase08_*.py'."""
import importlib.util
from pathlib import Path
import unittest

MOD = Path(__file__).resolve().parents[2] / 'full-app/scripts/omega/phase08_world.py'
spec = importlib.util.spec_from_file_location('phase08_world', MOD)
world = importlib.util.module_from_spec(spec)
spec.loader.exec_module(world)
BUILD, AUDIT = world.OPERATION_NAMES


class Phase08ContractTest(unittest.TestCase):
    def test_frozen_operation_names_and_no_import_side_effect(self):
        self.assertEqual(world.CONTRACT_VERSION, 'RENDER-OMEGA-1')
        self.assertEqual(world.OPERATION_NAMES, ('omega.world.build_scene', 'omega.world.audit'))
        self.assertEqual(world.validate(BUILD, {}), {
            'name':'RailwayTemple','seed':8,'trees':18,'grass':48,'layout':'RAILWAY_TEMPLE'})

    def test_identical_seed_produces_identical_scatter_and_fingerprint(self):
        a=world.plan({'seed':78,'trees':12,'grass':20})
        b=world.plan({'seed':78,'trees':12,'grass':20})
        c=world.plan({'seed':79,'trees':12,'grass':20})
        self.assertEqual(a,b)
        self.assertNotEqual(a['scatter'],c['scatter'])
        self.assertNotEqual(a['fingerprint'],c['fingerprint'])
        self.assertEqual(len(a['scatter'][0][1]),12)
        self.assertEqual(len(a['scatter'][1][1]),20)

    def test_scatter_is_outside_rail_and_temple(self):
        for _,items in world.plan({'trees':48,'grass':96})['scatter']:
            for x,y,_ in items:
                self.assertFalse(-7.9 < x < -3.4)
                self.assertFalse(-1.2 < x < 9.5 and -1.7 < y < 9.2)
                self.assertLessEqual(abs(x),13.4)
                self.assertLessEqual(abs(y),13.4)

    def test_strict_invalid_field_and_type_rejection(self):
        examples=[{'name':'../bad'}, {'name':'a'*41}, {'seed':True},
                  {'seed':-1}, {'seed':2**31}, {'trees':48.5},
                  {'trees':49}, {'grass':-1}, {'grass':97},
                  {'layout':'SILENT_LOW_POLY'}, {'render_samples':2},
                  {'filename':'/sdcard/private.blend'}, {'source_url':'http://example.com/model'}]
        for payload in examples:
            with self.subTest(payload=payload),self.assertRaises(ValueError):
                world.validate(BUILD,payload)
        with self.assertRaises(ValueError):world.validate('python.eval',{})
        with self.assertRaises(ValueError):world.validate(BUILD,[])
        with self.assertRaises(ValueError):world.validate(AUDIT,{'seed':3})
        with self.assertRaises(ValueError):world.validate(BUILD,{'seed':float('nan')})

    def test_terrain_native_geometry_spec_is_manifold_grid(self):
        vs,fs=world._terrain_data()
        self.assertEqual(len(vs),41*41)
        self.assertEqual(len(fs),40*40)
        self.assertEqual(fs[0],(0,1,42,41))
        self.assertEqual(len({tuple(v) for v in vs}),len(vs))

    def test_arch_and_column_geometry_are_nonprimitive(self):
        v,f=world._arch_data();self.assertEqual(len(v),100)
        self.assertEqual(len(f),24*4+2)
        self.assertGreater(len(world._shaft_data()[1]),90)
        self.assertGreater(len(world._canopy_data()[1]),80)

    def test_no_fake_native_execution_without_bpy(self):
        with self.assertRaisesRegex(RuntimeError,'UNSUPPORTED_NATIVE_FEATURE'):
            world.execute(BUILD,{}, {})
        with self.assertRaisesRegex(RuntimeError,'UNSUPPORTED_NATIVE_FEATURE'):
            world.execute(BUILD,{}, {'scene':object()})
        with self.assertRaisesRegex(RuntimeError,'UNSUPPORTED_NATIVE_FEATURE'):
            world.audit(AUDIT,{}, {'scene':object()})

    def test_no_final_render_setting_in_validation_spec(self):
        permitted=set(world.validate(BUILD,{}))
        self.assertFalse(permitted.intersection({
            'samples','resolution','fps','engine','denoising','render_percentage','output_path'}))


if __name__=='__main__':unittest.main()
