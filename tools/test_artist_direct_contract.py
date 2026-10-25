# SPDX-License-Identifier: GPL-2.0-or-later
"""Offline trust and gesture tests; never substitute a simulated Blender render."""
import importlib
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_artist_direct_contract as Contract

A="a"*64
B="b"*64

def valid():
    return {"object":"SculptedHero","expected_mesh_sha256":A,
            "expected_view_sha256":B,
            "points":[{"x":.42,"y":.56,"pressure":.75},
                      {"x":.51,"y":.55,"pressure":.9}]}

class ArtistDirectContractTests(unittest.TestCase):
    def test_safe_typed_live_sculpt(self):
        self.assertEqual(Contract.validate(Contract.OPS[2],valid()),valid())
        fields=Contract.to_operator_stroke(valid()["points"],1001,501)
        self.assertEqual(len(fields),2)
        self.assertAlmostEqual(fields[0]["mouse"][0],420)
        self.assertAlmostEqual(fields[0]["mouse"][1],220)
        self.assertAlmostEqual(fields[1]["mouse"][0],510)
        self.assertAlmostEqual(fields[1]["mouse"][1],225)
        self.assertEqual(fields[0]["time"],0)
        self.assertGreater(fields[1]["time"],0)
        self.assertTrue(fields[0]["is_start"])
        self.assertFalse(fields[1]["is_start"])
        self.assertEqual(fields[0]["pressure"],.75)

    def test_connected_sculpt_copy_requires_safe_budget_and_distinct_target(self):
        valid={"object":"SculptedHero","name":"ScupltCandidate002",
               "voxel_size_m":.015,"max_voxels":1000000,
               "location":[2.0,0.0,0.0]}
        self.assertEqual(Contract.validate(Contract.OPS[5],valid),valid)
        for change in (
            {"name":"SculptedHero"},{"name":"../Unsafe"},
            {"location":[0,0]},{"location":[0,0,float("nan")]},
            {"voxel_size_m":.00001},{"max_voxels":100000000},
            {"max_voxels":True},{"__arbitrary_bpy__":"bpy.ops.wm.quit_blender()"},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    Contract.validate(Contract.OPS[5],dict(valid,**change))
        self.assertTrue(Contract.capabilities()[-1]["non_destructive_surface_copy"])
        self.assertIn("location",Contract.capabilities()[-1]["input_schema"]["required"])

    def test_native_essentials_brush_allowlist(self):
        for brush in Contract.BRUSH_PRESETS:
            request={"object":"SculptedHero","brush":brush}
            self.assertEqual(Contract.validate(Contract.OPS[4],request),request)
        for brush in ("../path","bpy.ops.wm.open_mainfile","Unknown",3,["DRAW"],None):
            with self.subTest(brush=brush):
                with self.assertRaises(ValueError):
                    Contract.validate(Contract.OPS[4],{"object":"SculptedHero","brush":brush})
        self.assertEqual(Contract.BRUSH_PRESETS["CLAY_STRIPS"],"Clay Strips")
        self.assertIn("brush",next(row for row in Contract.capabilities() if row["operation"]==Contract.OPS[4])["input_schema"]["required"])

    def test_rejects_unsafe_or_unverified_sculpt_requests(self):
        bad=[
            {"object":"SculptedHero","points":valid()["points"]},
            dict(valid(),object="../Gallery"),
            dict(valid(),object="bpy.ops.object.delete()"),
            dict(valid(),expected_mesh_sha256="$prev_mesh_sha256"),
            dict(valid(),expected_view_sha256="unsafe"),
            dict(valid(),points=[{"x":.5,"y":.5}]),
            dict(valid(),points=[{"x":.5,"y":.5},{"x":.5,"y":.5}]),
            dict(valid(),points=[{"x":float("nan"),"y":.5},{"x":.4,"y":.4}]),
            dict(valid(),points=[{"x":True,"y":.3},{"x":.4,"y":.2}]),
            dict(valid(),points=[{"x":1.1,"y":.3},{"x":.4,"y":.2}]),
            dict(valid(),points=[{"x":.2,"y":.4,"pressure":2},{"x":.3,"y":.4}]),
            dict(valid(),points=valid()["points"],shell="rm -rf"),
        ]
        for payload in bad:
            with self.subTest(payload=str(payload)[:90]):
                with self.assertRaises(ValueError):
                    Contract.validate(Contract.OPS[2],payload)

    def test_requires_real_view_revision_and_refuses_bad_view(self):
        matrix=[[float(i==j) for j in range(4)] for i in range(4)]
        sha=Contract.view_digest(100,200,matrix)
        self.assertEqual(len(sha),64)
        self.assertNotEqual(sha,Contract.view_digest(101,200,matrix))
        self.assertNotEqual(sha,Contract.view_digest(100,201,matrix))
        with self.assertRaises(ValueError):Contract.view_digest(0,200,matrix)
        with self.assertRaises(ValueError):Contract.view_digest(100,200,[[float("nan")]*4]*4)

    def test_discoverability_no_arbitrary_python(self):
        rows=Contract.capabilities()
        self.assertEqual({row["operation"] for row in rows},set(Contract.OPS))
        for row in rows:
            self.assertFalse(row["native_touch_event_fabricated"])
            self.assertTrue(row["requires_native_blender"])
        self.assertIn("expected_view_sha256",rows[2]["input_schema"]["required"])

    def test_native_topology_and_revision_checks_with_mesh_values(self):
        # Mock only the *data structures* for pure host checks, not execution.
        fake=types.ModuleType("bpy")
        sys.modules["bpy"]=fake
        try:
            Native=importlib.import_module("render_artist_direct")
            def vertex(x):
                return types.SimpleNamespace(co=types.SimpleNamespace(x=x,y=0.,z=0.))
            data=types.SimpleNamespace(vertices=[vertex(0.),vertex(1.),vertex(2.)],
                        polygons=[],edges=[types.SimpleNamespace(vertices=(0,1))])
            obj=types.SimpleNamespace(data=data)
            a=Native._revision(obj)
            self.assertEqual(Native._components(obj)["connected_components"],2)
            data.edges.append(types.SimpleNamespace(vertices=(1,2)))
            self.assertEqual(Native._components(obj)["connected_components"],1)
            data.vertices[2].co.x=3.
            self.assertNotEqual(a,Native._revision(obj))
            class Huge:
                def __len__(self):return Contract.MAX_HASH_VERTICES+1
            data.vertices=Huge()
            with self.assertRaisesRegex(ValueError,"TOO_DENSE"):
                Native._revision(obj)
        finally:
            sys.modules.pop("render_artist_direct",None)
            sys.modules.pop("bpy",None)

    def test_bridge_packaging_and_guardrails(self):
        bridge=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        ops=(ROOT/"full-app/scripts/render_production_contract.py").read_text()
        runtime=(ROOT/"full-app/scripts/render_unified_workspace.py").read_text()
        staging=(ROOT/"tools/assemble_full_native.py").read_text()
        session=(ROOT/"full-app/scripts/render_session_tools.py").read_text()
        dispatch=(ROOT/"full-app/scripts/render_production.py").read_text()
        for op in Contract.OPS:
            self.assertIn(op,bridge)
            self.assertIn(op,ops)
            self.assertIn(op,runtime)
        for name in ("render_artist_direct_contract.py","render_artist_direct.py",
                     "render_artist_direct_ui.py"):
            self.assertIn(name,staging)
        self.assertIn("render_artist_direct_ui.install()",session)
        self.assertIn('"studio.artist.sculpt.stroke"',dispatch)
        self.assertIn("render_artist_direct.execute",runtime)
        self.assertIn('"screenshot.preview"',bridge)
        capture=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionCapture.java").read_text()
        self.assertIn("PixelCopy.request(",capture)
        self.assertIn("preview_only",capture)
        self.assertIn("final_render_quality_unchanged",capture)
        self.assertIn("RENDER_WINDOW_NOT_VISIBLE",capture)
        self.assertIn("DIRECT_SCULPT_SURFACE_STILL_DISCONNECTED",
                      (ROOT/"full-app/scripts/render_artist_direct.py").read_text())
        self.assertIn("DIRECT_SCULPT_NO_MEASURED_MESH_CHANGE",
                      (ROOT/"full-app/scripts/render_artist_direct.py").read_text())
        self.assertNotIn("exec(",(ROOT/"full-app/scripts/render_artist_direct.py").read_text())
        self.assertNotIn("eval(",(ROOT/"full-app/scripts/render_artist_direct.py").read_text())

if __name__=="__main__":
    unittest.main()
