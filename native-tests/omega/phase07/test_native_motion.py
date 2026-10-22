# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual bpy acceptance fixture for Phase 07 (not mocks).

Run at repository root:
    blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase07/test_native_motion.py

Creates an independent two-leg FK armature and two physical Blender cameras,
checks action curves/NLA/world contact, saves .blend, reopens, retimes and checks
that no render quality or motion keys were touched by the retime operation.
"""
import importlib.util
import math
from pathlib import Path
import tempfile

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "omega_phase07_motion", ROOT / "full-app/scripts/omega/phase07_motion.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def create_rig(scene):
    arm = bpy.data.armatures.new("OMEGA07_TestArmature")
    rig = bpy.data.objects.new("OMEGA07_TestRig", arm)
    scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    specs = (
        ("Root", None, (0, 0, .89), (0, 0, 1.10)),
        ("LeftThigh", "Root", (-.18, 0, 1.0), (-.18, 0, .5)),
        ("LeftShin", "LeftThigh", (-.18, 0, .5), (-.18, 0, 0)),
        ("RightThigh", "Root", (.18, 0, 1.0), (.18, 0, .5)),
        ("RightShin", "RightThigh", (.18, 0, .5), (.18, 0, 0)),
    )
    for name, parent, head, tail in specs:
        bone = arm.edit_bones.new(name)
        bone.head, bone.tail, bone.roll = head, tail, 0.
        if parent:
            bone.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
    rig["omega_motion_channels"] = __import__("json").dumps(M._DEFAULT_BONES)
    return rig


def create_camera(scene, name, position):
    camera = bpy.data.objects.new(name, bpy.data.cameras.new(name + "Data"))
    scene.collection.objects.link(camera)
    camera.location = position
    direction = Vector((0, 0, .7)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 3.5
    return camera


def visible(scene, rig, camera, bone_name):
    tip = rig.matrix_world @ rig.pose.bones[bone_name].tail
    image_xy = world_to_camera_view(scene, camera, tip)
    assert all(math.isfinite(float(v)) for v in image_xy)
    return (float(image_xy.x), float(image_xy.y))


def run():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 24000
    scene.render.fps_base = 1001.0
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    before_quality = (scene.render.fps, scene.render.fps_base,
                      scene.render.resolution_x, scene.render.resolution_y,
                      scene.render.resolution_percentage, scene.render.engine)
    rig = create_rig(scene)
    front = create_camera(scene, "OMEGA07_Front", (0, -5, 1.8))
    side = create_camera(scene, "OMEGA07_Side", (5, 0, 1.8))
    bpy.ops.mesh.primitive_cube_add(location=(2, 0, 0))
    sentinel = bpy.context.object
    sentinel.name = "OMEGA07_UnchangedSceneObject"
    original_location = tuple(sentinel.location)
    request = {"rig": rig.name, "clip": "WalkCycle", "frames": 25,
               "stride": .36, "clearance": .075, "contact_z": .12,
               "start": 1, "retime_scale": 1.0}
    context = {"scene": scene, "job_id": "0123456789abcdef0123456789abcdef",
               "dry_run": False, "cancellation_requested": False}
    created = M.execute("omega.motion.create_actions", request, context)
    assert created["state"] == "succeeded" and created["native_execution_verified"], created
    assert len(bpy.data.actions) >= 1 and created["fcurve_count"] == 5, created
    audited = M.execute("omega.motion.audit", {"rig": rig.name, "clip": "WalkCycle"}, context)
    assert audited["fcurve_count"] == 5, audited
    assert audited["keyframes"] == 125, audited
    assert abs(audited["root_motion"]["stride"] - .36) < 1e-5, audited
    assert audited["loop_seam_rotation_error_radians"] < 1e-5, audited
    assert audited["contact"]["max_planted_drift"] < .035, audited
    assert audited["contact"]["max_penetration"] < .025, audited
    assert tuple(rig.location) == (0, 0, 0), "Must animate root pose, not world object position"
    original_hash = audited["fcurve_hash"]
    assert (scene.render.fps, scene.render.fps_base, scene.render.resolution_x,
            scene.render.resolution_y, scene.render.resolution_percentage,
            scene.render.engine) == before_quality

    # Both projections must come from actual evaluated 3D native bone positions.
    scene.frame_set(1)
    fleft = visible(scene, rig, front, "LeftShin")
    fright = visible(scene, rig, front, "RightShin")
    sleft = visible(scene, rig, side, "LeftShin")
    assert abs(fleft[0] - fright[0]) > .05, (fleft, fright)
    scene.frame_set(13)
    sleft2 = visible(scene, rig, side, "LeftShin")
    assert math.dist(sleft, sleft2) < .4, (sleft, sleft2)

    again = M.execute("omega.motion.create_actions", request, context)
    assert again["already_complete"], again
    assert len(rig.animation_data.nla_tracks) == 1
    collision = dict(request, stride=.25)
    try:
        M.execute("omega.motion.create_actions", collision, context)
        raise AssertionError("Conflicting same clip request should not replace source actions")
    except ValueError as exc:
        assert str(exc) == "CHECKPOINT_CONFLICT", exc

    with tempfile.TemporaryDirectory(prefix="omega07-native-") as temp:
        filename = str(Path(temp) / "phase07_walk.blend")
        bpy.ops.wm.save_as_mainfile(filepath=filename, compress=False)
        assert Path(filename).is_file() and Path(filename).stat().st_size > 1024
        bpy.ops.wm.open_mainfile(filepath=filename)
        scene, rig = bpy.context.scene, bpy.data.objects["OMEGA07_TestRig"]
        context["scene"] = scene
        reopened = M.audit("omega.motion.audit", {"rig": rig.name, "clip": "WalkCycle"}, context)
        assert reopened["fcurve_hash"] == original_hash, reopened
        assert reopened["contact"]["max_planted_drift"] < .035, reopened
        assert len(rig.animation_data.nla_tracks) == 1
        assert tuple(bpy.data.objects[sentinel.name].location) == original_location

        retimed = M.execute("omega.motion.create_actions", {
            "kind": "retime", "rig": rig.name, "clip": "WalkCycle", "retime_scale": 1.5}, context)
        assert retimed["keyframes_unchanged"] and retimed["fcurve_hash"] == original_hash
        after_retime = M.audit("omega.motion.audit", {"rig": rig.name, "clip": "WalkCycle"}, context)
        assert after_retime["nla"]["scale"] == 1.5, after_retime
        assert after_retime["fcurve_hash"] == original_hash
        assert after_retime["contact"]["max_planted_drift"] < .035, after_retime
        bpy.ops.wm.save_as_mainfile(filepath=filename, compress=False)
        bpy.ops.wm.open_mainfile(filepath=filename)
        persisted = M.audit("omega.motion.audit", {
            "rig": "OMEGA07_TestRig", "clip": "WalkCycle"}, {"scene": bpy.context.scene})
        assert persisted["fcurve_hash"] == original_hash
        assert persisted["nla"]["scale"] == 1.5
        assert bpy.data.objects["OMEGA07_UnchangedSceneObject"].location == Vector(original_location)

    print("PASS: genuine bpy pose-bone walk, five F-curves/125 keys, native NLA retime")
    print("PASS: planted shin-tip contact metrics, two camera projections and .blend reopen")
    print("NOT CLAIMED: foot mesh contact, photoreal choreography, Android/Vulkan render")


if __name__ == "__main__":
    run()
