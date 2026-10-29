# SPDX-License-Identifier: GPL-2.0-or-later
"""Native articulated mannequin, contact-aware clips and evaluated motion QA.

The mannequin is an editable motion-study asset, not automatic anatomical
reconstruction. All motion is real Blender armature/IK/action data. The audit
uses declared contact intervals and joint mappings instead of guessing intent.
"""
import hashlib
import json
import math

import bpy
from mathutils import Quaternion, Vector
import render_motion_lab_contract as C
from render_creator_ops import _Transaction, _curves, _mesh_object, _simple_material

TAG = "render_motion_lab"


def _rig(scene, name):
    rig = scene.objects.get(name)
    if rig is None or rig.type != "ARMATURE":
        raise ValueError("MOTION_ARMATURE_NOT_FOUND")
    if len(rig.data.bones) > C.MAX_BONES:
        raise ValueError("MOTION_BONE_BUDGET_EXCEEDED")
    return rig


def _spec(height):
    """Z up, -Y forward, +X left. Segment endpoints are in rig-local space."""
    bones = [
        ("root", (0, 0, 0), (0, 0, .07), None, 0),
        ("hips", (0, 0, .53), (0, 0, .63), "root", .09),
        ("spine", (0, 0, .63), (0, 0, .76), "hips", .085),
        ("chest", (0, 0, .76), (0, 0, .84), "spine", .095),
        ("neck", (0, 0, .84), (0, 0, .88), "chest", .032),
        ("head", (0, 0, .88), (0, 0, .98), "neck", .067)]
    for side, sign in (("L", 1), ("R", -1)):
        bones.extend([
            ("upper_arm."+side, (sign*.14, 0, .80), (sign*.27, 0, .64), "chest", .035),
            ("forearm."+side, (sign*.27, 0, .64), (sign*.30, -.015, .49), "upper_arm."+side, .029),
            ("hand."+side, (sign*.30, -.015, .49), (sign*.30, -.02, .43), "forearm."+side, .034),
            ("thigh."+side, (sign*.095, 0, .53), (sign*.095, -.015, .29), "hips", .049),
            ("shin."+side, (sign*.095, -.015, .29), (sign*.095, 0, .035), "thigh."+side, .037),
            # Independent foot orientation keeps soles level while the knee IK
            # solves the leg; native Copy Location anchors its ankle.
            ("foot."+side, (sign*.095, 0, .035), (sign*.095, -.105, .035), "root", .035)])
    return [(name, Vector(a)*height, Vector(b)*height, parent, radius*height)
            for name, a, b, parent, radius in bones]


def _capsule(vertices, faces, a, b, radius):
    axis = (b-a).normalized()
    u = axis.cross(Vector((0, 1, 0)))
    if u.length < .01:
        u = axis.cross(Vector((1, 0, 0)))
    u.normalize(); v = axis.cross(u).normalized()
    # Rounded ends overlap at joints. Each closed component is rigidly weighted
    # to its corresponding bone, like an articulated studio posing mannequin.
    rings = []
    for center, r in ((a-axis*radius*.45, radius*.55), (a, radius),
                      (b, radius*.85), (b+axis*radius*.35, radius*.45)):
        ring = []
        for i in range(12):
            angle = i*math.tau/12
            ring.append(len(vertices))
            vertices.append(tuple(center+(u*math.cos(angle)+v*math.sin(angle))*r))
        rings.append(ring)
    faces.append(tuple(reversed(rings[0])))
    for left, right in zip(rings, rings[1:]):
        for i in range(12):
            j = (i+1) % 12
            faces.append((left[i], left[j], right[j], right[i]))
    faces.append(tuple(rings[-1]))


def _structure(rig, controls):
    data = {"matrix": [list(row) for row in rig.matrix_world],
            "bones": [[b.name, [list(row) for row in b.matrix_local], b.parent.name if b.parent else None,
                       bool(b.use_connect), bool(b.use_inherit_rotation), b.inherit_scale, bool(b.use_local_location)]
                      for b in rig.data.bones],
            "poses": [[b.name, b.rotation_mode, [list(row) for row in b.matrix_basis],
                       float(b.ik_stretch), [[getattr(b, "lock_ik_"+axis), getattr(b, "use_ik_limit_"+axis),
                                             getattr(b, "ik_min_"+axis), getattr(b, "ik_max_"+axis)]
                                            for axis in ("x", "y", "z")],
                       [[c.name, c.type, c.target.name if hasattr(c, "target") and c.target else None,
                         float(c.influence), getattr(c, "chain_count", None),
                         c.pole_target.name if hasattr(c, "pole_target") and c.pole_target else None,
                         getattr(c, "pole_angle", None), getattr(c, "use_stretch", None),
                         getattr(c, "owner_space", None), getattr(c, "target_space", None),
                         bool(c.mute)] for c in b.constraints]] for b in rig.pose.bones],
            "controls": [[ob.name, [list(row) for row in ob.matrix_world]] for ob in controls]}
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _create(tx, scene, p):
    names = [p["name"], p["name"]+"_Body"] + [p["name"]+"_"+part+"_"+side
                for side in ("L", "R") for part in ("Foot", "Knee")]
    if any(n in bpy.data.objects for n in names):
        raise ValueError("MOTION_NAME_EXISTS")
    arm = tx.add("armatures", bpy.data.armatures.new(p["name"]+"_Skeleton"))
    rig = tx.add("objects", bpy.data.objects.new(p["name"], arm))
    scene.collection.objects.link(rig)
    rig.location = p["origin"]; rig.show_in_front = True
    for selected in list(bpy.context.selected_objects):
        selected.select_set(False)
    rig.select_set(True); bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    spec = _spec(p["height"])
    for name, a, b, parent, radius in spec:
        bone = arm.edit_bones.new(name); bone.head = a; bone.tail = b
        bone.use_deform = radius > 0
        if parent:
            bone.parent = arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    controls = []
    for side, sign in (("L", 1), ("R", -1)):
        target = tx.add("objects", bpy.data.objects.new(p["name"]+"_Foot_"+side, None))
        scene.collection.objects.link(target)
        target.location = Vector(p["origin"])+Vector((sign*.095, 0, .035))*p["height"]
        target.empty_display_type = "CUBE"; target.empty_display_size = p["height"]*.045
        target[TAG] = rig.name; target["motion_role"] = "foot."+side
        pole = tx.add("objects", bpy.data.objects.new(p["name"]+"_Knee_"+side, None))
        scene.collection.objects.link(pole); pole.parent = rig
        pole.location = Vector((sign*.095, -.6, .29))*p["height"]
        pole.empty_display_type = "SPHERE"; pole.empty_display_size = p["height"]*.025
        pole[TAG] = rig.name; pole["motion_role"] = "knee."+side
        controls.extend((target, pole))
        ik = rig.pose.bones["shin."+side].constraints.new("IK")
        ik.name = "MotionLab Leg IK"; ik.target = target; ik.pole_target = pole
        ik.chain_count = 2; ik.pole_angle = -math.pi/2; ik.use_stretch = False
        foot = rig.pose.bones["foot."+side].constraints.new("COPY_LOCATION")
        foot.name = "MotionLab Planted Ankle"; foot.target = target
        foot.owner_space = "WORLD"; foot.target_space = "WORLD"
    vertices, faces, groups = [], [], {}
    for name, a, b, parent, radius in spec:
        if not radius:
            continue
        start = len(vertices)
        _capsule(vertices, faces, a, b, radius)
        groups[name] = list(range(start, len(vertices)))
    mesh = _mesh_object(tx, scene, p["name"]+"_Body", vertices, faces)
    mesh.parent = rig
    material = _simple_material(tx, p["name"]+"_Mannequin", (.28, .55, .68), roughness=.48)
    mesh.data.materials.append(material)
    for polygon in mesh.data.polygons:
        polygon.use_smooth = True
    for name, indices in groups.items():
        mesh.vertex_groups.new(name=name).add(indices, 1, "REPLACE")
    modifier = mesh.modifiers.new("MotionLab Armature", "ARMATURE"); modifier.object = rig
    rig[TAG] = C.VERSION; rig["motion_height"] = p["height"]
    rig["motion_controls"] = json.dumps([ob.name for ob in controls])
    rig["motion_mesh"] = mesh.name; mesh[TAG] = rig.name
    bpy.context.view_layer.update()
    rig["motion_structure"] = _structure(rig, controls)
    return {"rig": rig.name, "mesh": mesh.name, "controls": [ob.name for ob in controls],
            "bones": len(arm.bones), "weighted_vertices": len(vertices),
            "bone_map": {side: {"hip": "thigh."+side, "knee": "shin."+side, "foot": "foot."+side}
                         for side in ("L", "R")},
            "rig_scope": "articulated_mannequin", "native_leg_ik": True,
            "continuous_anatomical_skin": False, "production_character_quality_verified": False}


def _key(owner, path, frame, group):
    if not owner.keyframe_insert(data_path=path, frame=frame, group=group):
        raise RuntimeError("MOTION_NATIVE_KEY_INSERT_FAILED")


def _rotate(pb, angle):
    local_axis = pb.bone.matrix_local.to_quaternion().inverted() @ Vector((1, 0, 0))
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion(local_axis, angle)


def _foot_phase(t, stride, height):
    cycle = math.floor(t+1e-9); phase = t-cycle
    if phase < 0:
        phase = 0
    if phase <= .5:
        return -stride*cycle, 0., True
    u = (phase-.5)*2
    smooth = u*u*(3-2*u)
    return -stride*(cycle+smooth), height*.06*math.sin(math.pi*u)**2, False


def _clip(tx, scene, p):
    rig = _rig(scene, p["rig"])
    if rig.get(TAG) != C.VERSION or rig.library is not None or rig.data.library is not None:
        raise ValueError("MOTION_OWNED_MANNEQUIN_REQUIRED")
    control_names = json.loads(rig.get("motion_controls", "[]"))
    if len(control_names) != 4:
        raise ValueError("MOTION_CONTROLS_INVALID")
    controls = [scene.objects.get(name) for name in control_names]
    if any(ob is None or ob.get(TAG) != rig.name or ob.library is not None for ob in controls):
        raise ValueError("MOTION_CONTROLS_INVALID")
    owners = [rig] + controls
    for ob in owners:
        ad = ob.animation_data
        if ad and (ad.action or len(ad.nla_tracks) or len(ad.drivers)):
            raise ValueError("MOTION_EXISTING_ANIMATION_REQUIRES_NEW_RIG")
    bpy.context.view_layer.update()
    if rig.get("motion_structure") != _structure(rig, controls):
        raise ValueError("MOTION_MANNEQUIN_EDITED_REQUIRES_CUSTOM_CLIP")
    height = float(rig["motion_height"])
    origin = rig.location.copy()
    poses = [(pb, pb.matrix_basis.copy(), pb.rotation_mode) for pb in rig.pose.bones]
    transforms = [(ob, ob.matrix_basis.copy(), ob.animation_data is None) for ob in owners]
    old_metadata = rig.get("motion_clip", None)
    actions_before = {action.as_pointer() for action in bpy.data.actions}

    def restore():
        for ob, matrix, no_ad in transforms:
            if ob.animation_data:
                ob.animation_data.action = None
                if no_ad:
                    ob.animation_data_clear()
            ob.matrix_basis = matrix
        for pb, matrix, mode in poses:
            pb.rotation_mode = mode; pb.matrix_basis = matrix
        if old_metadata is None:
            if "motion_clip" in rig:
                del rig["motion_clip"]
        else:
            rig["motion_clip"] = old_metadata
        for action in list(bpy.data.actions):
            if action.as_pointer() not in actions_before and action.users == 0:
                bpy.data.actions.remove(action)
    tx.defer(restore)
    feet = {ob["motion_role"][-1]: ob for ob in controls if ob["motion_role"].startswith("foot.")}
    contacts, current_contact = [], {}
    start, end = p["start"], p["end"]
    duration = end-start
    for frame in range(start, end+1):
        u = (frame-start)/duration; t = u*p["cycles"]
        phase = math.tau*t
        rig.location = origin
        hips = rig.pose.bones["hips"]
        hips.location = (0, 0, 0)
        if p["preset"] == "walk":
            stride = height*p["stride"]
            rig.location.y -= stride*t
            # Keep reach below chain length even for the largest admitted stride.
            leg_vertical = math.sqrt((height*.487)**2-(stride*.5)**2)
            hips.location.y = leg_vertical-height*.495-height*.004*math.sin(phase*2)**2
            arm_angle = .32*math.sin(phase)
        elif p["preset"] == "squat":
            hips.location.y = -height*(.004+.15*math.sin(math.pi*t)**2)
            arm_angle = -.45*math.sin(math.pi*t)**2
        else:
            hips.location.y = -height*(.004+.002*math.sin(phase)**2)
            arm_angle = .025*math.sin(phase)
        _key(rig, "location", frame, "Root travel")
        _key(hips, "location", frame, "Pelvis balance")
        _rotate(rig.pose.bones["spine"], .025*math.sin(phase) if p["preset"] == "idle" else 0.)
        _key(rig.pose.bones["spine"], "rotation_quaternion", frame, "Breathing")
        for side, sign in (("L", 1), ("R", -1)):
            angle = arm_angle*sign if p["preset"] == "walk" else arm_angle
            _rotate(rig.pose.bones["upper_arm."+side], angle)
            _key(rig.pose.bones["upper_arm."+side], "rotation_quaternion", frame, "Arm swing")
            foot = feet[side]
            if p["preset"] == "walk":
                y, lift, contact = _foot_phase(t+(0 if side == "L" else .5), stride, height)
                if side == "R":
                    y += stride*.5
            else:
                y, lift, contact = 0., 0., True
            foot.location = origin+Vector((sign*height*.095, y, height*.035+lift))
            _key(foot, "location", frame, "Planted contact and swing")
            if contact and side not in current_contact:
                current_contact[side] = frame
            if not contact and side in current_contact:
                first = current_contact.pop(side)
                if frame-1 > first:
                    contacts.append({"bone": "foot."+side, "start": first, "end": frame-1,
                                     "max_drift": height*.001})
    for side, first in current_contact.items():
        if end > first:
            contacts.append({"bone": "foot."+side, "start": first, "end": end, "max_drift": height*.001})
    actions = []
    for owner in (rig, feet["L"], feet["R"]):
        action = owner.animation_data.action
        if action is None:
            raise RuntimeError("MOTION_NATIVE_ACTION_MISSING")
        action.name = rig.name+"_"+p["preset"]+"_"+owner.name
        action[TAG] = rig.name
        tx.add("actions", action)
        curves = _curves(action)
        if not curves:
            raise RuntimeError("MOTION_NATIVE_CURVES_MISSING")
        for curve in curves:
            for key in curve.keyframe_points:
                key.interpolation = "LINEAR"
        actions.append({"owner": owner.name, "action": action.name,
                        "fcurves": len(curves), "keyframes": sum(len(c.keyframe_points) for c in curves)})
    joints = [{"parent": "thigh."+s, "child": "shin."+s, "min_degrees": 0., "max_degrees": 155.}
              for s in ("L", "R")]
    audit = {"rig": rig.name, "start": start, "end": end, "step": 1,
             "contacts": contacts, "joints": joints, "max_distance_per_frame": height*.25}
    rig["motion_clip"] = json.dumps(audit, sort_keys=True)
    return {"rig": rig.name, "preset": p["preset"], "actions": actions, "audit_payload": audit,
            "contact_intervals": contacts, "editable_native_keyframes": True,
            "interpolation": "LINEAR", "timeline_range_unchanged": True,
            "scope": "mannequin_motion_study", "perfect_motion_certified": False}


def _audit(scene, p):
    rig = _rig(scene, p["rig"])
    if "contacts" not in p or "joints" not in p:
        stored = rig.get("motion_clip") if rig.get(TAG) == C.VERSION else None
        mapping = json.loads(stored) if isinstance(stored, str) else {}
        for field in ("contacts", "joints"):
            if field not in p:
                source = mapping.get(field, [])
                if field == "contacts":
                    source = [dict(c, start=max(c["start"], p["start"]), end=min(c["end"], p["end"]))
                              for c in source if max(c["start"], p["start"]) < min(c["end"], p["end"])]
                p[field] = source
        p = C.validate("studio.motion.audit", p)
    contacts, joints = p["contacts"], p["joints"]
    for contact in contacts:
        if contact["bone"] not in rig.pose.bones:
            raise ValueError("MOTION_CONTACT_BONE_NOT_FOUND")
    for joint in joints:
        parent = rig.pose.bones.get(joint["parent"]); child = rig.pose.bones.get(joint["child"])
        if parent is None or child is None or child.parent != parent:
            raise ValueError("MOTION_JOINT_REQUIRES_PARENT_CHILD_CHAIN")
    frames = C.sample_frames(p["start"], p["end"], p["step"], contacts)
    old_frame, old_subframe = scene.frame_current, scene.frame_subframe
    samples, issues, issue_count = {}, [], 0

    def issue(kind, **details):
        nonlocal issue_count
        issue_count += 1
        if len(issues) < 256:
            issues.append(dict(kind=kind, **details))
    try:
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            frame_data = {}
            for bone in evaluated.pose.bones:
                head = evaluated.matrix_world @ bone.head
                tail = evaluated.matrix_world @ bone.tail
                if any(not math.isfinite(x) for point in (head, tail) for x in point):
                    raise ValueError("MOTION_NONFINITE_EVALUATED_POSE")
                frame_data[bone.name] = (head.copy(), tail.copy())
            samples[frame] = frame_data
    finally:
        scene.frame_set(old_frame, subframe=old_subframe)
    contact_results = []
    for contact in contacts:
        relevant = [f for f in frames if contact["start"] <= f <= contact["end"]]
        reference = samples[relevant[0]][contact["bone"]][0]
        maximum = 0.; worst_frame = relevant[0]
        for frame in relevant:
            point = samples[frame][contact["bone"]][0]
            drift = math.hypot(point.x-reference.x, point.y-reference.y)
            if drift > maximum:
                maximum, worst_frame = drift, frame
        passed = maximum <= contact["max_drift"]
        contact_results.append(dict(contact, max_measured_drift=maximum, worst_frame=worst_frame,
                                    samples=len(relevant), passed=passed))
        if not passed:
            issue("FOOT_SLIDE", bone=contact["bone"], frame=worst_frame,
                  measured=maximum, allowed=contact["max_drift"])
    joint_results = []
    for joint in joints:
        values = []
        for frame in frames:
            a, b = samples[frame][joint["parent"]], samples[frame][joint["child"]]
            parent, child = a[1]-a[0], b[1]-b[0]
            if min(parent.length, child.length) < 1e-9:
                raise ValueError("MOTION_COLLAPSED_EVALUATED_BONE")
            degrees = math.degrees(parent.angle(child))
            values.append(degrees)
            if degrees < joint["min_degrees"]-.01 or degrees > joint["max_degrees"]+.01:
                issue("JOINT_FLEXION", parent=joint["parent"], child=joint["child"], frame=frame,
                      measured_degrees=degrees, allowed_degrees=[joint["min_degrees"], joint["max_degrees"]])
        joint_results.append(dict(joint, minimum_measured_degrees=min(values), maximum_measured_degrees=max(values),
                                  passed=min(values) >= joint["min_degrees"]-.01 and max(values) <= joint["max_degrees"]+.01))
    max_speed = 0.
    for previous, current in zip(frames, frames[1:]):
        for bone in rig.pose.bones:
            speed = (samples[current][bone.name][0]-samples[previous][bone.name][0]).length/(current-previous)
            max_speed = max(max_speed, speed)
            if speed > p["max_distance_per_frame"]:
                issue("POSE_JUMP", bone=bone.name, from_frame=previous, frame=current,
                      distance_per_frame=speed, allowed=p["max_distance_per_frame"])
    complete = bool(contacts) and bool(joints)
    return {"rig": rig.name, "quality_gate": "FAIL" if issue_count else "PASS" if complete else "INCOMPLETE",
            "issue_count": issue_count, "issues": issues, "issues_truncated": issue_count > len(issues),
            "samples": len(frames), "sample_frames": frames, "contact_results": contact_results,
            "joint_results": joint_results, "maximum_distance_per_frame": max_speed,
            "evaluated_world_space": True, "frame_restored": scene.frame_current == old_frame and scene.frame_subframe == old_subframe,
            "perfect_motion_certified": False,
            "limitations": ["Only declared contacts and joints are checked; no intent or anatomy is inferred.",
                            "Contact drift measures world XY at the foot bone head; it does not test floor height, collision or sole rotation.",
                            "Joint flexion is the unsigned angle between bone axes; it does not detect backward bending or twist.",
                            "Sampling may miss changes between inspected frames; visual review remains necessary."]}


def execute(operation, payload, root, scene):
    p = C.validate(operation, payload)
    if scene != bpy.context.scene:
        raise ValueError("MOTION_ACTIVE_SCENE_REQUIRED")
    if operation == "studio.motion.audit":
        return _audit(scene, p)
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        raise ValueError("MOTION_OBJECT_MODE_REQUIRED")
    old_frame, old_subframe = scene.frame_current, scene.frame_subframe
    try:
        with _Transaction() as tx:
            return _create(tx, scene, p) if operation.endswith("rig.create") else _clip(tx, scene, p)
    finally:
        scene.frame_set(old_frame, subframe=old_subframe)
