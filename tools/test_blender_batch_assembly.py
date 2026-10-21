"""Static and pure preflight regression tests for native Android PBR assemblies."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

HELPER=Path(__file__).resolve().parents[1]/"full-app/scripts/render_batch_assembly.py"


def helper():
    fake=types.ModuleType("bpy")
    with patch.dict(sys.modules,{"bpy":fake}):
        spec=importlib.util.spec_from_file_location("render_batch_assembly_test",HELPER)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def good():
    return {"assembly":"ExteriorFacade","parts":[
        {"name":"LimestoneBand","kind":"CUBE",
         "location":[0,0,4],"scale":[6,4,.2],
         "color":[.72,.69,.60],"roughness":.62,"bevel":.08},
        {"name":"GlassWindow","kind":"CUBE",
         "location":[1,-4,5],"scale":[.5,.1,1],
         "color":[.08,.23,.40],"metallic":.3,"roughness":.18}
    ]}


class AssemblyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.m=helper()

    def test_valid_bounded_pbr_scene(self):
        key,parts,digest=self.m.validate_assembly(good())
        self.assertEqual(key,"ExteriorFacade")
        self.assertEqual(len(parts),2)
        self.assertEqual(len(digest),64)
        self.assertEqual(parts[0]["bevel"],.08)
        self.assertEqual(parts[1]["roughness"],.18)

    def test_same_input_is_idempotent_fingerprint(self):
        a=good()
        b=good()
        b["parts"][0]["bevel"]=.08
        self.assertEqual(self.m.validate_assembly(a)[-1],
                         self.m.validate_assembly(b)[-1])
        b["parts"][0]["color"]=[.20,.69,.60]
        self.assertNotEqual(self.m.validate_assembly(a)[-1],
                            self.m.validate_assembly(b)[-1])

    def test_rejects_unsafe_inputs_without_touching_bpy(self):
        variants=[
            {"assembly":"../wrong","parts":good()["parts"]},
            {"assembly":"Safe","parts":[]},
            {"assembly":"Safe","parts":good()["parts"]*49},
            {"assembly":"Safe","parts":[dict(good()["parts"][0],kind="PYTHON")]},
            {"assembly":"Safe","parts":[dict(good()["parts"][0],location=[0,True,2])]},
            {"assembly":"Safe","parts":[dict(good()["parts"][0],scale=[0,1,1])]},
            {"assembly":"Safe","parts":[dict(good()["parts"][0],color=[1,0,2])]},
            {"assembly":"Safe","parts":[dict(good()["parts"][0],bevel=3)]},
            {"assembly":"Safe","parts":[dict(good()["parts"][0],code="bpy.ops.wm.open_mainfile")]},
            {"assembly":"Safe","parts":[good()["parts"][0],good()["parts"][0]]}
        ]
        for args in variants:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    self.m.validate_assembly(args)

    def test_no_external_script_execution(self):
        code=HELPER.read_text(encoding="utf-8")
        for needle in ("exec(", "eval(", "subprocess", "os.system(",
                       "bpy.ops.wm.open_mainfile", "http", "requests."):
            self.assertNotIn(needle,code)


if __name__=="__main__":
    unittest.main()
