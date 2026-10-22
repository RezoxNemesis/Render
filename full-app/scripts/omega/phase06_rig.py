# SPDX-License-Identifier: GPL-2.0-or-later
"""RENDER OMEGA P06: native Blender humanoid skinning, FK and opt-in leg IK.

The P10 registry owns dispatch; this module intentionally imports neither P05 nor
P07.  All lengths are *mesh local* Blender units, L means positive local X,
and coordinates use Z up / -Y forward.  The default landmarks fit only the
independent 2.05 BU test fixture; production meshes should pass landmarks.
No script is evaluated from client input and no filesystem paths are used.
"""
import hashlib
import json
import math
import re
import struct

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.rig.bind", "omega.rig.audit")
MAX_VERTICES = 100_000
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

# Neutral P05 -> P06 contract. Every landmark is expressed in mesh-local space.
LANDMARK_NAMES = (
    "pelvis", "spine", "chest", "neck", "head", "crown",
    "shoulder.L", "elbow.L", "wrist.L", "hand.L",
    "shoulder.R", "elbow.R", "wrist.R", "hand.R",
    "hip.L", "knee.L", "ankle.L", "toe.L",
    "hip.R", "knee.R", "ankle.R", "toe.R",
)

def default_landmarks():
    """Return a new, mutable set of neutral 2.05-BU humanoid landmarks."""
    points = {
        "pelvis": (0, 0, 1.00), "spine": (0, 0, 1.23),
        "chest": (0, 0, 1.50), "neck": (0, 0, 1.68),
        "head": (0, 0, 1.84), "crown": (0, 0, 2.06),
    }
    for side, sign in (("L", 1), ("R", -1)):
        points.update({
            "shoulder." + side: (sign * .28, 0, 1.55),
            "elbow." + side: (sign * .55, -.005, 1.35),
            "wrist." + side: (sign * .81, -.005, 1.24),
            "hand." + side: (sign * .95, -.015, 1.20),
            "hip." + side: (sign * .16, 0, 1.00),
            "knee." + side: (sign * .17, -.025, .55),
            "ankle." + side: (sign * .16, 0, .11),
            "toe." + side: (sign * .16, -.17, .07),
        })
    return points


def _finite_xyz(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("INVALID_ARGUMENTS: landmark must be xyz")
    if any(type(x) not in (float, int) or not math.isfinite(x) or abs(x) > 10000 for x in value):
        raise ValueError("INVALID_ARGUMENTS: nonfinite or excessive landmark")
    return tuple(float(v) for v in value)


def _distance_squared(a, b):
    return sum((u-v)**2 for u, v in zip(a, b))


def _segment_distance(point, head, tail):
    segment = tuple(b-a for a, b in zip(head, tail))
    length2 = sum(v*v for v in segment)
    if length2 < 1e-8:
        raise ValueError("INVALID_ARGUMENTS: coincident joint landmarks")
    t = max(0., min(1., sum((p-a)*d for p, a, d in zip(point, head, segment))/length2))
    return math.sqrt(sum((p-a-t*d)**2 for p, a, d in zip(point, head, segment)))


def _hierarchy(points):
    bones = [
        ("root", "ankle.L", "pelvis", None, False),
        ("hips", "pelvis", "spine", "root", True),
        ("spine", "spine", "chest", "hips", True),
        ("chest", "chest", "neck", "spine", True),
        ("neck", "neck", "head", "chest", True),
        ("head", "head", "crown", "neck", True),
    ]
    # Root should be on the centerline, not at the left ankle.
    points["root_floor"] = (0.0, 0.0, 0.0)
    points["root_tip"] = (0.0, 0.0, .16)
    bones[0] = ("root", "root_floor", "root_tip", None, False)
    chains = {"core": ("hips", "spine", "chest", "neck", "head")}
    for side in ("L", "R"):
        bones.extend((
            ("clavicle."+side, "chest", "shoulder."+side, "chest", True),
            ("upper_arm."+side, "shoulder."+side, "elbow."+side, "clavicle."+side, True),
            ("forearm."+side, "elbow."+side, "wrist."+side, "upper_arm."+side, True),
            ("hand."+side, "wrist."+side, "hand."+side, "forearm."+side, True),
            ("thigh."+side, "hip."+side, "knee."+side, "hips", True),
            ("shin."+side, "knee."+side, "ankle."+side, "thigh."+side, True),
            ("foot."+side, "ankle."+side, "toe."+side, "shin."+side, True),
        ))
        chains["arm."+side] = tuple(n+"."+side for n in ("clavicle", "upper_arm", "forearm", "hand"))
        chains["leg."+side] = tuple(n+"."+side for n in ("thigh", "shin", "foot"))
    return bones, chains


def _weights_for_vertex(xyz, segments, chains):
    """Two joint-local influences, normalized and isolated to the nearest limb.

    Choosing one chain avoids the common catastrophe where an opposite arm or
    thigh contributes weights to a nearby limb. Adjacent segments in that chain
    interpolate smoothly near elbows and knees. Does not imply final art QA.
    """
    distances = {name: _segment_distance(xyz, *endpoints)
                 for name, endpoints in segments.items()}
    family = min(chains.values(), key=lambda chain: min(distances[n] for n in chain))
    near = sorted(family, key=lambda name: (distances[name], name))[:2]
    raw = [(name, (distances[name] + .055) ** -2) for name in near]
    denom = sum(w for _, w in raw)
    if denom <= 0 or not math.isfinite(denom):
        raise ValueError("INVALID_ARGUMENTS: invalid bind distances")
    return {name: weight / denom for name, weight in raw}


def _landmarks(value):
    if value is None:
        return default_landmarks(), "default_neutral_humanoid"
    if not isinstance(value, dict) or set(value) != set(LANDMARK_NAMES):
        raise ValueError("INVALID_ARGUMENTS: all named neutral landmarks required")
    parsed = {name: _finite_xyz(value[name]) for name in LANDMARK_NAMES}
    for side, sign in (("L", 1), ("R", -1)):
        if sign * parsed["shoulder."+side][0] <= 0 or sign * parsed["hip."+side][0] <= 0:
            raise ValueError("INVALID_ARGUMENTS: reversed local X side landmarks")
    return parsed, "supplied_mesh_local"


def validate(operation, payload):
    """Pure strict validator, safe without bpy or an Android process."""
    if operation not in OPERATION_NAMES or not isinstance(payload, dict):
        raise ValueError("INVALID_ARGUMENTS: unknown rig operation/payload")
    allowed = {"object_name", "expected_revision"}
    if operation == "omega.rig.bind":
        allowed |= {"rig_name", "template", "landmarks", "enable_leg_ik"}
    if set(payload) - allowed:
        raise ValueError("INVALID_ARGUMENTS: unexpected fields")
    name = payload.get("object_name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("INVALID_ARGUMENTS: object_name")
    revision = payload.get("expected_revision")
    if revision is not None and (not isinstance(revision, str) or not _HEX64.fullmatch(revision)):
        raise ValueError("INVALID_ARGUMENTS: expected_revision")
    clean = {"object_name": name, "expected_revision": revision}
    if operation == "omega.rig.bind":
        rig = payload.get("rig_name", "OmegaRig."+name)
        if not isinstance(rig, str) or not _NAME.fullmatch(rig):
            raise ValueError("INVALID_ARGUMENTS: rig_name")
        if payload.get("template", "humanoid") != "humanoid":
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE: quadruped template not implemented")
        ik = payload.get("enable_leg_ik", False)
        if type(ik) is not bool:
            raise ValueError("INVALID_ARGUMENTS: enable_leg_ik")
        landmarks, origin = _landmarks(payload.get("landmarks"))
        bones, _ = _hierarchy(dict(landmarks))
        for _, a, b, _, _ in bones:
            if _distance_squared(landmarks.get(a, (0,0,0)), landmarks.get(b, (0,0,0))) < 1e-8 and not a.startswith("root_"):
                raise ValueError("INVALID_ARGUMENTS: collapsed bone")
        clean.update({"rig_name": rig, "template": "humanoid", "landmarks": landmarks,
                      "landmark_origin": origin, "enable_leg_ik": ik})
    return clean


def _bpy():
    try:
        import bpy
        return bpy
    except ImportError as exc:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE: bpy runtime is absent") from exc


def _object(scene, name):
    ob = scene.objects.get(name)
    if ob is None or ob.type != "MESH":
        raise ValueError("MISSING_REFERENCE: mesh object not in active scene")
    return ob


def _revision(ob):
    """Revision of source mesh geometry, topology and world transform, not pose."""
    digest = hashlib.sha256()
    digest.update(struct.pack("<II", len(ob.data.vertices), len(ob.data.polygons)))
    for vert in ob.data.vertices:
        digest.update(struct.pack("<3d", *vert.co))
    for poly in ob.data.polygons:
        digest.update(struct.pack("<I", len(poly.vertices)))
        for v in poly.vertices:
            digest.update(struct.pack("<I", v))
    for row in ob.matrix_world:
        digest.update(struct.pack("<4d", *row))
    return digest.hexdigest()


def _receipt(operation, scene, revision, **extra):
    out = {"operation": operation, "state": "succeeded", "scene": scene.name,
           "source_revision": revision, "created": [],
           "artifact": {"kind": "none", "sha256": None},
           "native_execution_verified": True, "visual_quality_verified": False,
           "quality_reduced": False, "warnings": []}
    out.update(extra)
    return out


def _audit_native(bpy, scene, ob):
    arm_name = ob.get("omega_rig_name")
    rig = scene.objects.get(arm_name) if isinstance(arm_name, str) else None
    if not rig or rig.type != "ARMATURE":
        raise ValueError("MISSING_REFERENCE: bound rig not in scene")
    if rig.get("omega_bound_mesh") != ob.name:
        raise ValueError("CHECKPOINT_CONFLICT: wrong mesh binding")
    modifier = next((m for m in ob.modifiers if m.type == "ARMATURE" and m.object == rig), None)
    if modifier is None:
        raise ValueError("MISSING_REFERENCE: no deform modifier")
    deform_names = {bone.name for bone in rig.data.bones if bone.use_deform}
    group_index = {vg.index: vg.name for vg in ob.vertex_groups}
    missing_groups = sorted(name for name in deform_names if ob.vertex_groups.get(name) is None)
    zeros = 0
    overflow = 0
    max_error = 0.0
    max_influences = 0
    for vertex in ob.data.vertices:
        weights = [v.weight for v in vertex.groups
                   if group_index.get(v.group) in deform_names and v.weight > 1e-7]
        total = sum(weights)
        max_error = max(max_error, abs(1.0 - total))
        max_influences = max(max_influences, len(weights))
        if not weights:
            zeros += 1
        if total > 1.0001:
            overflow += 1
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = ob.evaluated_get(graph)
    eval_mesh = evaluated.to_mesh()
    try:
        topology_matches = len(eval_mesh.vertices) == len(ob.data.vertices)
        moved = 0
        max_displacement = 0.0
        if topology_matches:
            transform = ob.matrix_world
            for src, dst in zip(ob.data.vertices, eval_mesh.vertices):
                before, after = transform @ src.co, transform @ dst.co
                diff = (after - before).length
                if not math.isfinite(diff):
                    raise ValueError("INVALID_ARGUMENTS: nonfinite evaluated vertex")
                if diff > .0001:
                    moved += 1
                max_displacement = max(max_displacement, diff)
    finally:
        evaluated.to_mesh_clear()
    constraints = {b.name: [c.type for c in rig.pose.bones[b.name].constraints]
                   for b in rig.data.bones if b.name.startswith("shin.")}
    return {"armature": rig.name, "mesh": ob.name, "bone_count": len(rig.data.bones),
            "deform_bones": sorted(deform_names), "missing_deform_groups": missing_groups,
            "vertex_count": len(ob.data.vertices), "unweighted_vertices": zeros,
            "overweight_vertices": overflow, "max_weight_error": round(max_error, 7),
            "max_influences": max_influences, "topology_matches": topology_matches,
            "moved_vertices": moved, "max_displacement": round(max_displacement, 7),
            "ik_constraints": constraints,
            "pass_weights": not (zeros or overflow or missing_groups) and max_error < .0001,
            "unsupported_controllers": ["facial_shape_keys", "quadruped"],
            "landmark_origin": rig.get("omega_landmark_origin", "unknown"),
            "axis_contract": "+X=L, -X=R, Z=up, -Y=forward",
            "native_blender_version": bpy.app.version_string}


def audit(operation, payload, context):
    request = validate(operation, payload)
    bpy = _bpy()
    scene = context.get("scene") if isinstance(context, dict) else None
    if scene is None or bpy.context.scene != scene:
        raise ValueError("INVALID_ARGUMENTS: scene context mismatch")
    ob = _object(scene, request["object_name"])
    rev = _revision(ob)
    if request["expected_revision"] and request["expected_revision"] != rev:
        raise ValueError("CHECKPOINT_CONFLICT: mesh source revision changed")
    result = _audit_native(bpy, scene, ob)
    return _receipt("omega.rig.audit", scene, rev, audit=result,
                    warnings=[] if result["pass_weights"] else ["WEIGHT_AUDIT_FAILED"])


def execute(operation, payload, context):
    request = validate(operation, payload)
    if operation == "omega.rig.audit":
        return audit(operation, payload, context)
    bpy = _bpy()
    if not isinstance(context, dict) or bpy.context.scene != context.get("scene"):
        raise ValueError("INVALID_ARGUMENTS: scene context mismatch")
    scene = context["scene"]
    if context.get("cancellation_requested") is True or (
            callable(context.get("cancellation_requested")) and context["cancellation_requested"]()):
        raise ValueError("CANCELLED: rigging not started")
    ob = _object(scene, request["object_name"])
    if len(ob.data.vertices) == 0 or len(ob.data.vertices) > MAX_VERTICES:
        raise ValueError("INVALID_ARGUMENTS: mesh vertex budget")
    available = context.get("available_memory_bytes")
    if isinstance(available, int) and available < len(ob.data.vertices) * 400 + 8_000_000:
        raise ValueError("OUT_OF_MEMORY_PAUSED: insufficient memory for skinning")
    rev = _revision(ob)
    if request["expected_revision"] and request["expected_revision"] != rev:
        raise ValueError("CHECKPOINT_CONFLICT: mesh source revision changed")
    # Idempotent replay never duplicates a skeleton; differing settings conflict.
    spec = {k: request[k] for k in ("rig_name", "landmarks", "enable_leg_ik", "template")}
    spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
    existing = ob.get("omega_rig_name")
    if existing:
        if (existing != request["rig_name"] or ob.get("omega_rig_spec") != spec_hash
                or ob.get("omega_rig_source") != rev):
            raise ValueError("CHECKPOINT_CONFLICT: rig settings/source changed")
        checked = _audit_native(bpy, scene, ob)
        if not checked["pass_weights"]:
            raise ValueError("CHECKPOINT_CONFLICT: existing weights require repair")
        return _receipt(operation, scene, rev, already_complete=True, audit=checked)
    if scene.objects.get(request["rig_name"]) is not None:
        raise ValueError("CHECKPOINT_CONFLICT: rig object name in use")
    points = dict(request["landmarks"])
    bones, chains = _hierarchy(points)
    segments = {name: (points[a], points[b]) for name, a, b, _, deform in bones if deform}
    weights = [_weights_for_vertex(tuple(vert.co), segments, chains)
               for vert in ob.data.vertices]
    if any(ob.vertex_groups.get(n) for n in segments):
        raise ValueError("CHECKPOINT_CONFLICT: existing named deform groups")
    if context.get("dry_run"):
        return {"operation": operation, "state": "dry_run", "scene": scene.name,
                "source_revision": rev, "expected_bones": len(bones),
                "expected_vertices": len(weights), "native_execution_verified": False,
                "quality_reduced": False}
    previous_active = bpy.context.view_layer.objects.active
    previous_selected = [x for x in bpy.context.selected_objects]
    previous_mode = previous_active.mode if previous_active else "OBJECT"
    rig = None
    groups = []
    modifier = None
    try:
        if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        arm_data = bpy.data.armatures.new(request["rig_name"]+".Data")
        rig = bpy.data.objects.new(request["rig_name"], arm_data)
        scene.collection.objects.link(rig)
        rig.matrix_world = ob.matrix_world.copy()  # transforms aligned; no mesh parent change
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        for name, head, tail, parent, deform in bones:
            bone = arm_data.edit_bones.new(name)
            bone.head = points[head]
            bone.tail = points[tail]
            bone.use_deform = deform
            if parent:
                bone.parent = arm_data.edit_bones[parent]
                bone.use_connect = False
        if request["enable_leg_ik"]:
            for side in ("L", "R"):
                ankle = points["ankle."+side]
                knee = points["knee."+side]
                target = arm_data.edit_bones.new("ik_foot."+side)
                target.head = ankle
                target.tail = (ankle[0], ankle[1], ankle[2]+.14)
                target.parent = arm_data.edit_bones["root"]
                target.use_deform = False
                pole = arm_data.edit_bones.new("pole_knee."+side)
                pole.head = (knee[0], knee[1]-.45, knee[2])
                pole.tail = (knee[0], knee[1]-.45, knee[2]+.12)
                pole.parent = arm_data.edit_bones["root"]
                pole.use_deform = False
        bpy.ops.object.mode_set(mode="OBJECT")
        if request["enable_leg_ik"]:
            for side in ("L", "R"):
                con = rig.pose.bones["shin."+side].constraints.new("IK")
                con.name = "OmegaLegIK."+side
                con.target = rig
                con.subtarget = "ik_foot."+side
                con.chain_count = 2
                con.pole_target = rig
                con.pole_subtarget = "pole_knee."+side
                con.pole_angle = -math.pi / 2
        for name in segments:
            groups.append(ob.vertex_groups.new(name=name))
        lookup = {v.name: v for v in groups}
        for vi, binding in enumerate(weights):
            for name, weight in binding.items():
                lookup[name].add([vi], weight, "REPLACE")
        modifier = ob.modifiers.new("OmegaSkin", "ARMATURE")
        modifier.object = rig
        rig["omega_bound_mesh"] = ob.name
        rig["omega_landmark_origin"] = request["landmark_origin"]
        rig["omega_landmarks_json"] = json.dumps(request["landmarks"], sort_keys=True)
        rig["omega_axis_contract"] = "+X=L,-X=R,Z=up,-Y=forward"
        rig["omega_source_revision"] = rev
        ob["omega_rig_name"] = rig.name
        ob["omega_rig_spec"] = spec_hash
        ob["omega_rig_source"] = rev
        report = _audit_native(bpy, scene, ob)
        if not report["pass_weights"] or not report["topology_matches"]:
            raise ValueError("WEIGHT_AUDIT_FAILED: cannot verify deform skin")
        return _receipt(operation, scene, rev, created=[rig.name],
                        audit=report, already_complete=False,
                        warnings=["NEUTRAL_TEMPLATE_LANDMARKS_REQUIRE_FIT_AUDIT"]
                        if request["landmark_origin"].startswith("default") else [])
    except Exception:
        # Roll back newly added Blender objects and vertex groups; leave user mesh.
        for prop in ("omega_rig_name", "omega_rig_spec", "omega_rig_source"):
            if prop in ob:
                del ob[prop]
        if modifier and modifier.name in ob.modifiers:
            ob.modifiers.remove(modifier)
        for group in reversed(groups):
            if ob.vertex_groups.get(group.name):
                ob.vertex_groups.remove(group)
        if rig and rig.name in bpy.data.objects:
            if bpy.context.object and bpy.context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.data.objects.remove(rig, do_unlink=True)
        raise
    finally:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for selected in previous_selected:
            if selected.name in bpy.data.objects:
                selected.select_set(True)
        if previous_active and previous_active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = previous_active
            if previous_mode != "OBJECT":
                try:
                    bpy.ops.object.mode_set(mode=previous_mode)
                except RuntimeError:
                    pass
