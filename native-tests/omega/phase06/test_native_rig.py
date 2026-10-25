# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute with REAL Blender, not host Python:

    blender -b --factory-startup --python-exit-code 1 \\
      --python native-tests/omega/phase06/test_native_rig.py -- --output /tmp/p06

Tests genuine armature, deform, weights, FK bend, IK opt-in and .blend reopen.
"""
import importlib.util
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

BASE = Path(__file__).resolve().parents[3]
MODULE = BASE / "full-app/scripts/omega/phase06_rig.py"
spec = importlib.util.spec_from_file_location("phase06_rig", MODULE)
rig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rig)


def create_mesh(name, offset=0.):
    points = rig.default_landmarks()
    bones, _ = rig._hierarchy(points)
    # Genuine editable native tube meshes, not mock bpy or decorative curves.
    # Separate anatomical regions approximate a simple skinned studio test doll.
    verts, faces = [], []
    for bone_name, start, finish, parent, deform in bones:
        if not deform:
            continue
        a, b = Vector(points[start]), Vector(points[finish])
        d = (b-a).normalized()
        u = d.cross(Vector((0, 1, 0)))
        if u.length < .02:
            u = d.cross(Vector((1, 0, 0)))
        u.normalize()
        v = d.cross(u).normalized()
        width = (.095 if bone_name in ("hips", "spine", "chest") else
                 .085 if bone_name.startswith("thigh") else
                 .06 if bone_name.startswith(("upper_arm", "shin", "neck", "head")) else .04)
        first = len(verts)
        for t in (0., .5, 1.):
            center = a.lerp(b, t)
            for i in range(8):
                ang = i * math.tau / 8
                p = center + width*(u*math.cos(ang)+v*math.sin(ang))
                verts.append(tuple(p))
        for r in range(2):
            for i in range(8):
                faces.append((first+r*8+i, first+r*8+(i+1)%8,
                              first+(r+1)*8+(i+1)%8, first+(r+1)*8+i))
    mesh = bpy.data.meshes.new(name+".Data")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.location.x = offset
    return ob


def sampled_evaluated(ob):
    depgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = ob.evaluated_get(depgraph)
    result = evaluated.to_mesh()
    try:
        assert len(result.vertices) == len(ob.data.vertices)
        return [tuple(ob.matrix_world @ v.co) for v in result.vertices]
    finally:
        evaluated.to_mesh_clear()


def max_delta(before, after):
    return max((Vector(a)-Vector(b)).length for a, b in zip(before, after))


def run(output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    body = create_mesh("OmegaRigTestBody")
    render_before = (scene.render.resolution_x, scene.render.resolution_y,
                     scene.render.resolution_percentage, scene.render.fps,
                     scene.render.fps_base, scene.render.engine)
    context = {"scene": scene, "job_id": "a"*32, "dry_run": False}
    args = {"object_name": body.name}
    preview = rig.execute("omega.rig.bind", args, dict(context, dry_run=True))
    assert preview["state"] == "dry_run" and len(body.modifiers) == 0
    result = rig.execute("omega.rig.bind", args, context)
    report = result["audit"]
    assert result["native_execution_verified"] is True
    assert result["quality_reduced"] is False
    assert result["visual_quality_verified"] is False
    assert report["pass_weights"] and report["max_weight_error"] < .0001
    assert report["unweighted_vertices"] == 0 and report["overweight_vertices"] == 0
    assert report["bone_count"] >= 20
    assert body.modifiers.get("OmegaSkin").type == "ARMATURE"
    assert body.get("omega_rig_name") in scene.objects
    arm = scene.objects[body["omega_rig_name"]]
    assert arm.type == "ARMATURE"
    assert arm.matrix_world == body.matrix_world
    assert len(body.vertex_groups) == len(report["deform_bones"])
    assert json.loads(arm["omega_landmarks_json"])["crown"][2] > 2.
    baseline = sampled_evaluated(body)
    replay = rig.execute("omega.rig.bind", args, context)
    assert replay["already_complete"] and len(scene.objects) == 2
    arm.pose.bones["forearm.L"].rotation_mode = "XYZ"
    arm.pose.bones["forearm.L"].rotation_euler.z = .65
    bpy.context.view_layer.update()
    bent = sampled_evaluated(body)
    deformation = max_delta(baseline, bent)
    assert .015 < deformation < 1.0, deformation
    audited = rig.audit("omega.rig.audit", args, context)
    assert audited["audit"]["moved_vertices"] > 0
    assert audited["audit"]["max_displacement"] > .015
    assert audited["audit"]["pass_weights"]
    assert render_before == (scene.render.resolution_x, scene.render.resolution_y,
                             scene.render.resolution_percentage, scene.render.fps,
                             scene.render.fps_base, scene.render.engine)
    # IK uses a separate synthetic mesh. Moving the controller must move a joint;
    # opt-in preserves FK for production assets that do not request IK.
    ik_body = create_mesh("OmegaIKTestBody", offset=3.)
    ik_args = {"object_name": ik_body.name, "enable_leg_ik": True}
    ik_result = rig.execute("omega.rig.bind", ik_args, context)
    ik_arm = scene.objects[ik_body["omega_rig_name"]]
    for side in ("L", "R"):
        shin = ik_arm.pose.bones["shin."+side]
        constraint = next(c for c in shin.constraints if c.type == "IK")
        assert constraint.target == ik_arm and constraint.chain_count == 2
        assert constraint.pole_target == ik_arm and constraint.pole_subtarget == "pole_knee."+side
        assert not ik_arm.data.bones["ik_foot."+side].use_deform
    ik_before = sampled_evaluated(ik_body)
    ik_arm.pose.bones["ik_foot.L"].location.y -= .10
    bpy.context.view_layer.update()
    ik_after = sampled_evaluated(ik_body)
    ik_delta = max_delta(ik_before, ik_after)
    assert .001 < ik_delta < 1.0, ik_delta
    assert rig.audit("omega.rig.audit", {"object_name": ik_body.name}, context)["audit"]["pass_weights"]
    # Native serialization/recovery: an actual .blend file, not a JSON receipt.
    output.mkdir(parents=True, exist_ok=True)
    path = output / "phase06_weighted_bend.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), check_existing=False)
    assert path.stat().st_size > 10_000
    bpy.ops.wm.open_mainfile(filepath=str(path))
    reopened = bpy.data.objects["OmegaRigTestBody"]
    reopened_arm = bpy.data.objects[reopened["omega_rig_name"]]
    assert abs(reopened_arm.pose.bones["forearm.L"].rotation_euler.z - .65) < 1e-5
    persisted = rig.audit("omega.rig.audit", {"object_name": reopened.name},
                          {"scene": bpy.context.scene})["audit"]
    assert persisted["pass_weights"] and persisted["moved_vertices"] > 0
    receipt = {"blender_version": bpy.app.version_string, "vertices": report["vertex_count"],
               "deform_bones": len(report["deform_bones"]),
               "max_weight_error": report["max_weight_error"],
               "fk_bend_displacement": deformation, "ik_controller_displacement": ik_delta,
               "saved_file": path.name, "saved_bytes": path.stat().st_size,
               "reopen_moved_vertices": persisted["moved_vertices"],
               "quality_settings_untouched": True}
    (output / "phase06_native_receipt.json").write_text(json.dumps(receipt, indent=2))
    print("PHASE06_REAL_BPY_PASS", json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if len(argv) != 2 or argv[0] != "--output":
        raise ValueError("usage: ... -- --output DIRECTORY")
    run(Path(argv[1]).resolve())
