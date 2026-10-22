# SPDX-License-Identifier: GPL-2.0-or-later
"""Phase 11: bounded, independently testable Blender-main-thread artist tools.

No startup registration, filesystem traversal, remote Python, UI event synthesis, or
shared bridge hooks. P10 may dispatch ONLY the two canonical operations here.

The implemented edit tool is explicitly a native BMesh *edit-mode surface edit*,
not Blender's Sculpt brush engine. True SCULPT brush_stroke needs a foreground
VIEW_3D context and is intentionally *not* advertised by this initial slice.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import threading

try:
    import bpy
except ImportError:  # importable for pure contract/unit tests
    bpy = None

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.artist.inspect_ui", "omega.artist.execute_tool")
_TOOLS = {
    "object.select": ("OBJECT", "selection_active"),
    "object.mode_set": ("OBJECT", "mode_changed"),  # source mode may be EDIT too
    "mesh.edit_surface_stroke": ("EDIT", "evaluated_mesh_changed"),
    "modifier.add": ("OBJECT", "modifier_present"),
}
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_JOB = re.compile(r"^[a-f0-9]{32}$")
_MAX_VERTICES_PER_EDIT = 200_000  # reject safely; never simplify user mesh
_MAX_SCENE_OBJECTS = 10_000
_MAX_RECEIPTS = 24
_RECEIPTS_KEY = "omega_p11_completed_jobs"


def _fail(code):
    raise ValueError(code)


def _keys(obj, allowed, required=()):
    if type(obj) is not dict or (obj.keys() - set(allowed)) or not set(required).issubset(obj):
        _fail("INVALID_ARGUMENTS")


def _name(value):
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        _fail("INVALID_ARGUMENTS")
    return value


def _float(value, lo, hi):
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        _fail("INVALID_ARGUMENTS")
    return float(value)


def _vec(value, limit):
    if type(value) is not list or len(value) != 3:
        _fail("INVALID_ARGUMENTS")
    return tuple(_float(v, -limit, limit) for v in value)


def validate(operation: str, payload: dict) -> dict:
    """Pure, strict and small allowlist. Never mutate / import Blender context."""
    if operation not in OPERATION_NAMES:
        _fail("UNSUPPORTED_NATIVE_FEATURE")
    if operation == "omega.artist.inspect_ui":
        _keys(payload, ("target",))
        return {"target": _name(payload["target"]) if "target" in payload else None}

    _keys(payload, ("tool", "target", "expected_mode", "expected_scene_revision",
                    "parameters", "postcondition"),
          ("tool", "target", "expected_mode", "expected_scene_revision",
           "parameters", "postcondition"))
    tool = payload["tool"]
    if type(tool) is not str or tool not in _TOOLS:
        _fail("UNSUPPORTED_NATIVE_FEATURE")
    target = _name(payload["target"])
    mode = payload["expected_mode"]
    if type(mode) is not str or mode not in ("OBJECT", "EDIT"):
        _fail("INVALID_ARGUMENTS")
    if tool != "object.mode_set" and mode != _TOOLS[tool][0]:
        _fail("INVALID_ARGUMENTS")
    if type(payload["postcondition"]) is not str or payload["postcondition"] != _TOOLS[tool][1]:
        _fail("INVALID_ARGUMENTS")
    rev = payload["expected_scene_revision"]
    if type(rev) is not str or _SHA256.fullmatch(rev) is None:
        _fail("INVALID_ARGUMENTS")
    p = payload["parameters"]
    if tool == "object.select":
        _keys(p, ())
    elif tool == "object.mode_set":
        _keys(p, ("mode",), ("mode",))
        if p["mode"] not in ("OBJECT", "EDIT") or p["mode"] == mode:
            _fail("INVALID_ARGUMENTS")
    elif tool == "mesh.edit_surface_stroke":
        _keys(p, ("radius", "strength", "direction", "samples"),
              ("radius", "strength", "direction", "samples"))
        _float(p["radius"], 0.001, 100.0)
        _float(p["strength"], 0.000001, 2.0)
        d = _vec(p["direction"], 1.0)
        if sum(v*v for v in d) < 1e-12:
            _fail("INVALID_ARGUMENTS")
        samples = p["samples"]
        if type(samples) is not list or not 1 <= len(samples) <= 32:
            _fail("INVALID_ARGUMENTS")
        for point in samples:
            _vec(point, 10_000.0)
    else:  # modifier.add
        _keys(p, ("kind", "name", "width", "segments", "levels"), ("kind", "name"))
        if p["kind"] not in ("BEVEL", "SUBSURF"):
            _fail("UNSUPPORTED_NATIVE_FEATURE")
        _name(p["name"])
        if p["kind"] == "BEVEL":
            if set(p) - {"kind", "name", "width", "segments"}:
                _fail("INVALID_ARGUMENTS")
            _float(p.get("width", 0.04), 0.00001, 10.0)
            if type(p.get("segments", 3)) is not int or not 1 <= p.get("segments", 3) <= 12:
                _fail("INVALID_ARGUMENTS")
        else:
            if set(p) - {"kind", "name", "levels"}:
                _fail("INVALID_ARGUMENTS")
            if type(p.get("levels", 2)) is not int or not 0 <= p.get("levels", 2) <= 5:
                _fail("INVALID_ARGUMENTS")
    return {"tool": tool, "target": target, "expected_mode": mode,
            "expected_scene_revision": rev, "parameters": p,
            "postcondition": payload["postcondition"]}


def _native(context):
    if bpy is None:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE: bpy not installed")
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("BLENDER_MAIN_THREAD_REQUIRED")
    if type(context) is not dict or "scene" not in context or not isinstance(context["scene"], bpy.types.Scene):
        _fail("INVALID_NATIVE_CONTEXT")
    scene = context["scene"]
    if bpy.context.scene != scene:
        _fail("SCENE_CONTEXT_CONFLICT")
    # This phase cannot open other projects. When P10 supplies the app's canonical
    # root, require an existing saved .blend inside that owned root, not a path
    # supplied by the remote payload. Headless Blender fixtures also obey this.
    root = context.get("production_root")
    if root is None or type(root) not in (str, Path):
        _fail("MISSING_REFERENCE")
    try:
        base = Path(root).resolve(strict=True)
        path = Path(bpy.data.filepath).resolve(strict=True)
        if path.suffix.lower() != ".blend" or os.path.commonpath((str(base), str(path))) != str(base):
            _fail("OWNER_PROJECT_SCOPE_REQUIRED")
    except (OSError, ValueError) as ex:
        # Preserve our typed failure, don't leak the owner filesystem path.
        if isinstance(ex, ValueError) and str(ex) == "OWNER_PROJECT_SCOPE_REQUIRED":
            raise
        _fail("OWNER_PROJECT_SCOPE_REQUIRED")
    return scene


def _mesh_coords(obj):
    """Read REAL Blender mesh data, including unsaved EDIT mode BMesh."""
    if obj.type != "MESH":
        _fail("TARGET_OBJECT_WRONG_TYPE")
    if obj.mode == "EDIT":
        import bmesh
        mesh = bmesh.from_edit_mesh(obj.data)
        mesh.verts.ensure_lookup_table()
        mesh.faces.ensure_lookup_table()
        coords = [tuple(v.co) for v in mesh.verts]
        # BMesh indices may be -1 until explicitly populated.
        mesh.verts.index_update()
        faces = [tuple(v.index for v in face.verts) for face in mesh.faces]
        return coords, faces, len(mesh.edges)
    return ([tuple(v.co) for v in obj.data.vertices],
            [tuple(p.vertices) for p in obj.data.polygons], len(obj.data.edges))


def _mesh_digest(obj):
    coords, faces, edges = _mesh_coords(obj)
    h = hashlib.sha256()
    h.update(struct.pack("<QQQ", len(coords), edges, len(faces)))
    for v in coords:
        for c in v:
            h.update(struct.pack("<d", round(float(c), 8)))
    for face in faces:
        h.update(struct.pack("<I", len(face)))
        for index in face:
            h.update(struct.pack("<I", index))
    return h.hexdigest(), len(coords), len(faces)


def _scene_revision(scene):
    """Deterministic native object/mesh/transform/mode fingerprint, not a file SHA.

    Deliberately includes real geometry so external edits invalidate expected revision.
    Doesn't claim to hash arbitrary third-party add-on state or image pixels.
    """
    if len(scene.objects) > _MAX_SCENE_OBJECTS:
        _fail("OUT_OF_MEMORY_PAUSED")
    h = hashlib.sha256()
    h.update(scene.name.encode("utf-8"))
    h.update(struct.pack("<i", scene.frame_current))
    active = bpy.context.view_layer.objects.active
    h.update((active.name if active else "-").encode("utf-8"))
    for obj in sorted(scene.objects, key=lambda x: x.name):
        h.update(obj.name.encode("utf-8"))
        h.update(obj.type.encode("ascii"))
        h.update(obj.mode.encode("ascii"))
        h.update(b"1" if obj.select_get() else b"0")
        for row in obj.matrix_world:
            for x in row:
                h.update(struct.pack("<d", round(float(x), 8)))
        if obj.type == "MESH":
            h.update(_mesh_digest(obj)[0].encode("ascii"))
        for m in obj.modifiers:
            h.update(m.name.encode("utf-8"))
            h.update(m.type.encode("ascii"))
            if m.type == "BEVEL":
                h.update(struct.pack("<di", float(m.width), int(m.segments)))
            elif m.type == "SUBSURF":
                h.update(struct.pack("<ii", int(m.levels), int(m.render_levels)))
    return h.hexdigest()


def _target(scene, name):
    obj = scene.objects.get(name)
    if obj is None:
        _fail("MISSING_REFERENCE")
    return obj


def _cancel(context):
    flag = context.get("cancellation_requested", False)
    if callable(flag):
        flag = flag()
    if flag:
        raise RuntimeError("CANCELLED_AT_SAFE_BOUNDARY")


def _receipt(operation, scene, before, after, *, target=None, detail=None):
    return {"operation": operation, "state": "succeeded", "scene": scene.name,
            "source_revision": before, "new_scene_revision": after,
            "created": [], "artifact": {"kind": "none", "sha256": None},
            "native_execution_verified": True, "visual_quality_verified": False,
            "quality_reduced": False, "target": target,
            "detail": detail or {}, "warnings": [
                "Revision is a native object/mesh fingerprint, not a full .blend SHA-256; "+
                "project save and Android visual verification are separate gates."]}


def _inspect(scene, target_name=None):
    active = bpy.context.view_layer.objects.active
    window = bpy.context.window
    areas = []
    if window is not None and window.screen is not None:
        for area in window.screen.areas:
            entry = {"type": area.type, "width": int(area.width), "height": int(area.height)}
            if area.type == "VIEW_3D":
                space = area.spaces.active
                region = getattr(space, "region_3d", None)
                if region is not None:
                    entry["perspective"] = region.view_perspective
                    entry["view_matrix"] = [[float(x) for x in row] for row in region.view_matrix]
                    entry["view_distance"] = float(region.view_distance)
            areas.append(entry)
    sculpt = getattr(getattr(bpy.context, "tool_settings", None), "sculpt", None)
    brush = getattr(sculpt, "brush", None)
    detail = {"blender_version": bpy.app.version_string,
              "active_object": active.name if active else None,
              "active_mode": active.mode if active else "OBJECT",
              "selected_objects": sorted(o.name for o in scene.objects if o.select_get()),
              "workspace": bpy.context.workspace.name if bpy.context.workspace else None,
              "areas": areas,
              "sculpt_brush": brush.name if brush else None,
              "headless": bool(bpy.app.background),
              "viewport_capture_available": False}
    if target_name:
        ob = _target(scene, target_name)
        detail["target_type"] = ob.type
        detail["target_mode"] = ob.mode
        detail["target_modifiers"] = [{"name": m.name, "type": m.type} for m in ob.modifiers]
        if ob.type == "MESH":
            sha, verts, faces = _mesh_digest(ob)
            detail["mesh_sha256"] = sha
            detail["vertices"] = verts
            detail["faces"] = faces
    return detail


def _execute_select(scene, obj):
    if bpy.context.view_layer.objects.active and bpy.context.view_layer.objects.active.mode != "OBJECT":
        _fail("MODE_CONFLICT")
    old_active = bpy.context.view_layer.objects.active
    old_selected = [o for o in scene.objects if o.select_get()]
    try:
        for o in old_selected:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        if bpy.context.view_layer.objects.active != obj or not obj.select_get():
            raise RuntimeError("NATIVE_POSTCONDITION_FAILED")
    except Exception:
        obj.select_set(False)
        for o in old_selected:
            o.select_set(True)
        bpy.context.view_layer.objects.active = old_active
        raise
    return {"previous_active": old_active.name if old_active else None,
            "new_active": obj.name, "selected": True,
            "touch_event_observed": False}


def _execute_mode_set(obj, mode):
    if bpy.context.view_layer.objects.active != obj:
        _fail("TARGET_MUST_BE_ACTIVE")
    old = obj.mode
    if old == mode:
        _fail("INVALID_ARGUMENTS")
    try:
        result = bpy.ops.object.mode_set(mode=mode)
        if "FINISHED" not in result or obj.mode != mode:
            raise RuntimeError("NATIVE_POSTCONDITION_FAILED")
    except Exception:
        if obj.mode != old:
            bpy.ops.object.mode_set(mode=old)
        raise
    return {"old_mode": old, "new_mode": obj.mode,
            "touch_event_observed": False}


def _execute_surface_stroke(obj, p, context):
    """Apply bounded smooth falloff to true BMesh vertices in Blender edit mode.

    Coordinates are object-local mesh coordinates. This is NOT a fabricated
    SCULPT_MODE brush operator. Exact changed-vertex count and mesh digests prove
    the edit; unchanged influence is an error. Restores coordinates on failure.
    """
    if obj.type != "MESH" or obj.mode != "EDIT" or bpy.context.view_layer.objects.active != obj:
        _fail("TARGET_MODE_OR_TYPE_MISMATCH")
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    if len(bm.verts) > _MAX_VERTICES_PER_EDIT:
        _fail("OUT_OF_MEMORY_PAUSED")
    before, _, _ = _mesh_digest(obj)
    previous = [(v, v.co.copy()) for v in bm.verts]
    radius = float(p["radius"])
    strength = float(p["strength"])
    dx, dy, dz = p["direction"]
    mag = math.sqrt(dx*dx + dy*dy + dz*dz)
    dx, dy, dz = dx/mag, dy/mag, dz/mag
    touched = set()
    try:
        for sx, sy, sz in p["samples"]:
            _cancel(context)
            for i, v in enumerate(bm.verts):
                cx, cy, cz = v.co
                d = math.sqrt((cx-sx)**2 + (cy-sy)**2 + (cz-sz)**2)
                if d < radius:
                    q = d/radius
                    weight = (1-q*q)**2
                    move = strength*weight
                    if move > 1e-12:
                        v.co.x += dx*move
                        v.co.y += dy*move
                        v.co.z += dz*move
                        touched.add(i)
        if not touched:
            raise RuntimeError("NATIVE_POSTCONDITION_FAILED: zero brush influence")
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        after, _, _ = _mesh_digest(obj)
        if before == after:
            raise RuntimeError("NATIVE_POSTCONDITION_FAILED: unchanged geometry")
    except Exception:
        for v, co in previous:
            v.co = co
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        raise
    return {"method": "native_bmesh_edit_surface_stroke", "sculpt_brush_operator_used": False,
            "old_mesh_sha256": before, "new_mesh_sha256": after,
            "changed_vertex_count": len(touched), "sample_count": len(p["samples"]),
            "touch_event_observed": False}


def _execute_modifier(obj, p):
    if obj.type != "MESH" or obj.mode != "OBJECT":
        _fail("TARGET_MODE_OR_TYPE_MISMATCH")
    if obj.modifiers.get(p["name"]) is not None:
        _fail("CHECKPOINT_CONFLICT")
    modifier = obj.modifiers.new(p["name"], p["kind"])
    try:
        if p["kind"] == "BEVEL":
            modifier.width = float(p.get("width", 0.04))
            modifier.segments = p.get("segments", 3)
        else:
            modifier.levels = p.get("levels", 2)
            # Do not reduce final render subdivisions: set a matching or higher render level.
            modifier.render_levels = max(modifier.render_levels, modifier.levels)
        found = obj.modifiers.get(p["name"])
        if found is None or found.type != p["kind"]:
            raise RuntimeError("NATIVE_POSTCONDITION_FAILED")
    except Exception:
        obj.modifiers.remove(modifier)
        raise
    return {"created_modifier": modifier.name, "kind": modifier.type,
            "viewport_levels": modifier.levels if modifier.type == "SUBSURF" else None,
            "render_levels": modifier.render_levels if modifier.type == "SUBSURF" else None,
            "touch_event_observed": False}


def _load_receipts(scene):
    try:
        rows = json.loads(scene.get(_RECEIPTS_KEY, "[]"))
        return rows if isinstance(rows, list) else []
    except (ValueError, TypeError):
        # A corrupt journal must never permit a destructive command replay.
        _fail("CHECKPOINT_CONFLICT")


def execute(operation: str, payload: dict, context: dict) -> dict:
    parsed = validate(operation, payload)
    scene = _native(context)
    if operation == "omega.artist.inspect_ui":
        return _receipt(operation, scene, _scene_revision(scene), _scene_revision(scene),
                        target=parsed["target"], detail=_inspect(scene, parsed["target"]))
    job = context.get("job_id")
    if job is not None and (type(job) is not str or _JOB.fullmatch(job) is None):
        _fail("INVALID_NATIVE_CONTEXT")
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    before = _scene_revision(scene)
    if job:
        for prior in _load_receipts(scene):
            if prior.get("job_id") == job:
                if prior.get("request_sha256") != fingerprint or prior.get("scene_revision") != before:
                    _fail("CHECKPOINT_CONFLICT")
                outcome = prior["receipt"].copy()
                outcome["replayed"] = True
                return outcome
    if before != parsed["expected_scene_revision"]:
        _fail("CHECKPOINT_CONFLICT")
    obj = _target(scene, parsed["target"])
    active = bpy.context.view_layer.objects.active
    current_mode = active.mode if active else "OBJECT"
    if current_mode != parsed["expected_mode"]:
        _fail("MODE_CONFLICT")
    if operation != "omega.artist.execute_tool":
        _fail("UNSUPPORTED_NATIVE_FEATURE")
    if context.get("dry_run", False):
        return {"operation": operation, "state": "validated", "scene": scene.name,
                "source_revision": before, "native_execution_verified": False,
                "quality_reduced": False, "would_target": obj.name}
    _cancel(context)
    tool = parsed["tool"]
    if tool == "object.select":
        detail = _execute_select(scene, obj)
    elif tool == "object.mode_set":
        detail = _execute_mode_set(obj, parsed["parameters"]["mode"])
    elif tool == "mesh.edit_surface_stroke":
        detail = _execute_surface_stroke(obj, parsed["parameters"], context)
    else:
        detail = _execute_modifier(obj, parsed["parameters"])
    after = _scene_revision(scene)
    if before == after:
        raise RuntimeError("NATIVE_POSTCONDITION_FAILED: no state change")
    outcome = _receipt(operation, scene, before, after, target=obj.name, detail=detail)
    if "created_modifier" in detail:
        outcome["created"] = [obj.name + "/" + detail["created_modifier"]]
    if job:
        rows = _load_receipts(scene)
        rows.append({"job_id": job, "request_sha256": fingerprint,
                     "scene_revision": after, "receipt": outcome})
        scene[_RECEIPTS_KEY] = json.dumps(rows[-_MAX_RECEIPTS:], sort_keys=True)
    return outcome


def audit(operation: str, payload: dict, context: dict) -> dict:
    parsed = validate(operation, payload)
    scene = _native(context)
    name = parsed.get("target")
    actual = _scene_revision(scene)
    result = _receipt(operation, scene, actual, actual, target=name,
                      detail=_inspect(scene, name))
    if operation == "omega.artist.execute_tool":
        result["detail"]["expected_revision_matches"] = (
            parsed["expected_scene_revision"] == actual)
    return result
