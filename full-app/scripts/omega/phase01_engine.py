# SPDX-License-Identifier: GPL-2.0-or-later
"""RENDER OMEGA P01: real Blender engine + reversible viewport diagnostics.

P10 may register these exact operations. No generic bpy operator, source-path
argument, shell, network, addon installation or external filesystem access.
Importing this module never assumes bpy is available on a host test runner.
"""
import json
import math

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.engine.diagnose", "omega.engine.viewport_profile")
_BACKUP = "_omega_p01_viewport_before"
_SUPPORTED_AA = frozenset(("OFF", "FXAA", "8", "16", "32"))


def _finite(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("INVALID_VIEWPORT_FINITE_NUMBER")
    return float(value)


def validate(operation, payload):
    if operation not in OPERATION_NAMES:
        raise ValueError("UNKNOWN_OMEGA_ENGINE_OPERATION")
    if not isinstance(payload, dict):
        raise ValueError("INVALID_ARGUMENTS")
    if operation == "omega.engine.diagnose":
        if set(payload) - {"max_objects"}:
            raise ValueError("UNKNOWN_ENGINE_DIAGNOSTIC_FIELD")
        limit = payload.get("max_objects", 32)
        if type(limit) is not int or not 1 <= limit <= 128:
            raise ValueError("INVALID_DIAGNOSTIC_LIMIT")
        return {"max_objects": limit}

    allowed = {"mode", "clip_start", "clip_end", "xray", "wire_overlay", "anti_alias"}
    if set(payload) - allowed:
        raise ValueError("UNKNOWN_VIEWPORT_SETTING")
    mode = payload.get("mode", "inspect")
    if mode not in ("inspect", "apply", "restore"):
        raise ValueError("INVALID_VIEWPORT_PROFILE_MODE")
    if mode != "apply" and set(payload) - {"mode"}:
        raise ValueError("INSPECT_OR_RESTORE_ACCEPTS_NO_MUTATIONS")
    data = {"mode": mode}
    if mode == "apply":
        if ("clip_start" in payload) != ("clip_end" in payload):
            raise ValueError("VIEWPORT_CLIP_RANGE_MUST_BE_PAIRED")
        if "clip_start" in payload:
            start = _finite(payload["clip_start"], 1e-7, 1e8)
            end = _finite(payload["clip_end"], start + 1e-7, 1e11)
            if end / start > 100000:
                raise ValueError("VIEWPORT_DEPTH_RATIO_EXCESSIVE")
            data["clip_start"], data["clip_end"] = start, end
        for flag in ("xray", "wire_overlay"):
            if flag in payload:
                if type(payload[flag]) is not bool:
                    raise ValueError("INVALID_VIEWPORT_TOGGLE")
                data[flag] = payload[flag]
        if "anti_alias" in payload:
            if type(payload["anti_alias"]) is not str or payload["anti_alias"] not in _SUPPORTED_AA:
                raise ValueError("INVALID_VIEWPORT_AA")
            data["anti_alias"] = payload["anti_alias"]
        if len(data) == 1:
            raise ValueError("VIEWPORT_NO_SETTINGS_REQUESTED")
    return data


def _native(context):
    blender = context.get("bpy") if isinstance(context, dict) else None
    if blender is None:
        try:
            import bpy as blender
        except ImportError as error:
            raise RuntimeError("NATIVE_BLENDER_BPY_REQUIRED") from error
    return blender


def _scene(context, blender):
    scene = context.get("scene") if isinstance(context, dict) else None
    if scene is None:
        scene = getattr(blender.context, "scene", None)
    if scene is None:
        raise RuntimeError("NATIVE_SCENE_UNAVAILABLE")
    return scene


def _areas(blender):
    window = getattr(blender.context, "window", None)
    if window is None or getattr(window, "screen", None) is None:
        return []
    screen = window.screen
    return [(i, area, area.spaces.active) for i, area in enumerate(screen.areas)
            if area.type == "VIEW_3D"]


def _snapshot(blender):
    entries = []
    for index, area, space in _areas(blender):
        entries.append({
            "index": index,
            "clip_start": float(space.clip_start),
            "clip_end": float(space.clip_end),
            "xray": bool(space.shading.show_xray),
            "wire_overlay": bool(space.overlay.show_wireframes),
            "precision_ratio": float(space.clip_end / space.clip_start),
        })
    return entries


def _renderer(scene):
    render = scene.render
    return {
        "engine": str(render.engine),
        "resolution_x": int(render.resolution_x),
        "resolution_y": int(render.resolution_y),
        "resolution_percentage": int(render.resolution_percentage),
        "fps": int(render.fps),
        "fps_base": float(render.fps_base),
    }


def _aa(blender):
    system = getattr(getattr(blender.context, "preferences", None), "system", None)
    return getattr(system, "viewport_aa", None)


def _check_supported_aa(blender, requested):
    system = getattr(getattr(blender.context, "preferences", None), "system", None)
    if system is None or not hasattr(system, "viewport_aa"):
        raise ValueError("VIEWPORT_AA_UNSUPPORTED_BY_NATIVE_BLENDER")
    try:
        permitted = {item.identifier for item in
                     system.bl_rna.properties["viewport_aa"].enum_items}
    except (AttributeError, KeyError, TypeError) as error:
        raise ValueError("VIEWPORT_AA_ENUM_UNAVAILABLE") from error
    if requested not in permitted:
        raise ValueError("VIEWPORT_AA_UNSUPPORTED_BY_NATIVE_BLENDER")
    return system


def _suspects(scene, limit):
    duplicate = {}
    nonuniform = []
    count = 0
    for ob in scene.objects:
        if count >= limit:
            break
        count += 1
        if ob.type != "MESH":
            continue
        scale = tuple(float(x) for x in ob.scale)
        if max(scale) - min(scale) > 0.0001:
            nonuniform.append(ob.name)
        try:
            matrix = tuple(round(float(v), 6) for row in ob.matrix_world for v in row)
        except (TypeError, AttributeError):
            continue
        key = (ob.data.name, matrix)
        duplicate.setdefault(key, []).append(ob.name)
    return {
        "nonuniform_scale_candidates": nonuniform[:16],
        "identical_mesh_transform_candidates":
            [names[:4] for names in duplicate.values() if len(names) > 1][:16],
        "scanned_objects": count,
        "candidate_scan_is_not_proof_of_z_fighting": True,
    }


def _receipt(op, scene, payload):
    result = {
        "operation": op,
        "state": "succeeded",
        "scene": scene.name,
        "source_revision": None,
        "created": [],
        "artifact": {"kind": "none", "sha256": None},
        "native_execution_verified": True,
        "visual_quality_verified": False,
        "quality_reduced": False,
        "render_quality_unchanged": True,
        "warnings": [],
    }
    result.update(payload)
    return result


def execute(operation, payload, context):
    p = validate(operation, payload)
    blender = _native(context)
    scene = _scene(context, blender)
    before_render = _renderer(scene)

    if operation == "omega.engine.diagnose":
        info = {
            "blender_version": getattr(blender.app, "version_string", "unknown"),
            "native_bpy_present": True,
            "blender_background": bool(getattr(blender.app, "background", False)),
            "visible_3d_editor_count": len(_areas(blender)),
            "viewports": _snapshot(blender),
            "viewport_aa": _aa(blender),
            "render": before_render,
            "mesh_warnings": _suspects(scene, p["max_objects"]),
            "android_vulkan_driver_verified": False,
            "first_vulkan_pixel_observed": False,
        }
        return _receipt(operation, scene, info)

    mode = p["mode"]
    areas = _areas(blender)
    if not areas:
        if mode == "inspect":
            return _receipt(operation, scene, {
                "viewports": [], "mode": mode, "native_viewport_available": False,
                "warnings": ["NO_NATIVE_VIEW3D_WINDOW_IN_CURRENT_CONTEXT"]})
        raise ValueError("NATIVE_VIEWPORT_NOT_OPEN")
    previous = _snapshot(blender)
    if mode == "apply":
        if scene.get(_BACKUP) is not None:
            raise ValueError("VIEWPORT_PROFILE_ALREADY_ACTIVE_RESTORE_FIRST")
        system = _check_supported_aa(blender, p["anti_alias"]) if "anti_alias" in p else None
        backup = {"views": previous, "aa": _aa(blender)}
        # Storing original state in .blend makes a deliberate restore possible
        # even after saving/reopening or Activity recreation.
        scene[_BACKUP] = json.dumps(backup, sort_keys=True)
        try:
            for _, area, space in areas:
                if "clip_start" in p:
                    space.clip_start = p["clip_start"]
                    space.clip_end = p["clip_end"]
                if "xray" in p:
                    space.shading.show_xray = p["xray"]
                if "wire_overlay" in p:
                    space.overlay.show_wireframes = p["wire_overlay"]
                area.tag_redraw()
            if system is not None:
                system.viewport_aa = p["anti_alias"]
        except Exception:
            _restore(blender, scene, areas, backup)
            del scene[_BACKUP]
            raise
    elif mode == "restore":
        raw = scene.get(_BACKUP)
        if not isinstance(raw, str):
            raise ValueError("NO_VIEWPORT_BACKUP_AVAILABLE")
        backup = json.loads(raw)
        _restore(blender, scene, areas, backup)
        del scene[_BACKUP]
    after = _snapshot(blender)
    if _renderer(scene) != before_render:
        raise RuntimeError("VIEWPORT_OPERATION_ALTERED_RENDER_SETTINGS")
    return _receipt(operation, scene, {
        "mode": mode,
        "native_viewport_available": True,
        "viewports_before": previous,
        "viewports_after": after,
        "profile_reversible": mode in ("apply", "restore"),
        "viewport_aa": _aa(blender),
        "original_mesh_data_modified": False,
        "warnings": ["VIEWPORT_CLIP_CHANGES_CAN_HIDE_DISTANT_OBJECTS"]
            if mode == "apply" and "clip_start" in p else [],
    })


def _restore(blender, scene, areas, backup):
    snapshots = {item["index"]: item for item in backup.get("views", [])}
    for index, area, space in areas:
        item = snapshots.get(index)
        if item is None:
            continue
        space.clip_start = item["clip_start"]
        space.clip_end = item["clip_end"]
        space.shading.show_xray = item["xray"]
        space.overlay.show_wireframes = item["wire_overlay"]
        area.tag_redraw()
    if backup.get("aa") is not None:
        system = _check_supported_aa(blender, backup["aa"])
        system.viewport_aa = backup["aa"]


def audit(operation, payload, context):
    p = validate(operation, payload)
    if operation == "omega.engine.viewport_profile":
        return execute(operation, {"mode": "inspect"}, context)
    return execute(operation, p, context)
