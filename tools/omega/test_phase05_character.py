# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-side pure contract tests; never substitute for native bpy fixtures."""
import importlib.util
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "full-app/scripts/omega/phase05_character.py"
spec = importlib.util.spec_from_file_location("omega_phase05_character", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class CharacterContractTests(unittest.TestCase):
    def test_import_and_static_operations(self):
        self.assertEqual(mod.CONTRACT_VERSION, "RENDER-OMEGA-1")
        self.assertEqual(mod.OPERATION_NAMES, ("omega.character.create", "omega.character.audit"))
        self.assertNotIn("bpy", mod.__dict__, "importing phase module must not load Blender")

    def test_canonical_defaults(self):
        self.assertEqual(mod.validate("omega.character.create", {"name":"Hero"}), {
            "name": "Hero", "style": "stylized_anatomical_v1",
            "height_m": 1.75, "reference_sha256": None})
        self.assertEqual(mod.validate("omega.character.audit", {"name":"Hero"}), {"name":"Hero"})

    def test_invalid_inputs_are_rejected(self):
        bad = [None, [], {"name": ""}, {"name": "7Hero"},
               {"name": "../../etc"}, {"name": "A"*33},
               {"name": "H", "unknown": 3}, {"name": "H", "style": "photoreal"},
               {"name": "H", "height_m": True}, {"name": "H", "height_m": float("nan")},
               {"name": "H", "height_m": float("inf")},
               {"name": "H", "height_m": 100},
               {"name": "H", "reference_sha256": "/storage/emulated/0"},
               {"name": "H", "reference_sha256": "f"*65}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod.validate("omega.character.create", value)
        with self.assertRaises(ValueError):
            mod.validate("omega.character.audit", {"name":"Hero","height_m":1.7})
        with self.assertRaises(ValueError):
            mod.validate("python.eval", {"name":"Hero"})

    def test_source_revision_and_provenance(self):
        a = mod.validate("omega.character.create", {"name":"Hero", "height_m":1.75})
        b = mod.validate("omega.character.create", {"height_m":1.75,"name":"Hero"})
        self.assertEqual(mod._digest(a), mod._digest(b))
        self.assertNotEqual(mod._digest(a), mod._digest(mod.validate(
            "omega.character.create", {"name":"Hero","height_m":1.8})))
        self.assertEqual(len(mod._digest(a)),64)
        self.assertEqual(mod.validate("omega.character.create", {
            "name":"Hero","reference_sha256":"a"*64})["reference_sha256"], "a"*64)

    def test_declared_height_is_true_native_crown_height(self):
        self.assertAlmostEqual(mod._scale(1.75) * mod._SOURCE_HEIGHT, 1.75)
        self.assertAlmostEqual(mod._scale(2.1) * mod._SOURCE_HEIGHT, 2.1)
        self.assertGreater(mod._SOURCE_HEIGHT, 2.3)

    def test_stylized_anatomical_rings_have_positive_radius(self):
        controls=[(.9,.22,.16),(1.1,.18,.11),(1.7,.15,.1)]
        rings=mod._interp_rings(controls,.02)
        self.assertTrue(len(rings)>40)
        self.assertEqual(rings[0][2],.9)
        self.assertEqual(rings[-1][2],1.7)
        self.assertTrue(all(0<x[3] and 0<x[4] for x in rings))
        self.assertTrue(all(a[2]<b[2] for a,b in zip(rings,rings[1:])))
        for ring in rings:
            self.assertTrue(all(math.isfinite(v) for v in ring))

    def test_expected_rig_landmarks_are_mirrored(self):
        marks=mod._landmarks()
        for label in ("Shoulder","Elbow","Wrist","Hand","Hip","Knee","Ankle","Toe","Eye"):
            l,r=marks["Left"+label], marks["Right"+label]
            self.assertAlmostEqual(l[0],-r[0])
            self.assertAlmostEqual(l[1],r[1])
            self.assertAlmostEqual(l[2],r[2])
        self.assertGreater(marks["crown"][2], marks["pelvis"][2])

    def test_native_execution_is_never_faked_without_bpy(self):
        with self.assertRaises((RuntimeError,ValueError)):
            mod.execute("omega.character.create", {"name":"Test"}, {"scene": None})
        with self.assertRaises((RuntimeError,ValueError)):
            mod.audit("omega.character.audit", {"name":"Test"}, {"scene": None})

    def test_closed_loft_is_manifold_in_synthetic_mesh_arrays(self):
        # Exercise production surface construction through a tiny bpy *data*
        # capture, not a fake Blender execution receipt. True bpy is separate.
        from collections import Counter
        from types import SimpleNamespace
        class Mesh:
            materials = None
            def __init__(self):
                self.materials = []
            def from_pydata(self, vertices, edges, polygons):
                self.vertices = vertices
                self.polygons = [SimpleNamespace(vertices=face, use_smooth=False) for face in polygons]
            def update(self):
                pass
        class MeshStore:
            def __init__(self): self.last = None
            def new(self, name): self.last = Mesh(); return self.last
        class ObjectStore:
            def new(self, name, mesh): return SimpleNamespace(name=name, data=mesh)
        class ObjectCollection:
            def link(self, ob): pass
        meshes = MeshStore()
        api = SimpleNamespace(data=SimpleNamespace(meshes=meshes, objects=ObjectStore()))
        coll = SimpleNamespace(objects=ObjectCollection())
        rings = mod._interp_rings([(1.0,.23,.17), (1.12,.20,.14),
                                   (1.4,.31,.18)], .04)
        mod._loft(api, coll, "Surface", rings, object(), segments=24, uv=False)
        mesh = meshes.last
        counts = Counter()
        for poly in mesh.polygons:
            indices = poly.vertices
            for a,b in zip(indices, indices[1:]+indices[:1]):
                counts[tuple(sorted((a,b)))] += 1
        self.assertTrue(counts)
        self.assertEqual(set(counts.values()), {2})
        self.assertEqual(len(mesh.vertices),len(rings)*24)
        self.assertEqual(len(mesh.polygons),(len(rings)-1)*24+2)

    def test_actual_analytic_nose_relief_changes_surface_coordinates(self):
        from types import SimpleNamespace
        class Mesh:
            def __init__(self): self.materials=[]
            def from_pydata(self, verts, edges, faces):
                self.vertices = verts
                self.polygons = [SimpleNamespace(vertices=face, use_smooth=False) for face in faces]
            def update(self): pass
        class MeshStore:
            def __init__(self): self.saved=[]
            def new(self,name): self.saved.append(Mesh()); return self.saved[-1]
        class ObjectStore:
            def new(self,name,mesh): return SimpleNamespace(data=mesh)
        class Objects:
            def link(self, obj): pass
        store=MeshStore()
        fake=SimpleNamespace(data=SimpleNamespace(meshes=store,objects=ObjectStore()))
        coll=SimpleNamespace(objects=Objects())
        rings=[(0,0,z,.165,.149) for z in (2.07,2.08,2.09,2.10,2.11)]
        mod._loft(fake,coll,"Plain",rings,object(),segments=64,uv=False)
        mod._loft(fake,coll,"Relief",rings,object(),segments=64,uv=False,face_relief=True)
        # theta=270 degrees: the nose is exactly at x=0, forward is -Y.
        idx=2*64+48
        self.assertLess(store.saved[1].vertices[idx][1],
                        store.saved[0].vertices[idx][1]-0.035)


if __name__ == "__main__":
    unittest.main()
