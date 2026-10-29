# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender queue execution for every documented local recipe.

Run in an isolated factory-startup Blender process, never in an owner's file:
blender --factory-startup -b --python-exit-code 1 --python tools/test_real_command_recipes.py
"""
import math
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_command_contract as Contract
import render_command_planner as Planner
import render_unified_queue as Queue
import render_unified_workspace as Studio


class RealCommandRecipeTests(unittest.TestCase):
    def _fixture(self, folder):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        spool = Path(folder) / "Agent"
        spool.mkdir(exist_ok=True)
        os.environ["RENDER_AGENT_SPOOL"] = str(spool)
        scene = bpy.context.scene
        mesh = bpy.data.meshes.new("PreservedMesh")
        mesh.from_pydata([(30, 0, 0), (31, 0, 0), (30, 1, 0)], [], [(0, 1, 2)])
        mesh.update()
        sentinel = bpy.data.objects.new("PreservedObject", mesh)
        scene.collection.objects.link(sentinel)
        return scene, Path(folder) / "Production", sentinel

    def _assert_native_steps(self, preview, scene):
        for step in preview["steps"]:
            operation, p = step["operation"], step["payload"]
            if operation in ("studio.create.model", "studio.create.terrain"):
                ob = scene.objects[p["name"]]
                self.assertEqual(ob.type, "MESH")
                self.assertGreater(len(ob.data.vertices), 4)
                self.assertGreater(len(ob.data.polygons), 0)
                self.assertTrue(all(math.isfinite(x) for v in ob.data.vertices for x in v.co))
                if operation == "studio.create.terrain":
                    self.assertEqual(len(ob.data.vertices), (p["resolution"] + 1) ** 2)
            elif operation == "studio.create.material":
                ob = scene.objects[p["object"]]
                self.assertGreater(len(ob.data.materials), 0)
                mat = ob.data.materials[0]
                self.assertTrue(mat.use_nodes)
                self.assertTrue(any(n.type == "BSDF_PRINCIPLED" for n in mat.node_tree.nodes))
            elif operation == "studio.create.scatter":
                ob = scene.objects[p["name"]]
                self.assertEqual(len(ob.data.vertices), p["count"])
                self.assertTrue(any(mod.type == "NODES" and mod.node_group is not None
                                    for mod in ob.modifiers))
                depsgraph = bpy.context.evaluated_depsgraph_get()
                evaluated_instances = [item for item in depsgraph.object_instances
                                       if item.is_instance and item.parent is not None
                                       and item.parent.original == ob]
                self.assertEqual(len(evaluated_instances), p["count"])
            elif operation == "studio.create.motion":
                ob = scene.objects[p["object"]]
                self.assertIsNotNone(ob.animation_data)
                self.assertIsNotNone(ob.animation_data.action)
                action = ob.animation_data.action
                legacy = getattr(action, "fcurves", None)
                if legacy is not None:
                    curves = list(legacy)
                else:
                    # Independent inspection of Blender's layered action data;
                    # do not ask the implementation under test to verify itself.
                    curves = [curve for layer in action.layers for strip in layer.strips
                              for bag in getattr(strip, "channelbags", ()) for curve in bag.fcurves]
                self.assertGreater(sum(len(curve.keyframe_points) for curve in curves), 1)
                self.assertLessEqual(sum(len(curve.keyframe_points) for curve in curves),
                                     preview["estimated_complexity"]["keyframes_upper_bound"])
                self.assertTrue(any(abs(curve.evaluate(1) - curve.evaluate(60)) > .0001
                                    for curve in curves))
            elif operation == "studio.create.camera":
                self.assertEqual(scene.camera.name, p["name"])
                self.assertEqual(scene.camera.type, "CAMERA")
            elif operation == "studio.create.rig":
                arm = scene.objects[p["name"]]
                ob = scene.objects[p["object"]]
                self.assertEqual(arm.type, "ARMATURE")
                self.assertEqual(len(arm.data.bones), p["segments"])
                self.assertEqual(len(ob.vertex_groups), p["segments"])
                self.assertTrue(any(mod.type == "ARMATURE" and mod.object == arm
                                    for mod in ob.modifiers))
                bpy.context.view_layer.update()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                before = [v.co.copy() for v in ob.evaluated_get(depsgraph).data.vertices]
                arm.pose.bones[-1].rotation_mode = "XYZ"
                arm.pose.bones[-1].rotation_euler.x = .35
                bpy.context.view_layer.update()
                after = [v.co.copy() for v in ob.evaluated_get(depsgraph).data.vertices]
                self.assertTrue(any((a-b).length > .00001 for a, b in zip(before, after)))

    def _run_recipe(self, brief, name, quality="draft"):
        with tempfile.TemporaryDirectory(prefix="render-command-native-") as folder:
            scene, root, sentinel = self._fixture(folder)
            sentinel_vertices = [tuple(v.co) for v in sentinel.data.vertices]
            request = {"brief": brief, "name": name, "quality": quality, "seed": 103}
            preview = Planner.execute("studio.command.preview", request, root, scene)
            self.assertTrue(preview["ready_to_submit"], preview["preflight"])
            self.assertEqual(len(scene.objects), 1)
            self.assertFalse(root.exists())
            accepted = Planner.execute("studio.command.submit",
                dict(request, preview_sha256=preview["preview_sha256"]), root, scene)
            self.assertEqual(accepted["state"], "queued")
            self.assertEqual(accepted["completed_steps"], 0)
            self.assertEqual(len(scene.objects), 1)
            for index in range(preview["total_steps"]):
                result = Queue.tick(root, Studio._execute_step)
                state = Queue.get(root, accepted["plan_id"])
                self.assertEqual(result["result"], "succeeded", (result, state))
                self.assertEqual(state["completed_steps"], index + 1)
            finished = Queue.get(root, accepted["plan_id"])
            self.assertEqual(finished["state"], "completed")
            self.assertTrue(all(receipt["state"] == "succeeded" for receipt in finished["results"]))
            self.assertEqual(len(scene.objects), 1 + preview["estimated_complexity"]["created_objects"])
            self.assertEqual([tuple(v.co) for v in sentinel.data.vertices], sentinel_vertices)
            self.assertIsNone(sentinel.animation_data)
            self.assertEqual(len(sentinel.data.materials), 0)
            self.assertFalse(sentinel.hide_get())
            self._assert_native_steps(preview, scene)
            # Retries report the actual completed queue record, adding no objects.
            retry = Planner.execute("studio.command.submit",
                dict(request, preview_sha256=preview["preview_sha256"]), root, scene)
            self.assertTrue(retry["idempotent"])
            self.assertEqual(retry["state"], "completed")
            self.assertEqual(retry["plan_id"], accepted["plan_id"])
            # Release Blender's current checkpoint file before deleting the fixture.
            bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_every_documented_recipe_has_real_queued_geometry(self):
        for row in Contract.catalog()["recipes"]:
            with self.subTest(recipe=row["id"]):
                self._run_recipe(row["brief"], "Native_" + row["id"])

    def test_highest_quality_forest_uses_180_real_instances(self):
        self._run_recipe("forest environment", "Native_DetailForest", "detail")

    def test_scene_reopen_and_runtime_reload_invalidate_unsubmitted_review(self):
        with tempfile.TemporaryDirectory(prefix="render-command-reopen-") as folder:
            scene, root, sentinel = self._fixture(folder)
            request = {"brief": "crate", "name": "Native_Reopen"}
            old = Planner.preview(request, root, scene)
            scene, root, sentinel = self._fixture(folder)
            fresh = Planner.preview(request, root, scene)
            self.assertEqual(old["preflight"]["scene_guard"]["scene"],
                             fresh["preflight"]["scene_guard"]["scene"])
            self.assertEqual(old["preflight"]["scene_guard"]["scene_objects_sha256"],
                             fresh["preflight"]["scene_guard"]["scene_objects_sha256"])
            self.assertNotEqual(old["preview_sha256"], fresh["preview_sha256"])
            with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
                Planner.submit(dict(request, preview_sha256=old["preview_sha256"]), root, scene)
            importlib.reload(Planner)
            with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
                Planner.submit(dict(request, preview_sha256=fresh["preview_sha256"]), root, scene)
            self.assertFalse(root.exists())
            bpy.ops.wm.read_factory_settings(use_empty=True)

    def test_existing_collection_reserves_generated_object_name(self):
        with tempfile.TemporaryDirectory(prefix="render-command-collection-") as folder:
            scene, root, sentinel = self._fixture(folder)
            request = {"brief": "crate", "name": "Native_Collection"}
            old = Planner.preview(request, root, scene)
            reserved = old["preflight"]["objects_to_create"][0]
            collection = bpy.data.collections.new(reserved)
            reviewed = Planner.preview(request, root, scene)
            self.assertFalse(reviewed["ready_to_submit"])
            self.assertEqual(reviewed["preflight"]["collection_collisions"], [reserved])
            with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
                Planner.submit(dict(request, preview_sha256=old["preview_sha256"]), root, scene)
            with self.assertRaisesRegex(ValueError, "PREFLIGHT_BLOCKED.*COLLECTION_NAME_COLLISION"):
                Planner.submit(dict(request, preview_sha256=reviewed["preview_sha256"]), root, scene)
            self.assertFalse(root.exists())
            self.assertIsNotNone(bpy.data.collections.get(collection.name))
            self.assertEqual(len(scene.objects), 1)
            bpy.ops.wm.read_factory_settings(use_empty=True)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RealCommandRecipeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
