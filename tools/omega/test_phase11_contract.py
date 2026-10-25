# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure Phase 11 allowlist/security regressions. Run with Python, no bpy required.

Real native Blender fixture is native-tests/omega/phase11/test_phase11_bpy.py.
This suite must never be reported as evidence of a native mesh operation.
"""
import importlib.util
import math
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[2] / "full-app/scripts/omega/phase11_artist.py"
spec = importlib.util.spec_from_file_location("phase11_artist_test", MODULE_PATH)
artist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artist)

REV = "a" * 64
BASE = {
    "tool": "mesh.edit_surface_stroke",
    "target": "OmegaMesh",
    "expected_mode": "EDIT",
    "expected_scene_revision": REV,
    "postcondition": "evaluated_mesh_changed",
    "parameters": {"radius": 0.6, "strength": 0.25,
                   "direction": [0, 0, 1], "samples": [[0, 0, 1], [0.1, 0, 1]]},
}


def changed(**fields):
    obj = dict(BASE)
    obj["parameters"] = dict(BASE["parameters"])
    obj.update(fields)
    return obj


class Phase11ContractTests(unittest.TestCase):
    def bad(self, payload, code="INVALID_ARGUMENTS"):
        with self.assertRaises(ValueError) as e:
            artist.validate("omega.artist.execute_tool", payload)
        self.assertEqual(str(e.exception), code)

    def test_canonical_names_and_version(self):
        self.assertEqual(artist.CONTRACT_VERSION, "RENDER-OMEGA-1")
        self.assertEqual(artist.OPERATION_NAMES,
                         ("omega.artist.inspect_ui", "omega.artist.execute_tool"))

    def test_inspection_read_only_schema(self):
        self.assertEqual(artist.validate("omega.artist.inspect_ui", {}), {"target": None})
        self.assertEqual(artist.validate("omega.artist.inspect_ui", {"target": "OmegaMesh"}),
                         {"target": "OmegaMesh"})
        for p in ({"snapshot_path": "/sdcard/Gallery"}, {"target": "../data"},
                  {"target": "x", "screenshot": True}, []):
            with self.assertRaises(ValueError):
                artist.validate("omega.artist.inspect_ui", p)

    def test_typed_mesh_edit_is_valid(self):
        self.assertEqual(artist.validate("omega.artist.execute_tool", changed())["tool"],
                         "mesh.edit_surface_stroke")

    def test_explicit_unsupported_blender_operators(self):
        for op in ("python.eval", "bpy.ops.wm.open_mainfile", "mesh.sculpt_stroke",
                   "screen.fake_tap", "bpy.ops.mesh.delete", "object.delete", "shell.exec"):
            self.bad(changed(tool=op), "UNSUPPORTED_NATIVE_FEATURE")
        with self.assertRaises(ValueError) as e:
            artist.validate("omega.artist.raw_python", {})
        self.assertEqual(str(e.exception), "UNSUPPORTED_NATIVE_FEATURE")

    def test_deny_payload_injection(self):
        self.bad(changed(path="/sdcard/DCIM/Camera"))
        self.bad(changed(script="import os; os.system('rm -rf /')"))
        self.bad(changed(parameters={**BASE["parameters"], "operator": "wm.quit_blender"}))
        self.bad(changed(parameters={**BASE["parameters"], "__class__": "bpy"}))

    def test_names_and_scene_revision(self):
        for n in ("", "../Mesh", "X"*65, "é", "With spaces", "/etc/passwd", "0Mesh"):
            self.bad(changed(target=n))
        for revision in ("", "x"*64, "A"*64, "0"*63, 4, None):
            self.bad(changed(expected_scene_revision=revision))

    def test_mode_and_postconditions_cannot_be_forged(self):
        self.bad(changed(expected_mode="SCULPT"))
        self.bad(changed(expected_mode="OBJECT"))
        self.bad(changed(postcondition="looks_professional"))
        self.bad(changed(postcondition=None))

    def test_finite_vectors_and_stroke_limits(self):
        for strength in (True, False, -1, 0, math.nan, math.inf, 100):
            self.bad(changed(parameters={**BASE["parameters"], "strength": strength}))
        for radius in (0, -1, math.inf, "1", 1000):
            self.bad(changed(parameters={**BASE["parameters"], "radius": radius}))
        for direction in ([], [0, 0, 0], [1, 2], [1, 2, math.nan], "[0,0,1]", [True, 0, 1]):
            self.bad(changed(parameters={**BASE["parameters"], "direction": direction}))
        for samples in ([], [[0, 0, 0]]*33, [[0, 0, 999999]], [[0, True, 0]], "1,2,3"):
            self.bad(changed(parameters={**BASE["parameters"], "samples": samples}))

    def test_selection_and_switch_have_small_allowlists(self):
        select = changed(tool="object.select", expected_mode="OBJECT",
                         postcondition="selection_active", parameters={})
        self.assertEqual(artist.validate("omega.artist.execute_tool", select)["tool"], "object.select")
        self.bad({**select, "parameters": {"touch": [35, 90]}})
        mode = changed(tool="object.mode_set", expected_mode="OBJECT",
                       postcondition="mode_changed", parameters={"mode": "EDIT"})
        self.assertEqual(artist.validate("omega.artist.execute_tool", mode)["tool"], "object.mode_set")
        self.bad({**mode, "parameters": {"mode": "OBJECT"}})
        self.bad({**mode, "parameters": {"mode": "SCULPT"}})
        self.bad({**mode, "parameters": {"mode": "EDIT", "operator": "a.b"}})
        self.assertEqual(artist.validate("omega.artist.execute_tool",
                         {**mode, "expected_mode": "EDIT", "parameters": {"mode": "OBJECT"}})["expected_mode"], "EDIT")

    def test_modifier_no_destructive_decimation_or_render_downgrade(self):
        base = changed(tool="modifier.add", expected_mode="OBJECT",
                       postcondition="modifier_present", parameters={"kind": "BEVEL", "name": "SurfaceBevel", "width": 0.025, "segments": 3})
        self.assertEqual(artist.validate("omega.artist.execute_tool", base)["tool"], "modifier.add")
        self.bad({**base, "parameters": {"kind": "DECIMATE", "name": "Bad"}}, "UNSUPPORTED_NATIVE_FEATURE")
        self.bad({**base, "parameters": {"kind": "BEVEL", "name": "Good", "render_samples": 1}})
        self.bad({**base, "parameters": {"kind": "BEVEL", "name": "Good", "width": 0}})
        self.bad({**base, "parameters": {"kind": "BEVEL", "name": "Good", "segments": True}})
        self.assertEqual(artist.validate("omega.artist.execute_tool", {**base,
              "parameters": {"kind": "SUBSURF", "name": "SmoothMesh", "levels": 2}})["tool"], "modifier.add")

    def test_never_fabricates_bpy_without_runtime(self):
        if artist.bpy is not None:
            self.skipTest("This process already provides the real bpy module")
        with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
            artist.execute("omega.artist.inspect_ui", {}, {"scene": object()})
        with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
            artist.audit("omega.artist.inspect_ui", {}, {"scene": object()})
        with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
            artist.execute("omega.artist.execute_tool", changed(), {"scene": object()})


if __name__ == "__main__":
    unittest.main()
