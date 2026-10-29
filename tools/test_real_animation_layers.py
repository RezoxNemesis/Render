# SPDX-License-Identifier: GPL-2.0-or-later
"""Real bpy semantic coverage for layers, parallax projection and mesh morphs."""
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_animation_layers as Ops
import render_creator_ops as Creator


class NativeAnimationLayersTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_op(self,suffix,payload):
        return Ops.execute("studio.animation."+suffix,payload,self.root,self.scene)

    def snapshot(self):
        return {kind:frozenset(x.as_pointer() for x in getattr(bpy.data,kind))
                for kind in ("objects","meshes","materials","actions","cameras","shape_keys")}

    def layer(self,name,**kw):
        result=self.run_op("layer.create",{"name":name,**kw})
        return self.scene.objects[result["object"]]

    def column(self,name="Actor"):
        result=Creator.execute("studio.create.model",{"name":name,"kind":"column","detail":2},self.root,self.scene)
        return self.scene.objects[result["object"]]

    def test_editable_layers_have_uvs_and_flat_native_shader(self):
        payloads=[{"shape":"rectangle"},{"shape":"ellipse"},
                  {"shape":"polygon","points":[[-1,-1],[1,-1],[0,0],[1,1],[-1,1]]},
                  {"shape":"polygon","points":[[-1,-1],[0,-1],[1,-1],[1,1],[-1,1]]}]
        for i,p in enumerate(payloads):
            ob=self.layer("Cutout"+str(i),width=6,height=4,depth=i,color=[.8,.2,.1],**p)
            self.assertEqual(ob.type,"MESH")
            self.assertFalse(ob.data.validate(verbose=False))
            self.assertAlmostEqual(ob.location.z,i)
            self.assertEqual(len(ob.data.uv_layers),1)
            self.assertEqual(len(ob.data.polygons),1)
            self.assertTrue(all(abs(v.co.z)<1e-7 for v in ob.data.vertices))
            mat=ob.data.materials[0]
            emission=next(n for n in mat.node_tree.nodes if n.type=="EMISSION")
            self.assertAlmostEqual(emission.inputs["Color"].default_value[0],.8)
            ob.data.calc_loop_triangles()
            self.assertGreater(len(ob.data.loop_triangles),0)
            self.assertTrue(all(triangle.area>1e-8 for triangle in ob.data.loop_triangles))

    def test_parallax_is_real_projection_and_preserves_scene_state(self):
        far=self.layer("Far",depth=-4)
        near=self.layer("Near",depth=3)
        near.keyframe_insert(data_path="location",frame=1)
        prior_action=near.animation_data.action
        prior_location=near.location.copy()
        self.scene.frame_set(7,subframe=.25)
        result=self.run_op("parallax.create",{"name":"Shot","layers":["Far","Near"],
                                              "start":1,"end":25,"travel_x":4,"interpolation":"LINEAR"})
        camera=self.scene.objects[result["camera"]]
        self.assertEqual(self.scene.frame_current,7)
        self.assertAlmostEqual(self.scene.frame_subframe,.25)
        self.assertEqual(near.animation_data.action,prior_action)
        self.assertEqual(near.location,prior_location)
        positions=[]
        for frame in (1,25):
            self.scene.frame_set(frame)
            bpy.context.view_layer.update()
            positions.append([world_to_camera_view(self.scene,camera,ob.matrix_world.translation).x
                              for ob in (far,near)])
        displacement=[abs(positions[1][i]-positions[0][i]) for i in range(2)]
        self.assertGreater(displacement[1],displacement[0])
        self.assertGreater(displacement[0],.01)
        self.assertEqual(self.scene.camera,camera)
        self.assertTrue(result["native_camera_keyframes"])

    def test_parallax_rejects_flat_depth_and_behind_camera_without_edits(self):
        self.layer("A"); b=self.layer("B")
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,"DISTINCT_DEPTHS"):
            self.run_op("parallax.create",{"name":"Shot","layers":["A","B"]})
        self.assertEqual(before,self.snapshot())
        b.location.z=30
        with self.assertRaisesRegex(ValueError,"IN_FRONT"):
            self.run_op("parallax.create",{"name":"Shot","layers":["A","B"]})
        self.assertEqual(before,self.snapshot())

    def test_every_morph_changes_evaluated_geometry_and_preserves_original(self):
        for i,preset in enumerate(("breathe","twist","wave")):
            ob=self.column("Actor"+str(i))
            original=ob.data
            before=[v.co.copy() for v in original.vertices]
            ob.keyframe_insert(data_path="location",frame=1)
            transform_action=ob.animation_data.action
            result=self.run_op("morph.create",{"object":ob.name,"name":"Motion", "preset":preset,
                                              "start":1,"end":25,"amount":.2,"loop":True})
            self.assertNotEqual(ob.data,original)
            self.assertIsNone(original.shape_keys)
            self.assertTrue(original.use_fake_user)
            self.assertEqual([v.co.copy() for v in original.vertices],before)
            self.assertEqual(ob.animation_data.action,transform_action)
            self.assertEqual(len(ob.data.shape_keys.key_blocks),2)
            self.assertGreater(result["max_local_displacement"],1e-6)
            evaluated=[]
            for frame in (1,13,25,37):
                self.scene.frame_set(frame)
                bpy.context.view_layer.update()
                native=ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
                mesh=native.to_mesh()
                evaluated.append([v.co.copy() for v in mesh.vertices])
                native.to_mesh_clear()
            self.assertLess(max((a-b).length for a,b in zip(evaluated[0],evaluated[2])),1e-5)
            self.assertGreater(max((a-b).length for a,b in zip(evaluated[0],evaluated[1])),1e-5)
            self.assertLess(max((a-b).length for a,b in zip(evaluated[1],evaluated[3])),1e-5)

    def test_shape_keys_and_shared_mesh_users_are_preserved(self):
        ob=self.column()
        other=bpy.data.objects.new("LinkedActor",ob.data)
        self.scene.collection.objects.link(other)
        original=other.data
        self.run_op("morph.create",{"object":ob.name,"name":"Breath"})
        self.assertEqual(other.data,original)
        self.assertIsNone(other.data.shape_keys)
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,"EXISTING_SHAPE_KEYS"):
            self.run_op("morph.create",{"object":ob.name,"name":"Other"})
        self.assertEqual(before,self.snapshot())

    def test_failed_native_key_edit_rolls_back_created_mesh_keys_and_actions(self):
        ob=self.column()
        original=ob.data
        fake_user=original.use_fake_user
        before=self.snapshot()
        with patch.object(Ops,"_curves",side_effect=RuntimeError("INJECTED")):
            with self.assertRaisesRegex(RuntimeError,"INJECTED"):
                self.run_op("morph.create",{"object":ob.name,"name":"Breath"})
        self.assertEqual(ob.data,original)
        self.assertEqual(original.use_fake_user,fake_user)
        self.assertIsNone(ob.data.shape_keys)
        # Fail after native keys exist; rollback must clean their action and key datablocks.
        self.assertEqual(before,self.snapshot())

    def test_failed_camera_animation_rolls_back_native_ids(self):
        self.layer("Far",depth=-2); self.layer("Near",depth=2)
        before=self.snapshot()
        camera=self.scene.camera
        with patch.object(Ops,"_curves",side_effect=RuntimeError("INJECTED")):
            with self.assertRaisesRegex(RuntimeError,"INJECTED"):
                self.run_op("parallax.create",{"name":"Camera","layers":["Far","Near"]})
        self.assertEqual(before,self.snapshot())
        self.assertEqual(self.scene.camera,camera)

    def test_existing_name_and_invalid_polygon_do_not_create_ids(self):
        self.layer("Existing")
        before=self.snapshot()
        with self.assertRaises(ValueError):
            self.layer("Existing")
        with self.assertRaises(ValueError):
            self.layer("BowTie",shape="polygon",points=[[-1,-1],[1,1],[-1,1],[1,-1]])
        self.assertEqual(before,self.snapshot())


if __name__=="__main__":
    unittest.main(argv=[sys.argv[0]])
