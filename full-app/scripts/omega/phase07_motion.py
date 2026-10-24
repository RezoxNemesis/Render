# SPDX-License-Identifier: GPL-2.0-or-later
"""RENDER OMEGA Phase 07: bounded, editable native Blender biped walk/NLA.

This module deliberately has no import-time bpy dependency or app entrypoint.
Only P10's main-thread typed dispatcher may register its public operations.
Forward means armature-local +Y; contact is the shin tip (not a mesh sole).
"""
import hashlib
import json
import math
import re

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.motion.create_actions", "omega.motion.audit")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_CLIP = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}\Z")
_CHANNELS = ("root", "left_thigh", "left_shin", "right_thigh", "right_shin")
_DEFAULT_BONES = {"root": "Root", "left_thigh": "LeftThigh",
                  "left_shin": "LeftShin", "right_thigh": "RightThigh",
                  "right_shin": "RightShin"}
_CREATE_KEYS = {"rig", "clip", "kind", "start", "frames", "stride", "clearance",
                "contact_z", "retime_scale", "bones"}
_AUDIT_KEYS = {"rig", "clip"}


def _finite(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("INVALID_ARGUMENTS")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _name(value, pattern=_NAME):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _channels(value):
    if not isinstance(value, dict) or set(value) != set(_CHANNELS):
        raise ValueError("INVALID_ARGUMENTS")
    normalized = {k: _name(value[k]) for k in _CHANNELS}
    if len(set(normalized.values())) != len(_CHANNELS):
        raise ValueError("INVALID_ARGUMENTS")
    return normalized


def validate(operation, payload):
    """Pure allowlisted validation: never loads bpy or evaluates arbitrary code."""
    if operation not in OPERATION_NAMES or not isinstance(payload, dict):
        raise ValueError("INVALID_ARGUMENTS")
    if operation == "omega.motion.audit":
        if set(payload) != _AUDIT_KEYS:
            raise ValueError("INVALID_ARGUMENTS")
        return {"rig": _name(payload["rig"]), "clip": _name(payload["clip"], _CLIP)}
    if set(payload) - _CREATE_KEYS or not {"rig", "clip"} <= set(payload):
        raise ValueError("INVALID_ARGUMENTS")
    kind = payload.get("kind", "walk")
    if kind not in ("walk", "retime"):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    parsed = {"rig": _name(payload["rig"]),
              "clip": _name(payload["clip"], _CLIP), "kind": kind}
    parsed["retime_scale"] = _finite(payload.get("retime_scale", 1.0), .5, 3.0)
    if kind == "retime":
        if set(payload) - {"rig", "clip", "kind", "retime_scale"}:
            raise ValueError("INVALID_ARGUMENTS")
        return parsed
    start = payload.get("start", 1)
    frames = payload.get("frames", 25)
    if (type(start) is not int or not 1 <= start <= 100000 or
            type(frames) is not int or not 13 <= frames <= 121 or
            (frames - 1) % 4):
        raise ValueError("INVALID_ARGUMENTS")
    parsed.update(start=start, frames=frames,
                  stride=_finite(payload.get("stride", .36), .08, .45),
                  clearance=_finite(payload.get("clearance", .075), .01, .18))
    if "contact_z" in payload:
        parsed["contact_z"] = _finite(payload["contact_z"], -100.0, 100.0)
    if "bones" in payload:
        parsed["bones"] = _channels(payload["bones"])
    return parsed


def _bpy_scene(context):
    try:
        import bpy
    except ImportError:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE: bpy unavailable") from None
    if not isinstance(context, dict) or not isinstance(context.get("scene"), bpy.types.Scene):
        raise ValueError("INVALID_ARGUMENTS")
    return bpy, context["scene"]


def _guard_context(context):
    # P10 supplies trusted executor state, not a caller-supplied filesystem path.
    # A rejected dry run must never create a real action and call it a preview.
    if context.get("dry_run", False):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE: motion dry_run")
    cancel = context.get("cancellation_requested", False)
    if (cancel() if callable(cancel) else cancel):
        raise ValueError("CANCELLED_BY_OWNER")


def _rig(scene, name):
    ob = scene.objects.get(name)
    if ob is None or ob.type != "ARMATURE":
        raise ValueError("MISSING_REFERENCE")
    return ob


def _bones(rig, override):
    if override is not None:
        names = override
    elif "omega_motion_channels" in rig:
        try:
            data = rig["omega_motion_channels"]
            names = _channels(json.loads(data) if isinstance(data, str) else dict(data))
        except (ValueError, TypeError, KeyError):
            raise ValueError("INVALID_RIG_METADATA") from None
    else:
        names = _DEFAULT_BONES.copy()
    found = {}
    for alias, name in names.items():
        found[alias] = rig.pose.bones.get(name)
        if found[alias] is None:
            raise ValueError("MISSING_REFERENCE")
    return names, found


def _fingerprint(rig, names):
    data = []
    for alias in _CHANNELS:
        bone = rig.data.bones[names[alias]]
        data.append([alias, bone.name, bone.parent.name if bone.parent else None,
                     [round(float(x), 6) for x in bone.head_local],
                     [round(float(x), 6) for x in bone.tail_local],
                     [round(float(v), 6) for row in bone.matrix_local.to_3x3() for v in row]])
    return hashlib.sha256(json.dumps(data, separators=(",", ":")).encode("utf8")).hexdigest()


def _action_name(rig, clip):
    suffix = hashlib.sha256((rig + "\0" + clip).encode("utf8")).hexdigest()[:10]
    return "OMEGA07_" + clip[:38] + "_" + suffix


def _track_name(rig, clip):
    return _action_name(rig, clip) + "_NLA"


def _fcurves(action):
    """Handle Blender legacy actions and 4.4+ layered action channelbags."""
    found = []
    try:
        found = list(action.fcurves)
    except AttributeError:
        pass
    if found:
        return found
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for slot in getattr(action, "slots", []):
                bag = strip.channelbag(slot)
                if bag is not None:
                    found.extend(bag.fcurves)
    return found


def _curve_digest(action):
    data = [(f.data_path, f.array_index,
             [(round(float(k.co.x), 5), round(float(k.co.y), 6))
              for k in f.keyframe_points]) for f in _fcurves(action)]
    return hashlib.sha256(json.dumps(sorted(data), separators=(",", ":")).encode()).hexdigest()


def _find_strip(rig, clip):
    name = _track_name(rig.name, clip)
    anim = rig.animation_data
    if anim is None:
        return None, None
    for track in anim.nla_tracks:
        if track.name == name:
            for strip in track.strips:
                if strip.action is not None and strip.action.name == _action_name(rig.name, clip):
                    return track, strip
            raise ValueError("CHECKPOINT_CONFLICT")
    return None, None


def _preflight_pose(rig, pose):
    # This first slice is intentionally limited to straight-down, XYZ FK legs
    # with +Y travel. Arbitrary P06 bone-axis/IK conventions need negotiation.
    if any(abs(float(x) - 1.0) > .0001 for x in rig.scale):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    if any(abs(float(x)) > .0001 for x in rig.rotation_euler):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    root = pose["root"]
    if pose["left_thigh"].parent != root or pose["right_thigh"].parent != root:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    for side in ("left", "right"):
        upper, lower = pose[side + "_thigh"], pose[side + "_shin"]
        if lower.parent != upper:
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
        if abs(upper.bone.tail_local.z - lower.bone.head_local.z) > .01:
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
        for pb in (upper, lower):
            vec = pb.bone.tail_local - pb.bone.head_local
            if (vec.length < .1 or vec.z > -.9 * vec.length or
                    abs(vec.x) > .1 * vec.length or abs(vec.y) > .1 * vec.length or
                    pb.rotation_mode != "XYZ" or
                    max(abs(float(pb.rotation_euler.y)), abs(float(pb.rotation_euler.z))) > .001):
                raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
        def sign(pb):
            from mathutils import Vector
            axis = pb.bone.matrix_local.to_3x3() @ Vector((0.0, 0.0, 1.0))
            if abs(axis.y) < .9:
                raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
            return 1 if axis.y > 0 else -1
        if sign(upper) != sign(lower):
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    if root.rotation_mode != "XYZ" or any(abs(float(x)) > .001 for x in root.rotation_euler):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")


def _solve_leg(hip_z, l1, l2, target_y, hip_y, target_z):
    """Exact planar two-segment FK angles from a target shin-tip position."""
    d = target_y - hip_y
    down = hip_z - target_z
    r = math.hypot(d, down)
    if r >= l1 + l2 - .00001 or r <= abs(l1 - l2) + .00001 or down <= 0:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE: unreachable foot contact")
    a = math.acos(max(-1., min(1., (r*r + l1*l1 - l2*l2)/(2*r*l1))))
    knee = math.acos(max(-1., min(1., (r*r - l1*l1 - l2*l2)/(2*l1*l2))))
    thigh = math.atan2(d, down) + a
    return thigh, -knee


def _plan(p, pose):
    contact = p.get("contact_z", min(float(pose[x].bone.tail_local.z)
                    for x in ("left_shin", "right_shin")) + .09)
    frames = []
    for i in range(p["frames"]):
        t = i / (p["frames"] - 1)
        root_y = p["stride"] * t
        pitches = {}
        for side in ("left", "right"):
            if side == "left":
                stance = t <= .5
                step = 0. if stance else (t - .5) * 2.
                world_y = .25*p["stride"] if stance else (.25 + step)*p["stride"]
            else:
                stance = t >= .5
                step = t * 2.
                world_y = .75*p["stride"] if stance else (-.25 + step)*p["stride"]
            z = contact if stance else contact + p["clearance"]*math.sin(math.pi*step)
            a, b = pose[side+"_thigh"], pose[side+"_shin"]
            thigh, shin = _solve_leg(float(a.bone.head_local.z), a.bone.length,
                                    b.bone.length, world_y-root_y,
                                    float(a.bone.head_local.y), z)
            from mathutils import Vector
            axis = a.bone.matrix_local.to_3x3() @ Vector((0., 0., 1.))
            sign = 1. if axis.y > 0 else -1.
            pitches[side] = (sign * thigh, sign * shin)
        frames.append((p["start"] + i, root_y, pitches))
    return contact, frames


def _signature(p, names, revision):
    return hashlib.sha256(json.dumps({"payload": p, "bones": names,
                     "source_revision": revision}, sort_keys=True,
                     separators=(",", ":")).encode("utf8")).hexdigest()


def _receipt(op, scene, revision, created=(), **more):
    out = {"operation": op, "state": "succeeded", "scene": scene.name,
           "source_revision": revision, "created": list(created),
           "artifact": {"kind": "none", "sha256": None},
           "native_execution_verified": True, "visual_quality_verified": False,
           "quality_reduced": False, "warnings": [
                "Shin-tip contact heuristic only; character skin/visual quality not verified"]}
    out.update(more)
    return out


def execute(operation, payload, context):
    p = validate(operation, payload)
    bpy, scene = _bpy_scene(context)
    if operation == "omega.motion.audit":
        return audit(operation, payload, context)
    _guard_context(context)
    rig = _rig(scene, p["rig"])
    track, strip = _find_strip(rig, p["clip"])
    if p["kind"] == "retime":
        if strip is None or track.mute:
            raise ValueError("MISSING_REFERENCE")
        action = strip.action
        before = _curve_digest(action)
        old_scale = float(strip.scale)
        try:
            strip.scale = p["retime_scale"]
            if abs(float(strip.scale) - p["retime_scale"]) > .00001 or _curve_digest(action) != before:
                raise ValueError("NATIVE_RETIME_UNCONFIRMED")
        except Exception:
            strip.scale = old_scale
            raise
        return _receipt(operation, scene, action.get("omega_motion_source_revision", "unknown"),
                        action=action.name, nla_track=track.name, nla_scale=float(strip.scale),
                        fcurve_hash=before, keyframes_unchanged=True)
    names, pose = _bones(rig, p.get("bones"))
    _preflight_pose(rig, pose)
    revision = _fingerprint(rig, names)
    signature = _signature(p, names, revision)
    if strip is not None:
        if strip.action.get("omega_motion_signature") != signature:
            raise ValueError("CHECKPOINT_CONFLICT")
        return _receipt(operation, scene, revision, already_complete=True,
                        action=strip.action.name, nla_track=track.name,
                        nla_scale=float(strip.scale), fcurve_hash=_curve_digest(strip.action))
    action_name = _action_name(rig.name, p["clip"])
    if bpy.data.actions.get(action_name) is not None:
        raise ValueError("CHECKPOINT_CONFLICT")
    job_id = context.get("job_id")
    if job_id is not None:
        if not isinstance(job_id, str) or re.fullmatch(r"[0-9a-f]{32}", job_id) is None:
            raise ValueError("INVALID_ARGUMENTS")
        if any(a.get("omega_motion_job_id") == job_id for a in bpy.data.actions):
            raise ValueError("CHECKPOINT_CONFLICT")
    anim = rig.animation_data_create()
    if anim.action is not None or any(not t.mute for t in anim.nla_tracks):
        raise ValueError("CHECKPOINT_CONFLICT")
    contact, plan = _plan(p, pose)  # All IK reach checks before mutations.
    old_frame, old_subframe = scene.frame_current, scene.frame_subframe
    original = {alias: (tuple(pb.location), tuple(pb.rotation_euler))
                for alias, pb in pose.items()}
    action = None
    track = None
    try:
        action = bpy.data.actions.new(name=action_name)
        action["omega_motion_signature"] = signature
        action["omega_motion_source_revision"] = revision
        action["omega_motion_rig"] = rig.name
        action["omega_motion_clip"] = p["clip"]
        action["omega_motion_start"] = p["start"]
        action["omega_motion_frames"] = p["frames"]
        action["omega_motion_stride"] = p["stride"]
        action["omega_motion_contact_z"] = contact
        action["omega_motion_bones"] = json.dumps(names, sort_keys=True)
        action["omega_motion_fps"] = scene.render.fps
        action["omega_motion_fps_base"] = scene.render.fps_base
        if job_id is not None:
            action["omega_motion_job_id"] = job_id
        anim.action = action
        # PoseBone.location is in the ROOT BONE's local basis, not armature
        # axes. Convert armature-local forward +Y so an upright Root does not
        # accidentally animate vertical motion.
        from mathutils import Vector
        root_local_forward = pose["root"].bone.matrix_local.to_3x3().inverted() @ Vector((0., 1., 0.))
        for frame, root_y, ang in plan:
            _guard_context(context)  # Bounded cancellation at keyframe boundaries.
            for axis in range(3):
                pose["root"].location[axis] = root_y * root_local_forward[axis]
                pose["root"].keyframe_insert(data_path="location", index=axis,
                                              frame=frame, group="OMEGA07 Root Motion")
            for side in ("left", "right"):
                for alias, angle in ((side+"_thigh", ang[side][0]),
                                     (side+"_shin", ang[side][1])):
                    pb = pose[alias]
                    pb.rotation_euler.x = angle
                    pb.keyframe_insert(data_path="rotation_euler", index=0,
                                       frame=frame, group="OMEGA07 Foot Contact")
        curves = _fcurves(action)
        if len(curves) != 7 or any(len(c.keyframe_points) != p["frames"] for c in curves):
            raise ValueError("NATIVE_ACTION_UNCONFIRMED")
        for curve in curves:
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
                point.handle_left_type = "VECTOR"
                point.handle_right_type = "VECTOR"
            mod = curve.modifiers.new(type="CYCLES")
            mod.mode_before = "REPEAT_OFFSET" if curve.data_path.endswith(".location") else "REPEAT"
            mod.mode_after = mod.mode_before
            curve.update()
        track = anim.nla_tracks.new()
        track.name = _track_name(rig.name, p["clip"])
        strip = track.strips.new(action.name, p["start"], action)
        strip.action_frame_start = p["start"]
        strip.action_frame_end = p["start"] + p["frames"] - 1
        strip.scale = p["retime_scale"]
        strip.repeat = 1.0
        strip.blend_type = "REPLACE"
        strip.extrapolation = "HOLD_FORWARD"
        anim.action = None
        # Native postcondition: an evaluated pose and the real NLA strip must exist.
        result = _inspect(scene, rig, track, strip)
        if (result["contact"]["max_planted_drift"] > .035 or
                result["contact"]["max_penetration"] > .025):
            raise ValueError("NATIVE_CONTACT_VALIDATION_FAILED")
        return _receipt(operation, scene, revision, created=[action.name, track.name],
                        action=action.name, nla_track=track.name, nla_scale=float(strip.scale),
                        fcurve_hash=_curve_digest(action), root_motion=result["root_motion"],
                        contact=result["contact"], fcurve_count=len(curves))
    except Exception:
        if track is not None:
            anim.nla_tracks.remove(track)
        anim.action = None
        if action is not None:
            bpy.data.actions.remove(action)
        for alias, (location, rotation) in original.items():
            pose[alias].location = location
            pose[alias].rotation_euler = rotation
        raise
    finally:
        scene.frame_set(old_frame, subframe=old_subframe)


def _set_frame(scene, value):
    integer = math.floor(value)
    scene.frame_set(integer, subframe=value-integer)


def _inspect(scene, rig, track, strip):
    action = strip.action
    names = json.loads(action["omega_motion_bones"])
    frames = int(action["omega_motion_frames"])
    start = int(action["omega_motion_start"])
    stride = float(action["omega_motion_stride"])
    contact_z = float(action["omega_motion_contact_z"])
    curves = _fcurves(action)
    if len(curves) < 7:
        raise ValueError("NATIVE_ACTION_UNCONFIRMED")
    root_path = 'pose.bones["%s"].location' % names["root"]
    root_curves = {c.array_index: c for c in curves if c.data_path == root_path}
    if set(root_curves) != {0, 1, 2}:
        raise ValueError("NATIVE_ACTION_UNCONFIRMED")
    from mathutils import Vector
    root_basis = rig.data.bones[names["root"]].matrix_local.to_3x3()
    root = []
    for i in range(5):
        fr = start+i*(frames-1)/4
        local_vector = Vector(tuple(float(root_curves[j].evaluate(fr)) for j in range(3)))
        root.append(float((root_basis @ local_vector).y))
    # Verify local rotation loop seam from actual F-curves. Root uses offset cycle.
    seam = max((abs(float(c.evaluate(start)) - float(c.evaluate(start+frames-1)))
                for c in curves if c.data_path != root_path), default=math.inf)
    saved = (scene.frame_current, scene.frame_subframe)
    feet = {"left": [], "right": []}
    try:
        for i in range(frames):
            # End of NLA strip is exclusive. The epsilon measures its final pose.
            at = float(strip.frame_start) + i * float(strip.scale)
            if i == frames-1:
                at -= .00001
            _set_frame(scene, at)
            for side in feet:
                pb = rig.pose.bones[names[side+"_shin"]]
                local = pb.tail.copy()
                world = rig.matrix_world @ local
                feet[side].append((tuple(float(x) for x in world), float(local.z)))
    finally:
        scene.frame_set(saved[0], subframe=saved[1])
    middle = (frames-1)//2
    planted = {"left": feet["left"][:middle+1],
               "right": feet["right"][middle:]}
    drifts = {}
    for side, points in planted.items():
        anchor = points[0][0]
        drifts[side] = max(math.hypot(x[0][0]-anchor[0], x[0][1]-anchor[1]) for x in points)
    penetration = max(max(0.0, contact_z-p[1]) for points in planted.values() for p in points)
    return {"action": action.name,
            "nla": {"track": track.name, "strip": strip.name,
                    "scale": float(strip.scale), "repeat": float(strip.repeat),
                    "action_start": float(strip.action_frame_start),
                    "action_end": float(strip.action_frame_end),
                    "timeline_start": float(strip.frame_start),
                    "timeline_end": float(strip.frame_end)},
            "fcurve_count": len(curves), "keyframes": sum(len(c.keyframe_points) for c in curves),
            "fcurve_hash": _curve_digest(action),
            "root_motion": {"direction": "armature-local +Y",
                            "samples": root, "stride": root[-1]-root[0],
                            "expected_stride": stride},
            "loop_seam_rotation_error_radians": seam,
            "contact": {"method": "evaluated shin-tip; not skinned toe or sole",
                        "left_planted_drift": drifts["left"],
                        "right_planted_drift": drifts["right"],
                        "max_planted_drift": max(drifts.values()),
                        "max_penetration": penetration,
                        "contact_z_armature_local": contact_z}}


def audit(operation, payload, context):
    if operation != "omega.motion.audit":
        raise ValueError("INVALID_ARGUMENTS")
    p = validate(operation, payload)
    bpy, scene = _bpy_scene(context)
    rig = _rig(scene, p["rig"])
    track, strip = _find_strip(rig, p["clip"])
    if strip is None:
        raise ValueError("MISSING_REFERENCE")
    action = strip.action
    names = json.loads(action["omega_motion_bones"])
    revision = _fingerprint(rig, names)
    if revision != action["omega_motion_source_revision"]:
        raise ValueError("CHECKPOINT_CONFLICT")
    data = _inspect(scene, rig, track, strip)
    return _receipt(operation, scene, revision,
                    **data, fps=int(scene.render.fps), fps_base=float(scene.render.fps_base),
                    genuine_blender_data=True)
