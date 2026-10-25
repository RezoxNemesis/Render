"""Host validation only; no geometry, Blender model or Android render created."""
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'full-app/scripts/render_body_blockout.py'
spec=importlib.util.spec_from_file_location('body_profile_contract',path)
body=importlib.util.module_from_spec(spec);spec.loader.exec_module(body)


class BodyProfileContractTests(unittest.TestCase):
    def test_height_only_scales_unset_dimensions_without_changing_explicit_values(self):
        p=body.validate_profile({'height_m':1.98,'waist_width_m':.39})
        self.assertEqual(1.98,p['height_m'])
        self.assertAlmostEqual(.41*1.2,p['shoulder_width_m'])
        self.assertEqual(.39,p['waist_width_m'])

    def test_nonfinite_or_boolean_dimensions_are_rejected(self):
        for value in [float('nan'),float('inf'),True,-1,0,'1.65']:
            with self.subTest(value=value),self.assertRaises(ValueError):
                body.validate_profile({'height_m':value})

    def test_unknown_profile_fields_are_not_executed_or_ignored(self):
        with self.assertRaisesRegex(ValueError,'INVALID_BODY_PROPORTIONS'):
            body.validate_profile({'code':'arbitrary action'})

    def test_disconnected_hip_and_leg_dimensions_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'BODY_HIP_LEG_RATIO_OUT_OF_RANGE'):
            body.validate_profile({'hip_width_m':.20,'thigh_diameter_m':.21})

    def test_schema_is_closed_and_lists_all_available_controls(self):
        schema=body.profile_schema()
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(body.DEFAULTS),set(schema['properties']))

    def test_metre_dimensions_respect_an_existing_centimetre_scene(self):
        self.assertEqual([(0,0,165)],body.scene_coordinates([(0,0,1.65)],.01))


if __name__=='__main__':unittest.main()
