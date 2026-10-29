# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender render-profile and whole-action animation semantics."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "full-app/scripts"))
import render_animation_finish as F
import render_execution_settings as Settings


class NativeFinishTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.scene.render.engine = "CYCLES"
        self.scene.render.resolution_percentage = 100
        self.scene.render.resolution_x = 1280
        self.scene.render.resolution_y = 720
        self.scene.render.fps = 24
        self.scene.render.fps_base = 1
        camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("CameraData"))
        self.scene.collection.objects.link(camera)
        self.scene.camera = camera

    def run_op(self, operation, payload=None):
        return F.execute(operation, payload or {}, Path(tempfile.gettempdir()), self.scene)

    def animated(self, name="Actor"):
        obj = bpy.data.objects.new(name, None)
        self.scene.collection.objects.link(obj)
        for frame, value in ((1, 0), (11, 2), (21, -1)):
            obj.location.x = value
            obj.keyframe_insert("location", index=0, frame=frame)
        return obj, obj.animation_data.action

    def token(self, action):
        return self.run_op("studio.keyframes.inspect", {"action": action.name})["revision_sha256"]

    def retime(self, action, **overrides):
        return self.run_op("studio.keyframes.retime", {"action": action.name,
                           "expected_sha256": self.token(action), "scale": 2, **overrides})

    def test_preflight_is_read_only_and_reports_camera_and_cost(self):
        before = Settings.inspect(self.scene)
        result = self.run_op("studio.finish.inspect")
        self.assertTrue(result["ready"], result["blockers"])
        self.assertEqual(result["cost"]["total_pixel_frames"], 1280 * 720 * 250)
        self.assertEqual(before, Settings.inspect(self.scene))
        self.scene.camera = None
        self.assertIn("CAMERA_REQUIRED", [p["code"] for p in self.run_op("studio.finish.inspect")["blockers"]])

    def test_missing_and_unpacked_image_blocks_real_durable_queue(self):
        mesh = bpy.data.meshes.new("Mesh")
        mesh.from_pydata([(0,0,0), (1,0,0), (0,1,0)], [], [(0,1,2)])
        obj = bpy.data.objects.new("Mesh", mesh); self.scene.collection.objects.link(obj)
        material = bpy.data.materials.new("Material"); material.use_nodes = True
        mesh.materials.append(material)
        image = bpy.data.images.new("MissingReference", width=8, height=8)
        image.source = "FILE"; image.filepath = "/no-such-render-test-image.png"
        material.node_tree.nodes.new("ShaderNodeTexImage").image = image
        result = self.run_op("studio.finish.inspect")
        self.assertFalse(result["ready"])
        self.assertIn("MISSING_IMAGE", [p["code"] for p in result["blockers"]])
        self.assertIn("PACK_EXTERNAL_IMAGES", [p["code"] for p in result["blockers"]])
        self.assertEqual(result["unpacked_external_images"], ["MissingReference"])

    def test_preset_applies_actual_settings_and_overrides_stale_selected_profile(self):
        Settings.profiles(self.scene, {"profile": "final", "settings": {
            "width": 1920, "height": 1080, "percentage": 50, "fps": 60, "samples": 512}}, True)
        self.scene.frame_start, self.scene.frame_end = 10, 120
        result = self.run_op("studio.finish.preset", {"preset": "draft", "start": 25, "end": 72})
        self.assertEqual((self.scene.render.resolution_x, self.scene.render.resolution_y), (854, 480))
        self.assertEqual(self.scene.cycles.samples, 16)
        self.assertEqual((self.scene.frame_start, self.scene.frame_end), (25, 72))
        plan, profile, overrides = Settings.profile_plan(self.scene, {"profile": "final"})
        self.assertEqual((plan["width"], plan["height"], plan["fps"], plan["samples"]), (854, 480, 24, 16))
        self.assertEqual(result["updated_profile"], "final")
        self.assertFalse(result["render_started"])

    def test_failed_preset_restores_settings_profile_and_timeline(self):
        Settings.profiles(self.scene, {"profile": "final", "settings": {"samples": 23}}, True)
        before = Settings.inspect(self.scene)
        profile = self.scene["render_studio_profiles_v1"]
        frames = (self.scene.frame_start, self.scene.frame_end, self.scene.frame_step)
        preflight = F.inspect(self.scene)
        with patch.object(F, "inspect", side_effect=[preflight, RuntimeError("forced after configuration")]):
            with self.assertRaisesRegex(RuntimeError, "forced"):
                self.run_op("studio.finish.preset", {"preset": "draft", "fps": 30, "start": 20, "end": 40})
        self.assertEqual(before, Settings.inspect(self.scene))
        self.assertEqual(profile, self.scene["render_studio_profiles_v1"])
        self.assertEqual(frames, (self.scene.frame_start, self.scene.frame_end, self.scene.frame_step))

    def test_affine_retime_preserves_actual_evaluated_bezier_animation(self):
        obj, action = self.animated()
        curve = F._curves(action)[0][1]
        for key in curve.keyframe_points:
            key.handle_left_type = "FREE"; key.handle_right_type = "FREE"
            key.handle_left = (key.co.x - 2, key.co.y - .3)
            key.handle_right = (key.co.x + 2, key.co.y + .3)
        curve.update()
        samples = [(frame, curve.evaluate(frame)) for frame in (1, 2.5, 5, 9.5, 11, 17, 20.5, 21)]
        before_frames = (self.scene.frame_start, self.scene.frame_end)
        result = self.retime(action, scale=1.5, offset=7, pivot=1)
        for frame, value in samples:
            self.assertAlmostEqual(curve.evaluate(1 + (frame - 1) * 1.5 + 7), value, places=4)
        self.assertEqual(result["frame_range_after"], [8., 38.])
        self.assertEqual(before_frames, (self.scene.frame_start, self.scene.frame_end))
        self.assertEqual(curve.keyframe_points[0].handle_left_type, "FREE")

    def test_stale_out_of_range_and_shared_edits_do_not_mutate(self):
        obj, action = self.animated()
        token = self.token(action)
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            self.retime(action, expected_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "OUT_OF_RANGE"):
            self.retime(action, offset=-10)
        other = bpy.data.objects.new("Other", None); self.scene.collection.objects.link(other)
        other.animation_data_create(); other.animation_data.action = action
        if hasattr(other.animation_data, "action_slot"):
            other.animation_data.action_slot = obj.animation_data.action_slot
        with self.assertRaisesRegex(ValueError, "SHARED_ACTION"):
            self.retime(action)
        self.assertEqual(token, self.token(action))
        self.retime(action, allow_shared_action=True)

    def test_nla_and_time_dependent_modifiers_block_but_plain_cycles_work(self):
        obj, action = self.animated()
        curve = F._curves(action)[0][1]
        modifier = curve.modifiers.new("NOISE")
        with self.assertRaisesRegex(ValueError, "TIME_DEPENDENT_MODIFIER"):
            self.retime(action)
        curve.modifiers.remove(modifier)
        curve.modifiers.new("CYCLES")
        self.retime(action)
        obj.animation_data.nla_tracks.new().strips.new("Nla", 1, action)
        with self.assertRaisesRegex(ValueError, "ACTION_USED_IN_NLA"):
            self.retime(action, allow_shared_action=True)

    def test_retime_failure_restores_original_curve_data(self):
        obj, action = self.animated()
        before = F._keyframes_inspect({"action": action.name})
        payload = {"action": action.name, "expected_sha256": before["revision_sha256"], "scale": 2}
        with patch.object(F, "_keyframes_inspect", side_effect=[before, RuntimeError("forced after retime")]):
            with self.assertRaisesRegex(RuntimeError, "forced"):
                self.run_op("studio.keyframes.retime", payload)
        self.assertEqual(before["revision_sha256"], self.token(action))

    def test_locked_and_frozen_data_are_preserved(self):
        obj, action = self.animated()
        F._curves(action)[0][1].lock = True
        with self.assertRaisesRegex(ValueError, "LOCKED_CHANNEL"):
            self.retime(action)
        self.scene["production_frozen_job"] = "immutable"
        with self.assertRaisesRegex(ValueError, "IMMUTABLE"):
            self.run_op("studio.finish.preset", {"preset": "draft"})

    def test_revisions_include_modifiers_and_custom_range_cannot_desynchronize(self):
        obj, action = self.animated()
        curve = F._curves(action)[0][1]
        token = self.token(action)
        curve.modifiers.new("CYCLES")
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            self.retime(action, expected_sha256=token)
        action.use_frame_range = True
        with self.assertRaisesRegex(ValueError, "ACTION_CUSTOM_FRAME_RANGE"):
            self.retime(action)

    def test_actual_manual_queue_gate_unsupported_output_and_step(self):
        self.scene.render.engine = "BLENDER_WORKBENCH"
        self.assertIn("ENGINE_UNSUPPORTED", [p["code"] for p in self.run_op("studio.finish.inspect")["blockers"]])
        self.scene.render.engine = "CYCLES"
        self.scene.render.image_settings.file_format = "OPEN_EXR"
        self.assertIn("HDR_OUTPUT_REQUIRES_NATIVE_MENU", [p["code"] for p in self.run_op("studio.finish.inspect")["blockers"]])
        self.scene.render.image_settings.file_format = "PNG"
        self.scene.frame_step = 2
        self.assertIn("FRAME_STEP_UNSUPPORTED", [p["code"] for p in self.run_op("studio.finish.inspect")["blockers"]])

    def test_preflight_fps_base_matches_android_encoder_limits(self):
        for fps_base in (.1, 100, 101):
            self.scene.render.fps_base = fps_base
            result = self.run_op("studio.finish.inspect")
            self.assertIn("VIDEO_FPS_UNSUPPORTED", [p["code"] for p in result["blockers"]])
        self.scene.render.fps_base = 1.001
        result = self.run_op("studio.finish.inspect")
        self.assertTrue(result["ready"], result["blockers"])
        self.assertAlmostEqual(result["range"]["duration_seconds"], 250 / (24 / 1.001), places=4)

    def test_motion_lab_owners_require_coordinated_group_retime(self):
        for marker in ("render.motion.lab.v1", "CharacterRig"):
            obj, action = self.animated("MotionOwner")
            obj["render_motion_lab"] = marker
            before = self.run_op("studio.keyframes.inspect", {"action": action.name})
            self.assertIn("MOTION_LAB_GROUP_RETIME_REQUIRED", before["retime_blockers"])
            with self.assertRaisesRegex(ValueError, "FINISH_MOTION_LAB_GROUP_RETIME_REQUIRED"):
                self.retime(action, allow_shared_action=True)
            self.assertEqual(before["revision_sha256"], self.token(action))
            del obj["render_motion_lab"]
            # The restriction is tied to coordinated Motion Lab owners, not
            # generic object animations such as parallax or shape-key actions.
            self.retime(action)
            action["render_motion_lab"] = "CharacterRig"
            with self.assertRaisesRegex(ValueError, "FINISH_MOTION_LAB_GROUP_RETIME_REQUIRED"):
                self.retime(action)

    def test_multiple_action_slots_are_transformed_together(self):
        if bpy.app.version < (4, 4, 0):
            self.skipTest("Layered action slots were introduced in Blender 4.4")
        obj, action = self.animated()
        other = bpy.data.objects.new("OtherSlot", None); self.scene.collection.objects.link(other)
        other.animation_data_create(); other.animation_data.action = action
        other.animation_data.action_slot = action.slots.new(id_type="OBJECT", name="OtherSlot")
        for frame, value in ((2, 10), (12, 14)):
            other.location.y = value; other.keyframe_insert("location", index=1, frame=frame)
        curves = F._curves(action)
        self.assertEqual(len(curves), 2)
        self.retime(action, allow_shared_action=True)
        keyed_frames = sorted(tuple(round(key.co.x, 2) for key in curve.keyframe_points) for _, curve in curves)
        self.assertEqual(keyed_frames, [(2., 22., 42.), (4., 24.)])


if __name__ == "__main__":
    unittest.main(argv=[__file__], verbosity=2)
