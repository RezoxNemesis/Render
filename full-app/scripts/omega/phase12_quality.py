# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only native Blender quality observations and bounded revision proposals.

This is *not* an image similarity model. Every geometric observation comes from
bpy mesh datablocks in the selected scene. No bpy import or filesystem access
occurs at import time; P10 must dispatch on Blender's native main thread.
"""

import hashlib
import json
import math
import re
import struct

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.quality.inspect", "omega.quality.revise_plan")
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_LANDMARKS = frozenset(("shoulder_L", "shoulder_R", "head_L", "head_R", "neck_L", "neck_R"))
_REQUIRED = frozenset(("shoulder_L", "shoulder_R", "head_L", "head_R"))
_LIMIT_VERTICES = 60000
_LIMIT_FACES = 120000
_MAX_BYTES = 131072


def _error(code):
    raise ValueError(code)


def _finite(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _sha(value):
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def _indices(values, maximum=2048):
    return (type(values) is list and 0 < len(values) <= maximum and
            all(type(n) is int and 0 <= n < _LIMIT_VERTICES for n in values) and
            len(values) == len(set(values)))


def validate(operation, payload):
    """Strictly validate untrusted JSON; return an immutable-to-caller copy."""
    if operation not in OPERATION_NAMES:
        _error("UNSUPPORTED_NATIVE_FEATURE")
    if type(payload) is not dict:
        _error("INVALID_ARGUMENTS")
    try:
        encoded = json.dumps(payload, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError):
        _error("INVALID_ARGUMENTS")
    if len(encoded.encode("utf-8")) > _MAX_BYTES:
        _error("INVALID_ARGUMENTS")
    allowed = {"target_object", "landmarks", "reference_target", "source_revision",
               "image_name", "shoulder_region_vertices", "scene_scale"}
    if operation == "omega.quality.revise_plan":
        allowed |= {"checkpoint_sha256", "max_iterations", "attempts_used",
                    "previous_source_revision", "previous_metric", "previous_guard_sha256"}
    if set(payload) - allowed or "target_object" not in payload:
        _error("INVALID_ARGUMENTS")
    target = payload["target_object"]
    if type(target) is not str or not _NAME.fullmatch(target) or ".." in target:
        _error("INVALID_ARGUMENTS")
    if "source_revision" in payload and not _sha(payload["source_revision"]):
        _error("INVALID_ARGUMENTS")
    if "scene_scale" in payload and not _finite(payload["scene_scale"], 0.0001, 1000000):
        _error("INVALID_ARGUMENTS")
    if "image_name" in payload:
        name = payload["image_name"]
        if type(name) is not str or not _NAME.fullmatch(name) or ".." in name:
            _error("INVALID_ARGUMENTS")
    if "landmarks" in payload:
        marks = payload["landmarks"]
        if type(marks) is not dict or set(marks) - _LANDMARKS or not _REQUIRED.issubset(marks):
            _error("INVALID_ARGUMENTS")
        if any(type(v) is not int or v < 0 or v >= _LIMIT_VERTICES for v in marks.values()):
            _error("INVALID_ARGUMENTS")
        if len(set(marks.values())) != len(marks):
            _error("INVALID_ARGUMENTS")
        if ("neck_L" in marks) != ("neck_R" in marks):
            _error("INVALID_ARGUMENTS")
    if "reference_target" in payload:
        ref = payload["reference_target"]
        if (type(ref) is not dict or set(ref) != {"measurement", "min", "max", "provenance"}
                or ref["measurement"] != "shoulder_width_over_head_width"
                or ref["provenance"] not in ("synthetic_fixture", "owner_measured")
                or not _finite(ref["min"], 0.001, 100)
                or not _finite(ref["max"], 0.001, 100)
                or ref["min"] > ref["max"] or "landmarks" not in payload):
            _error("INVALID_ARGUMENTS")
    if "shoulder_region_vertices" in payload:
        region = payload["shoulder_region_vertices"]
        if not _indices(region) or "landmarks" not in payload:
            _error("INVALID_ARGUMENTS")
        if not {payload["landmarks"]["shoulder_L"], payload["landmarks"]["shoulder_R"]}.issubset(region):
            _error("INVALID_ARGUMENTS")
    if operation == "omega.quality.revise_plan":
        n = payload.get("max_iterations", 2)
        attempts = payload.get("attempts_used", 0)
        if type(n) is not int or not 1 <= n <= 3 or type(attempts) is not int or not 0 <= attempts <= n:
            _error("INVALID_ARGUMENTS")
        if "checkpoint_sha256" in payload and not _sha(payload["checkpoint_sha256"]):
            _error("INVALID_ARGUMENTS")
        if attempts:
            if (not _sha(payload.get("previous_source_revision")) or
                    not _sha(payload.get("previous_guard_sha256")) or
                    not _finite(payload.get("previous_metric"), 0, 1e8)):
                _error("INVALID_ARGUMENTS")
        elif ("previous_source_revision" in payload or "previous_metric" in payload or
              "previous_guard_sha256" in payload):
            _error("INVALID_ARGUMENTS")
    return json.loads(encoded)


def _components(vertex_count, polygons):
    """Topology-connected components and boundary/non-manifold edge counts."""
    parent = list(range(vertex_count))
    rank = [0] * vertex_count
    uses = [0] * vertex_count
    edges = {}

    def root(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    def union(a, b):
        ra, rb = root(a), root(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    for face in polygons:
        if len(face) < 3:
            _error("INVALID_NATIVE_TOPOLOGY")
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            if a == b or not (0 <= a < vertex_count and 0 <= b < vertex_count):
                _error("INVALID_NATIVE_TOPOLOGY")
            uses[a] += 1
            union(a, b)
            key = (a, b) if a < b else (b, a)
            edges[key] = edges.get(key, 0) + 1
    roots = {root(i) for i in range(vertex_count) if uses[i]}
    return {"face_components": len(roots),
            "isolated_vertices": sum(1 for n in uses if not n),
            "boundary_edges": sum(1 for n in edges.values() if n == 1),
            "nonmanifold_edges": sum(1 for n in edges.values() if n > 2)}


def _measure(vertices, faces, marks, reference=None):
    """Geometry-only core, exercised by real bpy and pure regression tests."""
    if not vertices or len(vertices) > _LIMIT_VERTICES or len(faces) > _LIMIT_FACES:
        _error("INSPECTION_BUDGET_EXCEEDED")
    for row in vertices:
        if len(row) != 3 or not all(_finite(v, -1e9, 1e9) for v in row):
            _error("INVALID_NATIVE_TOPOLOGY")
    limits = [[min(v[i] for v in vertices), max(v[i] for v in vertices)] for i in range(3)]
    d = math.sqrt(2)
    quarter = [(v[0] + v[1]) / d for v in vertices]
    results = {"mesh_vertex_count": len(vertices), "mesh_face_count": len(faces),
               "world_bounds": {"x": limits[0], "y": limits[1], "z": limits[2]},
               "front_extent_xz": [limits[0][1] - limits[0][0], limits[2][1] - limits[2][0]],
               "side_extent_yz": [limits[1][1] - limits[1][0], limits[2][1] - limits[2][0]],
               "three_quarter_45deg_extent_xz": [max(quarter) - min(quarter), limits[2][1] - limits[2][0]],
               "assumed_front_axis": "X", "landmark_source": "explicit_mesh_vertex_indices"}
    results.update(_components(len(vertices), faces))
    if marks is None:
        results["anatomical_landmarks"] = "INSPECTION_UNAVAILABLE"
        return results
    if any(i >= len(vertices) for i in marks.values()):
        _error("INVALID_MESH_LANDMARK_INDEX")
    shoulder = abs(vertices[marks["shoulder_L"]][0] - vertices[marks["shoulder_R"]][0])
    head = abs(vertices[marks["head_L"]][0] - vertices[marks["head_R"]][0])
    if head < 0.000001 or shoulder < 0.000001:
        _error("DEGENERATE_LANDMARKS")
    ratio = shoulder / head
    results.update({"shoulder_width": shoulder, "head_width": head,
                    "shoulder_width_over_head_width": ratio,
                    "landmarks": {k: [float(n) for n in vertices[i]] for k, i in marks.items()}})
    if "neck_L" in marks:
        neck = abs(vertices[marks["neck_L"]][0] - vertices[marks["neck_R"]][0])
        results["neck_width"] = neck
        results["shoulder_width_over_neck_width"] = shoulder / neck if neck > 0.000001 else None
    if reference:
        results["reference_target"] = dict(reference)
        results["reference_passed"] = reference["min"] <= ratio <= reference["max"]
    else:
        results["reference_passed"] = None
    return results


def _protected_geometry_hash(vertices, faces, region):
    """Topology plus all non-selected world coordinates; safety guard for revisions."""
    h = hashlib.sha256()
    excluded = set(region)
    for i, vertex in enumerate(vertices):
        if i not in excluded:
            h.update(struct.pack("!I", i))
            h.update(struct.pack("!ddd", *(round(float(v), 6) for v in vertex)))
    for face in faces:
        h.update(struct.pack("!I", len(face)))
        for index in face:
            h.update(struct.pack("!I", index))
    return h.hexdigest()


def _revision(scene, target, vertices, faces):
    """A scoped Blender scene/target snapshot fingerprint (not a .blend hash)."""
    h = hashlib.sha256()
    h.update(json.dumps([scene.name, target.name, int(scene.frame_current),
                         scene.camera.name if scene.camera else None],
                        separators=(",", ":")).encode())
    for coords in vertices:
        h.update(struct.pack("!ddd", *(round(float(v), 6) for v in coords)))
    for face in faces:
        h.update(struct.pack("!I", len(face)))
        for index in face:
            h.update(struct.pack("!I", index))
    return h.hexdigest()


def _native_scene(context):
    try:
        import bpy
    except ImportError:
        _error("UNSUPPORTED_NATIVE_FEATURE")
    scene = context.get("scene") if type(context) is dict else None
    if not isinstance(scene, bpy.types.Scene):
        _error("UNSUPPORTED_NATIVE_FEATURE")
    return bpy, scene


def _image_probe(bpy, name):
    if not name:
        return {"state": "INSPECTION_UNAVAILABLE", "reason": "NO_IMAGE_DATABLOCK_SELECTED"}
    image = bpy.data.images.get(name)
    if image is None or not image.has_data or image.size[0] <= 0 or image.size[1] <= 0:
        return {"state": "INSPECTION_UNAVAILABLE", "reason": "NO_NATIVE_IMAGE_PIXELS"}
    width, height = int(image.size[0]), int(image.size[1])
    total = width * height
    # Bounded non-destructive samples. A sample hash MUST NOT be called a PNG SHA.
    count = min(total, 256)
    h = hashlib.sha256()
    luma = []
    for i in range(count):
        pixel_index = int(i * (total - 1) / max(1, count - 1)) * 4
        rgb = [float(image.pixels[pixel_index + j]) for j in range(3)]
        if not all(math.isfinite(value) for value in rgb):
            return {"state": "INSPECTION_UNAVAILABLE", "reason": "NONFINITE_IMAGE_PIXELS"}
        h.update(struct.pack("!fff", *rgb))
        luma.append(sum(c * w for c, w in zip(rgb, (0.2126, 0.7152, 0.0722))))
    return {"state": "sampled_native_image_buffer", "image": image.name,
            "width": width, "height": height, "samples": count,
            "sample_sha256": h.hexdigest(), "min_luminance": min(luma),
            "max_luminance": max(luma), "saved_file_sha256": None,
            "file_content_verified": False, "image_frame_provenance_verified": False,
            "warning": "Sampling a native image buffer does not verify a saved PNG/EXR or visual likeness"}


def _scene_probe(bpy, scene, target, vertices):
    objects = list(scene.objects)
    armature_mods = sum(1 for mod in target.modifiers if mod.type == "ARMATURE")
    influenced = 0
    if target.vertex_groups:
        influenced = sum(1 for vertex in target.data.vertices
                         if any(group.weight > 0 for group in vertex.groups))
    camera = scene.camera
    framing = {"state": "INSPECTION_UNAVAILABLE", "reason": "NO_ACTIVE_CAMERA"}
    if camera and camera.type == "CAMERA":
        try:
            from bpy_extras.object_utils import world_to_camera_view
            from mathutils import Vector
            coords = [world_to_camera_view(scene, camera, Vector(vertex)) for vertex in vertices[::max(1, len(vertices) // 512)]]
            framing = {"state": "measured", "camera": camera.name,
                       "sampled_vertices": len(coords),
                       "all_samples_inside_frame": all(c.z > 0 and 0 <= c.x <= 1 and 0 <= c.y <= 1 for c in coords),
                       "note": "Vertex sample bounds are not an occlusion or aesthetic composition test"}
        except Exception as exc:
            framing = {"state": "INSPECTION_UNAVAILABLE", "reason": "CAMERA_PROJECTION_UNSUPPORTED",
                       "error_type": type(exc).__name__}
    return {"mesh_objects": sum(o.type == "MESH" for o in objects),
            "light_objects": sum(o.type == "LIGHT" for o in objects),
            "camera_objects": sum(o.type == "CAMERA" for o in objects),
            "instanced_objects": sum(o.instance_type != "NONE" for o in objects),
            "active_camera": camera.name if camera else None,
            "camera_framing": framing,
            "uv_layer_count": len(target.data.uv_layers),
            "material_slot_count": len(target.material_slots),
            "unassigned_material_slots": sum(slot.material is None for slot in target.material_slots),
            "armature_modifier_count": armature_mods,
            "weighted_vertex_fraction": influenced / len(target.data.vertices),
            "evaluated_pose_change_measured": False,
            "motion_foot_drift": "INSPECTION_UNAVAILABLE"}


def _inspect(operation, payload, context):
    bpy, scene = _native_scene(context)
    target = scene.objects.get(payload["target_object"])
    if target is None or target.type != "MESH":
        _error("TARGET_OBJECT_MISSING_OR_WRONG_TYPE")
    if len(target.data.vertices) > _LIMIT_VERTICES or len(target.data.polygons) > _LIMIT_FACES:
        _error("INSPECTION_BUDGET_EXCEEDED")
    # Use real world-space mesh coordinates; do not infer polygon/pose from a photograph.
    vertices = [tuple(float(v) for v in (target.matrix_world @ vertex.co))
                for vertex in target.data.vertices]
    faces = [tuple(poly.vertices) for poly in target.data.polygons]
    metrics = _measure(vertices, faces, payload.get("landmarks"), payload.get("reference_target"))
    revision = _revision(scene, target, vertices, faces)
    if "source_revision" in payload and revision != payload["source_revision"]:
        _error("CHECKPOINT_CONFLICT")
    scene_facts = _scene_probe(bpy, scene, target, vertices)
    pixel = _image_probe(bpy, payload.get("image_name"))
    pixel["scene_frame_at_inspection"] = int(scene.frame_current)
    pixel["camera_at_inspection"] = scene.camera.name if scene.camera else None
    pixel["source_revision_at_inspection"] = revision
    issues = []
    target_ref = payload.get("reference_target")
    if target_ref and not metrics["reference_passed"]:
        issues.append({"code": "RATIO_OUT_OF_REFERENCE_RANGE", "kind": "measured_mesh",
                       "measurement": target_ref["measurement"],
                       "observed": metrics["shoulder_width_over_head_width"],
                       "reference_target": target_ref,
                       "target_object": target.name, "view": "front_assumed_XZ",
                       "confidence": "high_for_explicit_vertex_landmarks_not_aesthetic_likeness"})
    if metrics["face_components"] > 1:
        issues.append({"code": "DISCONNECTED_MESH_COMPONENTS", "kind": "measured_topology",
                       "observed": metrics["face_components"], "target_object": target.name,
                       "note": "Disconnected islands may be intentional; cannot infer missing joints"})
    if not scene_facts["uv_layer_count"]:
        issues.append({"code": "NO_UV_LAYERS", "kind": "measured_mesh",
                       "target_object": target.name, "severity": "informational"})
    if not scene_facts["material_slot_count"]:
        issues.append({"code": "NO_MATERIAL_SLOTS", "kind": "measured_mesh",
                       "target_object": target.name, "severity": "informational"})
    return {"operation": operation, "state": "succeeded", "scene": scene.name,
            "source_revision": revision, "created": [],
            "artifact": {"kind": "none", "sha256": None},
            "native_execution_verified": True, "visual_quality_verified": False,
            "quality_reduced": False, "warnings": ["No universal human anatomy thresholds or image likeness claims"],
            "target_object": target.name, "metrics": metrics, "scene_facts": scene_facts,
            "pixel_evidence": pixel, "findings": issues, "source_kind": "native_bpy_mesh",
            "revision_scope": "target_world_vertices_faces_scene_frame_and_camera_name_not_full_blend",
            "protected_geometry_sha256": _protected_geometry_hash(
                vertices, faces, payload.get("shoulder_region_vertices", []))
                if "shoulder_region_vertices" in payload else None,
            "scene_scale": payload.get("scene_scale"),
            "unverified_visual_features": ["facial likeness", "hair realism", "hands", "self-intersection",
                                           "rig pose deformation", "animation contact", "pixel-reference similarity"]}


def _distance(value, bounds):
    return max(bounds["min"] - value, 0.0, value - bounds["max"])


def _plan(inspection, payload, context):
    metrics = inspection["metrics"]
    bounds = payload.get("reference_target")
    max_iterations = payload.get("max_iterations", 2)
    attempts = payload.get("attempts_used", 0)
    proposals = []
    stop_reason = None
    if not bounds:
        stop_reason = "MISSING_REFERENCE"
    elif metrics.get("reference_passed"):
        stop_reason = "TARGET_MET_MEASURED_ONLY"
    elif attempts >= max_iterations:
        stop_reason = "ITERATION_LIMIT_REACHED"
    elif attempts:
        if payload["previous_source_revision"] == inspection["source_revision"]:
            stop_reason = "NO_NATIVE_REVISION"
        elif payload["previous_guard_sha256"] != inspection["protected_geometry_sha256"]:
            stop_reason = "NON_TARGET_GEOMETRY_CHANGED"
        else:
            previous = _distance(payload["previous_metric"], bounds)
            current = _distance(metrics["shoulder_width_over_head_width"], bounds)
            if current >= previous - max(1e-6, previous * 0.01):
                stop_reason = "NO_MEASURABLE_IMPROVEMENT"
    if stop_reason is None:
        ratio = metrics["shoulder_width_over_head_width"]
        target_ratio = (bounds["min"] + bounds["max"]) / 2.0
        region = payload.get("shoulder_region_vertices")
        if region is None:
            stop_reason = "SHOULDER_REGION_ANNOTATION_REQUIRED"
        elif any(i >= metrics["mesh_vertex_count"] for i in region):
            _error("INVALID_MESH_LANDMARK_INDEX")
        else:
            # Proposal ONLY, never a destructive edit. P11/P03 must verify the
            # actual native tool capability, full checkpoint, permissions and readback.
            proposals.append({"priority": 1, "target_object": inspection["target_object"],
                              "evidence": {"kind": "measured_mesh", "view": "front",
                                           "measurement": "shoulder_width_over_head_width",
                                           "observed": ratio, "reference_target": bounds,
                                           "source_revision": inspection["source_revision"]},
                              "repair": {"operation": "omega.artist.execute_tool",
                                         "tool": "mesh.adjust_region",
                                         "parameters": {"region": "shoulders", "vertex_indices": region,
                                                        "axis": "X", "pivot_world_x": 0.0,
                                                        "scale_factor": target_ratio / ratio}},
                              "expected": {"measurement": "shoulder_width_over_head_width",
                                           "target_value": target_ratio,
                                           "other_landmarks_must_remain_stable": True,
                                           "topology_must_remain_stable": True,
                                           "protected_geometry_sha256": inspection["protected_geometry_sha256"]},
                              "max_iterations": max_iterations, "attempts_remaining": max_iterations - attempts,
                              "rollback_checkpoint_sha256": payload.get("checkpoint_sha256"),
                              "checkpoint_verification_required": True,
                              "requires_verified_artist_tool_capability": True,
                              "approved_for_auto_execution": False})
    inspection.update({"proposals": proposals, "max_iterations": max_iterations,
                       "attempts_used": attempts, "attempts_remaining": max_iterations - attempts,
                       "stopped_reason": stop_reason, "revision_engine_executed_edits": False,
                       "checkpoint_supplied": "checkpoint_sha256" in payload,
                       "checkpoint_verified": False,
                       "artist_tool_registered_by_dispatcher": False})
    return inspection


def execute(operation, payload, context):
    request = validate(operation, payload)
    observation = _inspect(operation, request, context)
    if operation == "omega.quality.revise_plan":
        return _plan(observation, request, context)
    return observation


def audit(operation, payload, context):
    """Re-evaluate the native scene. Never creates objects or changes settings."""
    return execute(operation, payload, context)
