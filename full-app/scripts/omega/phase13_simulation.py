# SPDX-License-Identifier: GPL-2.0-or-later
"""Phase 13: bounded real-bpy rigid-body simulation and verifiable sample cache.

No bpy import or filesystem access at module import time. The integration layer
must call execute/audit on Blender's main thread with a trusted app-owned root.
SAMPLED_NATIVE_PHYSICS is an evaluated simulation record, NOT a Blender baked
point cache. NATIVE_POINT_CACHE never silently falls back to sampled output.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.simulation.bake", "omega.simulation.inspect_cache")
_CACHE_SCHEMA = "omega-rigidbody-frames-v1"
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_JOB = re.compile(r"^[0-9a-f]{32}$")
_MAX_FRAMES = 120
_MAX_VERTICES = 250000


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("INVALID_ARGUMENTS")


def _finite(value, minimum, maximum):
    if type(value) not in (float, int) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("INVALID_ARGUMENTS")
    return float(value)


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _name(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _hash(value):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _bool(value):
    if type(value) is not bool:
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def validate(operation: str, payload: dict) -> dict:
    """Pure allowlisted request validation. No paths or generic bpy operators."""
    if operation not in OPERATION_NAMES:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    if operation == OPERATION_NAMES[1]:
        _fields(payload, ("expected_source_revision",))
        return ({"expected_source_revision": _hash(payload["expected_source_revision"])}
                if "expected_source_revision" in payload else {})
    _fields(payload, ("objects", "frame_start", "frame_end", "expected_scene_revision",
                      "cache_mode", "save_blend_copy"),
            ("objects", "frame_start", "frame_end", "expected_scene_revision"))
    objects = payload["objects"]
    if not isinstance(objects, list) or not 2 <= len(objects) <= 16:
        raise ValueError("INVALID_ARGUMENTS")
    result = []
    for entry in objects:
        _fields(entry, ("name", "role", "mass", "friction", "restitution", "shape", "collision_group"),
                ("name", "role"))
        role = entry["role"]
        if role not in ("ACTIVE", "PASSIVE"):
            raise ValueError("INVALID_ARGUMENTS")
        shape = entry.get("shape", "CONVEX_HULL" if role == "ACTIVE" else "BOX")
        if shape not in ("BOX", "CONVEX_HULL", "SPHERE"):
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
        mass = _finite(entry.get("mass", 1 if role == "ACTIVE" else 0), 0, 10000)
        if role == "ACTIVE" and mass < 0.01 or role == "PASSIVE" and mass != 0:
            raise ValueError("INVALID_ARGUMENTS")
        result.append({"name": _name(entry["name"]), "role": role, "mass": mass,
                       "shape": shape, "friction": _finite(entry.get("friction", 0.65), 0, 1),
                       "restitution": _finite(entry.get("restitution", 0.05), 0, 1),
                       "collision_group": _integer(entry.get("collision_group", 0), 0, 19)})
    names = [o["name"] for o in result]
    if len(set(names)) != len(names) or not {"ACTIVE", "PASSIVE"} <= {o["role"] for o in result}:
        raise ValueError("INVALID_ARGUMENTS")
    if not ({o["collision_group"] for o in result if o["role"] == "ACTIVE"} &
            {o["collision_group"] for o in result if o["role"] == "PASSIVE"}):
        raise ValueError("INVALID_ARGUMENTS")
    first = _integer(payload["frame_start"], 1, 10000)
    last = _integer(payload["frame_end"], first, 10000)
    if last - first + 1 < 24 or last - first + 1 > _MAX_FRAMES:
        raise ValueError("INVALID_ARGUMENTS")
    mode = payload.get("cache_mode", "NATIVE_POINT_CACHE")
    if mode not in ("NATIVE_POINT_CACHE", "SAMPLED_NATIVE_PHYSICS"):
        raise ValueError("INVALID_ARGUMENTS")
    return {"objects": result, "frame_start": first, "frame_end": last,
            "expected_scene_revision": _hash(payload["expected_scene_revision"]),
            "cache_mode": mode, "save_blend_copy": _bool(payload.get("save_blend_copy", True))}


def _require_native(context):
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("BLENDER_MAIN_THREAD_REQUIRED")
    try:
        import bpy
    except ImportError as exc:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE") from exc
    scene = context.get("scene") if isinstance(context, dict) else None
    if scene is None or not isinstance(scene, bpy.types.Scene):
        raise ValueError("INVALID_NATIVE_SCENE")
    if bpy.context.scene != scene:
        raise ValueError("BLENDER_SCENE_CONTEXT_MISMATCH")
    if context.get("dry_run", False):
        raise ValueError("DRY_RUN_MUST_USE_VALIDATE")
    return bpy, scene


def _cache_directory(context, create=False):
    ident = context.get("job_id")
    root = context.get("production_root")
    if not isinstance(ident, str) or not _JOB.fullmatch(ident):
        raise ValueError("INVALID_JOB_ID")
    if not isinstance(root, (str, os.PathLike)) or not Path(root).is_absolute():
        raise ValueError("PRODUCTION_ROOT_UNAVAILABLE")
    root = Path(root).resolve(strict=True)
    directory = root / "omega-simulation"
    if directory.is_symlink():
        raise ValueError("CACHE_OUTSIDE_SCOPE")
    target = directory / ident
    if target.is_symlink() or target.resolve().parent != directory.resolve():
        raise ValueError("CACHE_OUTSIDE_SCOPE")
    if create:
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
    return target


def _sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sync_dir(directory):
    try:
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass  # Not available on every Android filesystem.


def _write_json(path, value):
    blob = _canonical(value) + b"\n"
    temporary = path.with_name(path.name + ".writing")
    if temporary.is_symlink() or path.is_symlink():
        raise ValueError("CACHE_OUTSIDE_SCOPE")
    with temporary.open("wb") as out:
        out.write(blob)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, path)
    _sync_dir(path.parent)
    return hashlib.sha256(blob).hexdigest()


def _read_json(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 262144:
        raise ValueError("MISSING_REFERENCE")
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError("CACHE_CORRUPT") from exc


def _scene_revision(scene, specs):
    """Content fingerprint of source meshes and fixed physics settings, not UI pose."""
    h = hashlib.sha256()
    h.update(_canonical({"scene": scene.name, "gravity": [float(x) for x in scene.gravity],
                          "frame_start": scene.frame_start, "frame_end": scene.frame_end,
                          "use_gravity": scene.use_gravity,
                          "world_solver": (None if scene.rigidbody_world is None else {
                              "substeps": scene.rigidbody_world.substeps_per_frame,
                              "iterations": scene.rigidbody_world.solver_iterations})}))
    total = 0
    for entry in sorted(specs, key=lambda o: o["name"]):
        ob = scene.objects.get(entry["name"])
        if ob is None or ob.type != "MESH":
            raise ValueError("MISSING_REFERENCE")
        total += len(ob.data.vertices)
        if total > _MAX_VERTICES:
            raise ValueError("OUT_OF_MEMORY_PAUSED")
        if (ob.library or ob.data.library or ob.animation_data is not None or
                ob.parent is not None or len(ob.modifiers) or len(ob.constraints)):
            raise ValueError("CHECKPOINT_CONFLICT")
        body = ob.rigid_body
        h.update(_canonical({"name": ob.name, "loc": list(ob.location),
                             "rot": list(ob.rotation_euler), "scale": list(ob.scale),
                             "vertices": len(ob.data.vertices), "polygons": len(ob.data.polygons),
                             "body": (None if body is None else {
                                 "type": body.type, "shape": body.collision_shape,
                                 "mass": body.mass, "friction": body.friction,
                                 "restitution": body.restitution})}))
        for v in ob.data.vertices:
            h.update(_canonical([float(n) for n in v.co]))
        for poly in ob.data.polygons:
            h.update(_canonical([int(n) for n in poly.vertices]))
    return h.hexdigest()


def scene_revision(scene, object_names):
    """Read-only revision for a caller preparing an expected_scene_revision."""
    return _scene_revision(scene, [{"name": _name(name)} for name in object_names])


def _cancelled(context):
    status = context.get("cancellation_requested", False)
    return bool(status() if callable(status) else status)


def _verify_entries(directory, manifest):
    files = manifest.get("frames")
    if not isinstance(files, list) or len(files) > _MAX_FRAMES:
        raise ValueError("CACHE_CORRUPT")
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"frame", "file", "sha256"}:
            raise ValueError("CACHE_CORRUPT")
        frame = entry["frame"]
        if type(frame) is not int or entry["file"] != "frame_%06d.json" % frame:
            raise ValueError("CACHE_CORRUPT")
        file_path = directory / entry["file"]
        if file_path.is_symlink() or not file_path.is_file() or _sha_file(file_path) != entry["sha256"]:
            raise ValueError("CACHE_CORRUPT")
    snapshot = manifest.get("snapshot")
    if snapshot is not None:
        if not isinstance(snapshot, dict) or set(snapshot) != {"file", "sha256"} or snapshot["file"] != "native_physics.blend":
            raise ValueError("CACHE_CORRUPT")
        file_path = directory / snapshot["file"]
        if file_path.is_symlink() or not file_path.is_file() or _sha_file(file_path) != snapshot["sha256"]:
            raise ValueError("CACHE_CORRUPT")
    checkpoint = manifest.get("checkpoint")
    if checkpoint is not None:
        if (not isinstance(checkpoint, dict) or set(checkpoint) != {"file", "sha256"} or
                checkpoint["file"] != "source_checkpoint.blend"):
            raise ValueError("CACHE_CORRUPT")
        file_path = directory / checkpoint["file"]
        if file_path.is_symlink() or not file_path.is_file() or _sha_file(file_path) != checkpoint["sha256"]:
            raise ValueError("CACHE_CORRUPT")
    return len(files)


def _inspect(context, scene=None, expected_revision=None):
    directory = _cache_directory(context)
    manifest = _read_json(directory / "manifest.json")
    if manifest.get("schema") != _CACHE_SCHEMA or manifest.get("state") != "succeeded":
        raise ValueError("CACHE_CORRUPT")
    if expected_revision is not None and manifest.get("source_revision") != expected_revision:
        raise ValueError("CHECKPOINT_CONFLICT")
    count = _verify_entries(directory, manifest)
    if (count != manifest["frame_end"] - manifest["frame_start"] + 1 or
            [e["frame"] for e in manifest["frames"]] !=
            list(range(manifest["frame_start"], manifest["frame_end"] + 1))):
        raise ValueError("CACHE_CORRUPT")
    scene_verified = False
    if scene is not None:
        if _scene_revision(scene, manifest["objects"]) != manifest["post_scene_revision"]:
            raise ValueError("CHECKPOINT_CONFLICT")
        scene_verified = True
    return {"operation": OPERATION_NAMES[1], "state": "succeeded", "scene": manifest["scene"],
            "source_revision": manifest["source_revision"], "created": [],
            "artifact": {"kind": "cache", "sha256": _sha_file(directory / "manifest.json")},
            "native_execution_verified": scene_verified, "visual_quality_verified": False,
            "quality_reduced": False, "native_point_cache_baked": manifest["native_point_cache_baked"],
            "cache_kind": manifest["cache_mode"], "sampled_frames": count,
            "snapshot": manifest["snapshot"], "scene_revision_verified": scene_verified, "warnings": []}


def audit(operation: str, payload: dict, context: dict) -> dict:
    if operation != OPERATION_NAMES[1]:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    p = validate(operation, payload)
    _, scene = _require_native(context)
    return _inspect(context, scene, p.get("expected_source_revision"))


def _assign_bodies(bpy, scene, specs, allow_existing=False):
    if bpy.context.mode != "OBJECT":
        raise ValueError("OBJECT_MODE_REQUIRED")
    view_layer = bpy.context.view_layer
    old_active = view_layer.objects.active
    old_selected = tuple(bpy.context.selected_objects)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        for spec in specs:
            ob = scene.objects[spec["name"]]
            if ob.rigid_body is not None:
                if not allow_existing:
                    raise ValueError("CHECKPOINT_CONFLICT")
                if ob.rigid_body.type != spec["role"]:
                    raise ValueError("CHECKPOINT_CONFLICT")
                continue
            view_layer.objects.active = ob
            ob.select_set(True)
            result = bpy.ops.rigidbody.object_add()
            ob.select_set(False)
            if "FINISHED" not in result or ob.rigid_body is None:
                raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
            body = ob.rigid_body
            body.type = spec["role"]
            body.collision_shape = spec["shape"]
            body.mass = spec["mass"] if spec["role"] == "ACTIVE" else 1.0
            body.friction = spec["friction"]
            body.restitution = spec["restitution"]
            body.kinematic = False
            body.enabled = True
            for group in range(len(body.collision_collections)):
                body.collision_collections[group] = group == spec["collision_group"]
        if scene.rigidbody_world is None:
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for ob in old_selected:
            if ob.name in scene.objects:
                ob.select_set(True)
        view_layer.objects.active = old_active if old_active and old_active.name in scene.objects else None


def _bake_point_cache(bpy, scene, start, end):
    point_cache = scene.rigidbody_world.point_cache
    point_cache.frame_start = min(scene.frame_start, start)
    point_cache.frame_end = end
    try:
        with bpy.context.temp_override(scene=scene, point_cache=point_cache):
            result = bpy.ops.ptcache.bake(bake=True)
        if "FINISHED" not in result or not point_cache.is_baked:
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    except (AttributeError, RuntimeError, TypeError) as exc:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE") from exc
    return True


def _sample(scene, specs, frame):
    scene.frame_set(frame)
    depsgraph = __import__("bpy").context.evaluated_depsgraph_get()
    frames = {}
    for item in specs:
        ob = scene.objects[item["name"]].evaluated_get(depsgraph)
        matrix = ob.matrix_world
        frames[item["name"]] = {"location": [round(float(x), 6) for x in matrix.translation],
                                "matrix_world": [round(float(x), 6) for row in matrix for x in row],
                                "rigid_body_type": item["role"]}
    return {"frame": frame, "objects": frames}


def _save_copy(bpy, directory, base="native_physics"):
    if base not in ("native_physics", "source_checkpoint"):
        raise ValueError("INVALID_ARGUMENTS")
    original = bpy.data.filepath
    staging = directory / (base + "_pending.blend")
    final = directory / (base + ".blend")
    if staging.is_symlink() or final.is_symlink():
        raise ValueError("CACHE_OUTSIDE_SCOPE")
    result = bpy.ops.wm.save_as_mainfile(filepath=str(staging), copy=True,
                                         check_existing=False, compress=False)
    if "FINISHED" not in result or bpy.data.filepath != original or not staging.is_file():
        raise ValueError("NATIVE_SAVE_UNCONFIRMED")
    if staging.stat().st_size < 256 or staging.open("rb").read(7) != b"BLENDER":
        raise ValueError("NATIVE_SAVE_UNCONFIRMED")
    with staging.open("rb") as f:
        os.fsync(f.fileno())
    os.replace(staging, final)
    _sync_dir(directory)
    return {"file": final.name, "sha256": _sha_file(final)}


def execute(operation: str, payload: dict, context: dict) -> dict:
    p = validate(operation, payload)
    bpy, scene = _require_native(context)
    if operation == OPERATION_NAMES[1]:
        return _inspect(context, scene, p.get("expected_source_revision"))
    if scene.get("production_frozen_job"):
        raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
    if (scene.frame_start > p["frame_start"] or scene.frame_end < p["frame_end"] or
            not scene.use_gravity):
        raise ValueError("INVALID_ARGUMENTS")
    directory = _cache_directory(context)
    specifications = p["objects"]
    request_hash = _digest(p)
    if (directory / "manifest.json").exists():
        existing = _read_json(directory / "manifest.json")
        if existing.get("request_sha256") != request_hash:
            raise ValueError("CHECKPOINT_CONFLICT")
        evidence = _inspect(context, scene, p["expected_scene_revision"])
        evidence["idempotent_replay"] = True
        evidence["operation"] = operation
        return evidence
    stage_path = directory / "stage.json"
    continuing = stage_path.is_file()
    if continuing:
        stage = _read_json(stage_path)
        if (stage.get("request_sha256") != request_hash or
                stage.get("source_revision") != p["expected_scene_revision"] or
                scene.get("omega_p13_job_id") != context["job_id"]):
            raise ValueError("CHECKPOINT_CONFLICT")
    else:
        actual = _scene_revision(scene, specifications)
        if actual != p["expected_scene_revision"]:
            raise ValueError("CHECKPOINT_CONFLICT")
        if any(scene.objects[s["name"]].rigid_body is not None for s in specifications):
            raise ValueError("CHECKPOINT_CONFLICT")
        if _cancelled(context):
            return {"operation": operation, "state": "paused", "source_revision": actual,
                    "native_execution_verified": False, "quality_reduced": False,
                    "warnings": ["CANCELLED_BEFORE_MUTATION"]}
        directory = _cache_directory(context, create=True)
        checkpoint = _save_copy(bpy, directory, "source_checkpoint")
        stage = {"schema": _CACHE_SCHEMA, "source_revision": actual,
                 "request_sha256": request_hash, "frames": [], "checkpoint": checkpoint}
        _write_json(stage_path, stage)
        scene["omega_p13_job_id"] = context["job_id"]
    _assign_bodies(bpy, scene, specifications, allow_existing=continuing)
    if p["cache_mode"] == "NATIVE_POINT_CACHE":
        point_cache_baked = _bake_point_cache(bpy, scene, p["frame_start"], p["frame_end"])
    else:
        point_cache_baked = False
    first_positions = None
    last_positions = None
    original_frame = scene.frame_current
    try:
        scene.frame_set(scene.frame_start)
        for frame in range(scene.frame_start, p["frame_end"] + 1):
            if _cancelled(context):
                return {"operation": operation, "state": "paused", "scene": scene.name,
                        "source_revision": p["expected_scene_revision"], "created": [],
                        "artifact": {"kind": "none", "sha256": None},
                        "native_execution_verified": True, "quality_reduced": False,
                        "sampled_frames": len(stage["frames"]), "warnings": ["PAUSED_AT_FRAME_BOUNDARY"]}
            if frame < p["frame_start"]:
                scene.frame_set(frame)
                continue
            sample = _sample(scene, specifications, frame)
            positions = {k: v["location"] for k, v in sample["objects"].items()}
            if first_positions is None:
                first_positions = positions
            last_positions = positions
            filename = "frame_%06d.json" % frame
            path = directory / filename
            if path.exists():
                if _read_json(path) != sample:
                    raise ValueError("CHECKPOINT_CONFLICT")
                digest = _sha_file(path)
            else:
                digest = _write_json(path, sample)
            entry = {"frame": frame, "file": filename, "sha256": digest}
            matching = next((e for e in stage["frames"] if e["frame"] == frame), None)
            if matching and matching != entry:
                raise ValueError("CACHE_CORRUPT")
            if matching is None:
                stage["frames"].append(entry)
                _write_json(stage_path, stage)
    finally:
        scene.frame_set(original_frame)
    movement = {name: math.dist(first_positions[name], last_positions[name])
                for name in first_positions}
    dynamic = [ob["name"] for ob in specifications if ob["role"] == "ACTIVE"]
    if not any(movement[name] > 0.1 for name in dynamic):
        raise ValueError("SIMULATION_NOT_DYNAMIC")
    post_revision = _scene_revision(scene, specifications)
    snapshot = _save_copy(bpy, directory) if p["save_blend_copy"] else None
    manifest = {"schema": _CACHE_SCHEMA, "state": "succeeded", "scene": scene.name,
                "source_revision": p["expected_scene_revision"], "post_scene_revision": post_revision,
                "request_sha256": request_hash, "objects": specifications,
                "frame_start": p["frame_start"], "frame_end": p["frame_end"],
                "cache_mode": p["cache_mode"], "native_point_cache_baked": point_cache_baked,
                "frames": stage["frames"], "movement_meters": movement,
                "snapshot": snapshot, "checkpoint": stage["checkpoint"]}
    manifest_sha = _write_json(directory / "manifest.json", manifest)
    _verify_entries(directory, manifest)
    return {"operation": operation, "state": "succeeded", "scene": scene.name,
            "source_revision": p["expected_scene_revision"],
            "created": [o["name"] for o in specifications],
            "artifact": {"kind": "blend" if snapshot else "cache",
                         "sha256": snapshot["sha256"] if snapshot else manifest_sha},
            "native_execution_verified": True, "visual_quality_verified": False,
            "quality_reduced": False, "native_point_cache_baked": point_cache_baked,
            "cache_kind": p["cache_mode"], "sampled_frames": len(stage["frames"]),
            "movement_meters": movement, "snapshot": snapshot,
            "recovery_checkpoint": stage["checkpoint"],
            "warnings": ([] if point_cache_baked else ["SAMPLED_PHYSICS_NOT_NATIVE_POINT_CACHE_BAKE"])}
