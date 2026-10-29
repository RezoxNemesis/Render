# SPDX-License-Identifier: GPL-2.0-or-later
"""Semantic tests in real Blender, including evaluated instances and deformation.

Run with Blender --factory-startup --background --python-exit-code 1 --python
this_file.py, or a Python environment with the official bpy wheel installed.
No desktop/device visual-quality or performance claims are made by these tests.
"""
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_creator_contract as C
import render_creator_ops as Ops


class NativeCreatorTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

    def run_op(self, suffix, payload):
        return Ops.execute("studio.create."+suffix, payload, Path(self.temporary.name), self.scene)

    def model(self, name="Asset", kind="column", detail=2, **kwargs):
        receipt = self.run_op("model", {"name": name, "kind": kind, "detail": detail, **kwargs})
        return self.scene.objects[receipt["object"]]

    def snapshot(self):
        return {kind: frozenset(x.as_pointer() for x in getattr(bpy.data, kind))
                for kind in ("objects", "meshes", "materials", "node_groups", "actions", "armatures", "cameras")}

    def test_all_model_presets_create_valid_native_meshes(self):
        for kind in C.MODEL_KINDS:
            for detail in (1, 2, 3):
                ob = self.model(kind+str(detail), kind, detail)
                self.assertEqual(ob.type, "MESH")
                self.assertGreater(len(ob.data.polygons), 4)
                self.assertFalse(ob.data.validate(verbose=False))
                self.assertTrue(all(face.area > 1e-10 for face in ob.data.polygons), (kind, detail))
                self.assertTrue(all(math.isfinite(x) for v in ob.data.vertices for x in v.co))
                ob.data.calc_loop_triangles()
                estimate = C.estimate_model(kind, detail)
                self.assertLessEqual(len(ob.data.vertices), estimate["vertices"])
                self.assertLessEqual(len(ob.data.loop_triangles), estimate["triangles"])
                self.assertEqual(len(ob.data.materials), 2)
                bm = bmesh.new()
                try:
                    bm.from_mesh(ob.data)
                    self.assertTrue(all(edge.is_manifold for edge in bm.edges), (kind, detail))
                    self.assertGreater(bm.calc_volume(signed=True), 0, (kind, detail))
                finally:
                    bm.free()

    def test_seeded_rock_and_terrain_are_reproducible(self):
        a, b, c = (self.model("Rock"+str(i), "rock", seed=seed) for i, seed in enumerate((17, 17, 18)))
        coordinates = lambda ob: [tuple(v.co) for v in ob.data.vertices]
        self.assertEqual(coordinates(a), coordinates(b))
        self.assertNotEqual(coordinates(a), coordinates(c))
        for style in C.TERRAIN_STYLES:
            results = [self.run_op("terrain", {"name": style+str(i), "style": style,
                        "resolution": 12, "seed": seed}) for i, seed in enumerate((17, 17, 18))]
            meshes = [self.scene.objects[r["object"]] for r in results]
            self.assertEqual(coordinates(meshes[0]), coordinates(meshes[1]))
            self.assertNotEqual(coordinates(meshes[0]), coordinates(meshes[2]))
            self.assertEqual(len(meshes[0].data.vertices), 13**2)
            self.assertEqual(len(meshes[0].data.polygons), 12**2)
            self.assertEqual(len(meshes[0].data.uv_layers[0].data), 12**2*4)
            self.assertGreater(results[0]["height_range"][1], results[0]["height_range"][0])
        maximum = self.run_op("terrain", {"name": "MaximumTerrain", "resolution": 128})
        self.assertEqual(maximum["vertices"], 16641)

    def test_scatter_has_actual_evaluated_linked_instances(self):
        source = self.model("Tree", "tree", 2)
        terrain_result = self.run_op("terrain", {"name": "Terrain", "resolution": 16, "height": 5})
        result = self.run_op("scatter", {"name": "Forest", "source": source.name, "count": 128,
                             "terrain": terrain_result["object"], "extent": 40, "seed": 23})
        forest = self.scene.objects[result["object"]]
        self.assertEqual(len(forest.data.vertices), 128)
        self.assertEqual(len(forest.data.polygons), 0)
        self.assertEqual(len(self.scene.objects), 3)
        group = forest.modifiers[0].node_group
        self.assertFalse(any(n.bl_idname == "GeometryNodeRealizeInstances" for n in group.nodes))
        info = next(n for n in group.nodes if n.bl_idname == "GeometryNodeObjectInfo")
        self.assertEqual(info.inputs["Object"].default_value, source)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        instances = [instance.matrix_world.copy() for instance in depsgraph.object_instances
                     if instance.is_instance and instance.parent.original == forest]
        self.assertEqual(len(instances), 128)
        self.assertTrue(all(matrix.translation.z >= 0 for matrix in instances))
        # Changing one source vertex must change all evaluated instance geometry.
        source.data.vertices[-1].co.z += .5
        source.data.update()
        bpy.context.view_layer.update()
        copies = [instance.object.data for instance in bpy.context.evaluated_depsgraph_get().object_instances
                  if instance.is_instance and instance.parent.original == forest]
        self.assertEqual(len(copies), 128)
        self.assertTrue(all(abs(mesh.vertices[-1].co.z-source.data.vertices[-1].co.z) < 1e-5 for mesh in copies))
        again = self.run_op("scatter", {"name": "ForestAgain", "source": source.name, "count": 128,
                            "terrain": "Terrain", "extent": 40, "seed": 23})
        second = self.scene.objects[again["object"]]
        self.assertEqual([tuple(v.co) for v in forest.data.vertices], [tuple(v.co) for v in second.data.vertices])

    def test_scatter_limit_rejection_and_sparse_storage(self):
        # Two-triangle source exercises the public 10k count without high render cost.
        mesh = bpy.data.meshes.new("TinyMesh")
        mesh.from_pydata([(0,0,0), (.01,0,0), (.01,.01,.01), (0,.01,0)], [], [(0,1,2,3)])
        ob = bpy.data.objects.new("Tiny", mesh); self.scene.collection.objects.link(ob)
        result = self.run_op("scatter", {"name": "TenThousand", "source": "Tiny", "count": 10000})
        self.assertEqual(result["instances"], 10000)
        self.assertEqual(len(self.scene.objects), 2)
        self.assertEqual(len(self.scene.objects["TenThousand"].data.vertices), 10000)
        state = self.snapshot()
        with self.assertRaisesRegex(ValueError, "EDITABLE_SURFACE"):
            self.run_op("rig", {"object": "TenThousand", "name": "InvalidPointRig"})
        self.assertEqual(self.snapshot(), state)
        huge = self.model("HeavySource", "column", 3)
        state = self.snapshot()
        with self.assertRaisesRegex(ValueError, "TRIANGLE_BUDGET"):
            self.run_op("scatter", {"name": "TooHeavy", "source": huge.name, "count": 10000})
        self.assertEqual(self.snapshot(), state)
        self.run_op("terrain", {"name": "SmallTerrain", "size": 1, "resolution": 4})
        state = self.snapshot()
        with self.assertRaisesRegex(ValueError, "COVERAGE"):
            self.run_op("scatter", {"name": "NoCoverage", "source": "Tiny", "count": 100,
                                     "terrain": "SmallTerrain", "extent": 2048})
        self.assertEqual(self.snapshot(), state)

    def test_scatter_preserves_source_rotation_scale_without_source_translation(self):
        source = self.model("TransformSource", "tree")
        source.location = (100, 200, 300)
        source.rotation_euler = (.2, .3, .4)
        source.scale = (2, 3, 4)
        bpy.context.view_layer.update()
        receipt = self.run_op("scatter", {"name": "TransformInstances", "source": source.name,
                              "count": 3, "min_scale": 1, "max_scale": 1, "extent": 2})
        instancer = self.scene.objects[receipt["object"]]
        bpy.context.view_layer.update()
        evaluated = [item.matrix_world.copy() for item in bpy.context.evaluated_depsgraph_get().object_instances
                     if item.is_instance and item.parent.original == instancer]
        self.assertEqual(len(evaluated), 3)
        for matrix in evaluated:
            for got, want in zip(matrix.to_scale(), (2, 3, 4)):
                self.assertAlmostEqual(got, want, places=4)
            self.assertLess(abs(matrix.translation.x), 1.001)
            self.assertLess(abs(matrix.translation.y), 1.001)
            self.assertLess(abs(matrix.translation.z), 3)

    def test_procedural_materials_are_connected_and_object_local(self):
        source = self.model("Source")
        linked = source.copy(); linked.name = "Linked"; self.scene.collection.objects.link(linked)
        old_mesh = source.data
        old_indices = [f.material_index for f in source.data.polygons]
        for preset in C.MATERIAL_PRESETS:
            receipt = self.run_op("material", {"object": linked.name, "preset": preset, "color": [.2,.4,.7]})
            mat = bpy.data.materials[receipt["material"]]
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            output = mat.node_tree.nodes.get("Material Output")
            self.assertTrue(output.inputs["Surface"].is_linked)
            self.assertTrue(all(f.material_index == len(linked.data.materials)-1 for f in linked.data.polygons))
            if preset != "emissive":
                self.assertTrue(bsdf.inputs["Normal"].is_linked)
                self.assertTrue(bsdf.inputs["Base Color"].is_linked)
            else:
                self.assertGreater(bsdf.inputs["Emission Strength"].default_value, 0)
        self.assertEqual(source.data, old_mesh)
        self.assertNotEqual(linked.data, source.data)
        self.assertEqual([f.material_index for f in source.data.polygons], old_indices)

    def test_motion_evaluates_and_preserves_existing_animation(self):
        for preset in C.MOTION_PRESETS:
            ob = self.model("Motion"+preset)
            self.scene.frame_set(1)
            result = self.run_op("motion", {"object": ob.name, "preset": preset, "start": 1, "end": 33, "amount": 2})
            self.assertEqual(result["fcurves"], 3)
            self.scene.frame_set(1)
            initial = ob.matrix_world.copy()
            self.scene.frame_set(9)
            changed = ob.matrix_world.copy()
            self.assertGreater(sum(abs(initial[i][j]-changed[i][j]) for i in range(4) for j in range(4)), .1)
            if preset == "turntable":
                self.assertAlmostEqual(ob.rotation_euler.z, math.pi, places=5)
            if preset == "float":
                self.assertAlmostEqual(ob.location.z, 2, places=4)
            if preset == "bounce":
                self.scene.frame_set(17); self.assertAlmostEqual(ob.location.z, 2, places=4)
            self.scene.frame_set(41)
            if preset == "float":
                self.assertAlmostEqual(ob.location.z, 2, places=4)
            before = self.snapshot()
            action = ob.animation_data.action
            with self.assertRaisesRegex(ValueError, "EXISTING_ANIMATION"):
                self.run_op("motion", {"object": ob.name, "preset": "float"})
            self.assertEqual(ob.animation_data.action, action)
            self.assertEqual(before, self.snapshot())

    def test_cameras_aim_at_bounds_and_orbit_moving_targets(self):
        target = self.model("Target")
        target.location = (3, -2, 4)
        bpy.context.view_layer.update()
        self.scene.frame_set(17, subframe=.25)
        for preset in C.CAMERA_PRESETS:
            result = self.run_op("camera", {"target": target.name, "preset": preset, "name": "Camera"+preset,
                                "start": 1, "end": 33, "radius": 8})
            camera = self.scene.objects[result["object"]]
            self.assertEqual(self.scene.camera, camera)
            self.assertEqual(self.scene.frame_current, 17)
            self.assertAlmostEqual(self.scene.frame_subframe, .25)
            bpy.context.view_layer.update()
            center, _, _ = Ops._bounds(target, bpy.context.evaluated_depsgraph_get())
            direction = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            expected = (center-camera.matrix_world.translation).normalized()
            self.assertGreater(direction.dot(expected), .999)
        camera = self.scene.objects["Cameraorbit"]
        self.scene.frame_set(1); first = camera.matrix_world.translation.copy()
        self.scene.frame_set(17); middle = camera.matrix_world.translation.copy()
        self.assertGreater((first-middle).length, 10)
        self.run_op("motion", {"object": target.name, "preset": "float", "start": 1, "end": 33, "amount": 3})
        self.run_op("camera", {"target": target.name, "preset": "orbit", "name": "TrackingCamera", "start": 1, "end": 33})
        camera = self.scene.objects["TrackingCamera"]
        for frame in (1, 9, 17, 25, 33):
            self.scene.frame_set(frame)
            center, _, _ = Ops._bounds(target, bpy.context.evaluated_depsgraph_get())
            forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
            self.assertGreater(forward.dot((center-camera.matrix_world.translation).normalized()), .9999)

    def test_rig_weights_and_actual_deformation(self):
        ob = self.model("FlexibleColumn", detail=3)
        ob.location = (2, 3, 1)
        ob.scale = (1.1, .8, 1.2)
        bpy.context.view_layer.update()
        ob.select_set(True); bpy.context.view_layer.objects.active = ob
        result = self.run_op("rig", {"object": ob.name, "name": "FlexibleRig", "segments": 6})
        rig = self.scene.objects[result["rig"]]
        self.assertEqual(rig.type, "ARMATURE")
        self.assertEqual(len(rig.data.bones), 6)
        self.assertFalse(result["humanoid_auto_rig"])
        self.assertEqual(bpy.context.view_layer.objects.active, ob)
        self.assertTrue(ob.select_get())
        group_indices = {ob.vertex_groups[n].index for n in result["bones"]}
        for vertex in ob.data.vertices:
            total = sum(g.weight for g in vertex.groups if g.group in group_indices)
            self.assertAlmostEqual(total, 1., places=5)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        before = [v.co.copy() for v in ob.evaluated_get(depsgraph).data.vertices]
        bone = rig.pose.bones[result["bones"][2]]
        bone.rotation_mode = "XYZ"; bone.rotation_euler.x = .65
        bpy.context.view_layer.update()
        after = [v.co.copy() for v in ob.evaluated_get(depsgraph).data.vertices]
        self.assertGreater(max((a-b).length for a, b in zip(before, after)), .1)
        self.assertEqual(rig.mode, "OBJECT")
        state = self.snapshot()
        with self.assertRaisesRegex(ValueError, "EXISTING_ARMATURE"):
            self.run_op("rig", {"object": ob.name, "name": "AnotherRig"})
        self.assertEqual(state, self.snapshot())

    def test_collisions_and_invalid_payloads_leave_scene_unchanged(self):
        ob = self.model("Existing")
        before = self.snapshot()
        for payload in ({"name": "Existing", "kind": "tree"},
                        {"name": "New", "kind": "tree", "size": math.nan},
                        {"name": "New", "kind": "tree", "python": "bpy.ops.wm.read_homefile()"}):
            with self.assertRaises(ValueError):
                self.run_op("model", payload)
            self.assertEqual(before, self.snapshot())
        before_vertices = [tuple(v.co) for v in ob.data.vertices]
        with patch.object(Ops, "_simple_material", side_effect=RuntimeError("injected native failure")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.run_op("model", {"name": "Partial", "kind": "crate"})
        self.assertEqual(before, self.snapshot())
        self.assertEqual(before_vertices, [tuple(v.co) for v in ob.data.vertices])

    def test_action_and_camera_failure_roll_back_datablocks_and_state(self):
        ob = self.model("Existing")
        self.run_op("camera", {"target": ob.name, "preset": "hero", "name": "PreviousCamera"})
        camera = self.scene.camera
        self.scene.frame_set(7, subframe=.25)
        before = self.snapshot()
        transform = ob.matrix_basis.copy()
        with patch.object(Ops, "_finish_action", side_effect=RuntimeError("native curve failure")):
            with self.assertRaisesRegex(RuntimeError, "native curve"):
                self.run_op("motion", {"object": ob.name, "preset": "orbit"})
        self.assertIsNone(ob.animation_data)
        self.assertEqual(ob.matrix_basis, transform)
        self.assertEqual(before, self.snapshot())
        with patch.object(Ops, "_finish_action", side_effect=RuntimeError("native curve failure")):
            with self.assertRaisesRegex(RuntimeError, "native curve"):
                self.run_op("camera", {"target": ob.name, "preset": "orbit", "name": "PartialCamera"})
        self.assertEqual(self.scene.camera, camera)
        self.assertEqual(self.scene.frame_current, 7)
        self.assertAlmostEqual(self.scene.frame_subframe, .25)
        self.assertEqual(before, self.snapshot())

    def test_failure_after_completed_edits_restores_existing_mesh_and_selection(self):
        ob = self.model("Untouched")
        sibling = ob.copy(); sibling.name = "UntouchedSibling"; self.scene.collection.objects.link(sibling)
        mesh = ob.data
        self.run_op("camera", {"name": "OldCamera", "target": ob.name, "preset": "hero"})
        old_camera = self.scene.camera
        ob.select_set(True); bpy.context.view_layer.objects.active = ob
        state = self.snapshot()
        materials = list(mesh.materials)
        indices = [face.material_index for face in mesh.polygons]
        calls = {
            "material": {"object": ob.name, "preset": "stone"},
            "rig": {"object": ob.name, "name": "FailedRig", "segments": 6},
            "scatter": {"source": ob.name, "name": "FailedScatter", "count": 4},
            "terrain": {"name": "FailedTerrain"},
            "camera": {"name": "FailedCamera", "target": ob.name, "preset": "hero"},
        }
        for suffix, payload in calls.items():
            operation = "studio.create."+suffix
            handler = Ops._HANDLERS[operation]
            def complete_then_fail(tx, scene, clean, handler=handler):
                handler(tx, scene, clean)
                raise RuntimeError("failure after completed mutation")
            with patch.dict(Ops._HANDLERS, {operation: complete_then_fail}):
                with self.assertRaisesRegex(RuntimeError, "completed mutation"):
                    self.run_op(suffix, payload)
            self.assertEqual(state, self.snapshot(), suffix)
            self.assertEqual(ob.data, mesh)
            self.assertEqual(sibling.data, mesh)
            self.assertEqual(list(mesh.materials), materials)
            self.assertEqual([face.material_index for face in mesh.polygons], indices)
            self.assertEqual(len(ob.vertex_groups), 0)
            self.assertEqual(len(ob.modifiers), 0)
            self.assertEqual(self.scene.camera, old_camera)
            self.assertEqual(bpy.context.view_layer.objects.active, ob)
            self.assertEqual(bpy.context.mode, "OBJECT")
            self.assertTrue(ob.select_get())

    def test_native_geometry_survives_blend_save_reopen(self):
        ob = self.model("SavedAsset", "tree")
        self.run_op("scatter", {"name": "SavedInstances", "source": ob.name, "count": 9})
        self.run_op("motion", {"object": ob.name, "preset": "float"})
        self.run_op("camera", {"target": ob.name, "preset": "hero", "name": "SavedCamera"})
        path = str(Path(self.temporary.name)/"creator-native.blend")
        bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
        bpy.ops.wm.open_mainfile(filepath=path)
        scene = bpy.context.scene
        self.assertEqual(scene.camera.name, "SavedCamera")
        self.assertEqual(scene.objects["SavedInstances"].modifiers[0].node_group.bl_idname, "GeometryNodeTree")
        scene.frame_set(31)
        self.assertGreater(scene.objects["SavedAsset"].location.z, .95)
        instances = [x for x in bpy.context.evaluated_depsgraph_get().object_instances
                     if x.is_instance and x.parent.original == scene.objects["SavedInstances"]]
        self.assertEqual(len(instances), 9)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativeCreatorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Real native creator suite failed")
    print("CREATOR_NATIVE_PASS", bpy.app.version_string, "tests=", result.testsRun)
