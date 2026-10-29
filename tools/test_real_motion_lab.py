# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender evaluated-IK, foot-contact, rollback and adversarial motion tests."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import bpy
from mathutils import Vector
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "full-app/scripts"))
import render_motion_lab as M


class MotionLabTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene

    def run_op(self, suffix, payload):
        return M.execute("studio.motion."+suffix, payload, Path("/tmp"), self.scene)

    def make(self, name="Actor", **kwargs):
        return self.run_op("rig.create", {"name": name, **kwargs})

    def clip(self, name="Actor", preset="walk", **kwargs):
        return self.run_op("clip.create", {"rig": name, "preset": preset, **kwargs})

    def ids(self):
        return {kind: {x.as_pointer() for x in getattr(bpy.data, kind)}
                for kind in ("objects", "meshes", "armatures", "materials", "actions")}

    def test_native_rig_weights_and_ik_reach(self):
        result = self.make(origin=[3, 2, 1])
        rig = self.scene.objects[result["rig"]]; body = self.scene.objects[result["mesh"]]
        self.assertEqual(len(rig.data.bones), 18)
        self.assertTrue(all(len(v.groups) == 1 and abs(v.groups[0].weight-1) < 1e-7 for v in body.data.vertices))
        self.assertEqual(body.modifiers[0].object, rig)
        self.assertTrue(all(poly.area > 0 for poly in body.data.polygons))
        self.clip()
        for frame in (1, 7, 13, 19, 25, 37, 49):
            self.scene.frame_set(frame); bpy.context.view_layer.update()
            evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            for side in ("L", "R"):
                target = self.scene.objects["Actor_Foot_"+side]
                distance = (evaluated.matrix_world @ evaluated.pose.bones["shin."+side].tail-target.matrix_world.translation).length
                self.assertLess(distance, .001, (frame, side, distance))
                foot = evaluated.pose.bones["foot."+side]
                self.assertLess(abs((foot.tail-foot.head).z), .00001)

    def test_presets_have_evaluated_contact_and_joint_proof(self):
        for preset in ("walk", "idle", "squat"):
            name = "Actor_"+preset
            self.make(name)
            before_range = self.scene.frame_start, self.scene.frame_end
            clip = self.clip(name, preset)
            audit = self.run_op("audit", clip["audit_payload"])
            self.assertEqual(audit["quality_gate"], "PASS", (preset, audit["issues"]))
            self.assertTrue(audit["contact_results"] and audit["joint_results"])
            self.assertGreater(sum(a["keyframes"] for a in clip["actions"]), 100)
            self.assertEqual(before_range, (self.scene.frame_start, self.scene.frame_end))
            self.assertEqual(self.run_op("audit", {"rig": name})["quality_gate"], "PASS")

    def test_walk_preserves_planted_feet_but_deforms_actual_mesh(self):
        self.make(); clip = self.clip()
        rig = self.scene.objects["Actor"]; body = self.scene.objects["Actor_Body"]
        poses = []
        for frame in (1, 13, 25):
            self.scene.frame_set(frame); bpy.context.view_layer.update()
            evaluated = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                poses.append([tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices])
            finally:
                evaluated.to_mesh_clear()
        self.assertNotEqual(poses[0], poses[1])
        self.assertNotEqual(poses[1], poses[2])
        audit = self.run_op("audit", clip["audit_payload"])
        self.assertLess(max(c["max_measured_drift"] for c in audit["contact_results"]), .00001)

    def test_audit_detects_sliding_jump_and_bad_joint_mapping(self):
        self.make(); clip = self.clip(preset="idle")
        target = self.scene.objects["Actor_Foot_L"]
        self.scene.frame_set(20)
        target.location.x += 1
        target.keyframe_insert(data_path="location", frame=20)
        payload = copy.deepcopy(clip["audit_payload"]); payload["max_distance_per_frame"] = .05
        payload["joints"][0]["max_degrees"] = .1
        result = self.run_op("audit", payload)
        self.assertEqual(result["quality_gate"], "FAIL")
        self.assertTrue({"FOOT_SLIDE", "POSE_JUMP", "JOINT_FLEXION"}.issubset({i["kind"] for i in result["issues"]}))
        with self.assertRaisesRegex(ValueError, "PARENT_CHILD"):
            self.run_op("audit", {"rig": "Actor", "joints": [{"parent": "thigh.L", "child": "shin.R"}]})

    def test_audit_restores_frame_and_subframe_and_reports_missing_coverage(self):
        self.make(); self.clip()
        self.scene.frame_set(17, subframe=.25)
        before = self.ids()
        report = self.run_op("audit", {"rig": "Actor", "contacts": [], "joints": [], "step": 5})
        self.assertEqual(report["quality_gate"], "INCOMPLETE")
        self.assertTrue(report["frame_restored"])
        self.assertEqual((self.scene.frame_current, self.scene.frame_subframe), (17, .25))
        self.assertEqual(self.ids(), before)

    def test_overwrite_and_structural_edits_are_rejected_without_writes(self):
        self.make(); self.clip()
        before = self.ids()
        with self.assertRaisesRegex(ValueError, "EXISTING_ANIMATION"):
            self.clip(preset="squat")
        with self.assertRaisesRegex(ValueError, "NAME_EXISTS"):
            self.make()
        self.assertEqual(self.ids(), before)
        self.make("Edited")
        self.scene.objects["Edited_Foot_L"].location.x += .05
        with self.assertRaisesRegex(ValueError, "EDITED"):
            self.clip("Edited")

    def test_partial_clip_failure_restores_pose_and_removes_actions(self):
        self.make()
        before = self.ids()
        rig = self.scene.objects["Actor"]
        pose = {b.name: b.matrix_basis.copy() for b in rig.pose.bones}
        key = M._key
        calls = []
        def fail(owner, path, frame, group):
            key(owner, path, frame, group); calls.append(frame)
            if len(calls) == 9:
                raise RuntimeError("injected native insertion failure")
        with patch.object(M, "_key", fail), self.assertRaisesRegex(RuntimeError, "injected"):
            self.clip()
        self.assertEqual(self.ids(), before)
        self.assertIsNone(rig.animation_data)
        self.assertNotIn("motion_clip", rig)
        for bone in rig.pose.bones:
            self.assertEqual(bone.matrix_basis, pose[bone.name])
        self.assertEqual(self.clip()["preset"], "walk")

    def test_euler_pose_rest_roll_and_solver_edits_are_preserved(self):
        for index, change in enumerate(("euler", "stretch", "space", "roll")):
            name = "Edited"+str(index)
            self.make(name)
            rig = self.scene.objects[name]
            if change == "euler":
                bone = rig.pose.bones["upper_arm.L"]
                bone.rotation_mode = "XYZ"; bone.rotation_euler.x = .3
            elif change == "stretch":
                rig.pose.bones["shin.L"].constraints[0].use_stretch = True
            elif change == "space":
                rig.pose.bones["foot.L"].constraints[0].owner_space = "LOCAL"
            else:
                bpy.context.view_layer.objects.active = rig; rig.select_set(True)
                bpy.ops.object.mode_set(mode="EDIT")
                rig.data.edit_bones["upper_arm.L"].roll += .2
                bpy.ops.object.mode_set(mode="OBJECT")
            before = self.ids()
            with self.assertRaisesRegex(ValueError, "EDITED"):
                self.clip(name)
            self.assertEqual(self.ids(), before)
            if change == "euler":
                self.assertAlmostEqual(rig.pose.bones["upper_arm.L"].rotation_euler.x, .3)

    def test_partial_rig_failure_rolls_back_created_data(self):
        before = self.ids()
        with patch.object(M, "_simple_material", side_effect=RuntimeError("injected material failure")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.make()
        self.assertEqual(self.ids(), before)

    def test_extreme_admitted_stride_and_cycles_remain_reachable(self):
        self.make(height=.5)
        clip = self.clip(stride=.6, cycles=4, end=97)
        result = self.run_op("audit", clip["audit_payload"])
        self.assertEqual(result["quality_gate"], "PASS", result["issues"])
        rig = self.scene.objects["Actor"]
        for frame in range(1, 98):
            self.scene.frame_set(frame); bpy.context.view_layer.update()
            evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            for side in ("L", "R"):
                foot = self.scene.objects["Actor_Foot_"+side]
                self.assertLess((evaluated.matrix_world @ evaluated.pose.bones["shin."+side].tail-foot.matrix_world.translation).length, .001)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MotionLabTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Motion Lab native semantic tests failed")
