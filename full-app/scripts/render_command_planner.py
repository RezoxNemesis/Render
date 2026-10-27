# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only recipe previews and digest-bound submission to Render's real queue.

No recipe executes here. The existing Blender main-thread plan executor owns
checkpoints, serialized mutations and authoritative completion receipts.
"""
from collections import OrderedDict
import hashlib
import hmac
import json
from pathlib import Path
import secrets

import render_command_contract as Contract

OPS = Contract.OPS
READ_ONLY = Contract.READ_ONLY
# Session-local read-only bookkeeping. A preview cannot authorize writes after
# a native runtime restart, or against a newly allocated ID reusing an address.
_NATIVE_SESSION = secrets.token_hex(32)
_SCENE_IDENTITIES = OrderedDict()
_MAX_SCENE_IDENTITIES = 32
_CREATES = frozenset(("studio.create.model", "studio.create.terrain",
                      "studio.create.scatter", "studio.create.camera",
                      "studio.create.rig", "mesh.create", "rig.create",
                      "body.blockout"))


def capabilities():
    return Contract.capabilities()


def _names(steps):
    return sorted({step["payload"]["name"] for step in steps
                   if step["operation"] in _CREATES and
                   type(step["payload"].get("name")) is str})


def _queue_records(root):
    """Inspect existing durable records without creating a queue directory."""
    import render_unified_queue as Queue
    base = Path(root)
    folder = base / "StudioPlans"
    if base.is_symlink() or folder.is_symlink():
        raise ValueError("STUDIO_COMMAND_QUEUE_SYMLINK")
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise ValueError("STUDIO_COMMAND_QUEUE_NOT_DIRECTORY")
    records = []
    for path in sorted(folder.glob("*.json")):
        if not Queue.C.ID.fullmatch(path.stem):
            continue
        if path.is_symlink():
            raise ValueError("STUDIO_COMMAND_QUEUE_SYMLINK")
        records.append(Queue._load_file(path))
    return records


def _inventory_digest(objects):
    # This guards the names/types relevant to creation, not a costly mesh scan.
    rows = sorted((item.name, getattr(item, "type", "COLLECTION")) for item in objects)
    raw = json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest(), len(rows)


def _scene_identity(scene):
    """Stable within a live Blender ID/session; never writes an ID property.

    Retained RNA wrappers become invalid after deletion/file reopen, even when
    Blender 4.2 later reuses their address. Newer Blender's session_uid provides
    another identity check. Eviction fails closed by issuing a fresh token.
    """
    def native_id(value):
        pointer = value.as_pointer() if hasattr(value, "as_pointer") else id(value)
        uid = getattr(value, "session_uid", None)
        return int(pointer), int(uid) if uid is not None else None

    try:
        identity = native_id(scene)
    except (ReferenceError, TypeError, ValueError) as exc:
        raise ValueError("STUDIO_COMMAND_SCENE_UNAVAILABLE") from exc
    if not identity[0]:
        raise ValueError("STUDIO_COMMAND_SCENE_UNAVAILABLE")
    # Keeping references is deliberate: Python object IDs cannot be reused
    # while retained, and removed Blender RNA references expose invalidation.
    for key, (held, token) in list(_SCENE_IDENTITIES.items()):
        try:
            valid = native_id(held) == key
        except (ReferenceError, TypeError, ValueError):
            valid = False
        if not valid:
            del _SCENE_IDENTITIES[key]
    previous = _SCENE_IDENTITIES.get(identity)
    if previous is not None:
        held, token = previous
        try:
            matches = held is scene or held == scene
        except ReferenceError:
            matches = False
        if not matches:
            previous = None
    if previous is None:
        token = secrets.token_hex(24)
        _SCENE_IDENTITIES[identity] = (scene, token)
    _SCENE_IDENTITIES.move_to_end(identity)
    while len(_SCENE_IDENTITIES) > _MAX_SCENE_IDENTITIES:
        _SCENE_IDENTITIES.popitem(last=False)
    return Contract.digest({"native_session": _NATIVE_SESSION, "scene_token": token,
                            "pointer": identity[0], "session_uid": identity[1]})


def _preflight(compiled, root, scene):
    import bpy
    import render_creator_contract as Creator
    import render_production_contract as Production
    import render_unified_contract as Unified
    import render_unified_queue as Queue

    # A single snapshot runs on the same authenticated main thread as submit.
    names = _names(compiled["steps"])
    object_collisions = sorted(name for name in names if bpy.data.objects.get(name) is not None)
    collection_collisions = sorted(name for name in names if bpy.data.collections.get(name) is not None)
    collisions = sorted(set(object_collisions) | set(collection_collisions))
    records = _queue_records(root)
    active_records = [row for row in records if row["state"] in Queue.ACTIVE]
    reserved = set()
    queue_hash = hashlib.sha256()
    for row in records:
        pending_names = _names(row["steps"][row["next"]:]) if row["state"] in Queue.ACTIVE else []
        reserved.update(pending_names)
        # Terminal history distinguishes a fresh preview after cancellation from
        # an exact retry of the cancelled job. Stream summaries so old history
        # cannot overflow the bounded public preview JSON.
        summary = {"plan_id": row["plan_id"], "state": row["state"],
                   "next": row["next"], "fingerprint": row["fingerprint"],
                   "reserved_names": pending_names}
        queue_hash.update(Contract.canonical_bytes(summary))
        queue_hash.update(b"\n")
    queue_conflicts = sorted(set(names) & reserved)
    operations = sorted({step["operation"] for step in compiled["steps"]})
    missing = [operation for operation in operations
               if operation not in Creator.OPS or operation not in Production.OPERATIONS or
               operation not in Unified.PROGRAM_OPS]
    issues = []
    if object_collisions:
        issues.append("STUDIO_COMMAND_OBJECT_NAME_COLLISION")
    if collection_collisions:
        issues.append("STUDIO_COMMAND_COLLECTION_NAME_COLLISION")
    if queue_conflicts:
        issues.append("STUDIO_COMMAND_QUEUED_NAME_COLLISION")
    if missing:
        issues.append("STUDIO_COMMAND_OPERATION_NOT_INSTALLED")
    if len(active_records) >= Queue.MAX_PLANS:
        issues.append("STUDIO_PLAN_QUEUE_FULL")
    frozen = bool(scene.get("production_frozen_job"))
    if frozen:
        issues.append("RENDER_SNAPSHOT_IMMUTABLE")
    mode = getattr(bpy.context, "mode", None)
    if mode != "OBJECT":
        issues.append("STUDIO_COMMAND_OBJECT_MODE_REQUIRED")
    if getattr(bpy.context, "scene", None) != scene:
        issues.append("STUDIO_COMMAND_ACTIVE_SCENE_MISMATCH")
    if getattr(scene, "library", None) is not None or not getattr(scene, "is_editable", True):
        issues.append("STUDIO_COMMAND_SCENE_NOT_EDITABLE")
    # All references must point to objects created earlier in this same recipe.
    # A new recipe can never animate, re-material or rig an existing user object.
    created = {}
    for step in compiled["steps"]:
        operation = step["operation"]
        p = Creator.validate(operation, step["payload"])
        if operation in ("studio.create.material", "studio.create.motion", "studio.create.rig"):
            if created.get(p["object"]) not in ("model", "terrain"):
                issues.append("STUDIO_COMMAND_DEPENDENCY_INVALID")
        elif operation == "studio.create.camera":
            if p["target"] not in created:
                issues.append("STUDIO_COMMAND_DEPENDENCY_INVALID")
        elif operation == "studio.create.scatter":
            if created.get(p["source"]) != "model" or (
                    p.get("terrain") is not None and created.get(p["terrain"]) != "terrain"):
                issues.append("STUDIO_COMMAND_DEPENDENCY_INVALID")
        if operation in _CREATES:
            if p["name"] in created:
                issues.append("STUDIO_COMMAND_DUPLICATE_RECIPE_NAME")
            created[p["name"]] = operation.rsplit(".", 1)[-1]
    inventory_sha, global_count = _inventory_digest(bpy.data.objects)
    collections_sha, collection_count = _inventory_digest(bpy.data.collections)
    scene_sha, scene_count = _inventory_digest(scene.objects)
    camera = getattr(scene, "camera", None)
    scene_guard = {"scene": scene.name, "objects": scene_count,
                   "scene_identity_sha256": _scene_identity(scene),
                   "native_session_sha256": Contract.digest(_NATIVE_SESSION),
                   "scene_objects_sha256": scene_sha, "global_objects": global_count,
                   "global_objects_sha256": inventory_sha,
                   "global_collections": collection_count,
                   "global_collections_sha256": collections_sha,
                   "mode": mode, "frozen": frozen,
                   "active_camera": camera.name if camera is not None else None,
                   "frame_start": int(scene.frame_start), "frame_end": int(scene.frame_end),
                   "frame_current": int(scene.frame_current),
                   "blender_version": str(bpy.app.version_string),
                   "creator_contract": Creator.VERSION,
                   "available_operations": [op for op in operations if op not in missing],
                   "queue_sha256": queue_hash.hexdigest()}
    return {"compatible": not issues, "collisions": collisions,
            "object_collisions": object_collisions, "collection_collisions": collection_collisions,
            "queue_conflicts": queue_conflicts, "missing_operations": missing,
            "issues": sorted(set(issues)), "objects_to_create": names,
            "available_plan_slots": max(0, Queue.MAX_PLANS - len(active_records)),
            "creator_payloads_validated": True, "scene_preflight_complete": True,
            "scene_guard": scene_guard,
            "scene_guard_scope": "native session, live scene identity, object/collection names and types, active camera/frame, mode, tool registry and queue revisions",
            "existing_mesh_geometry_fingerprinted": False,
            "simulation_executed": False}


def preview(payload, root, scene):
    compiled = Contract.compile_request(payload)
    compiled["preflight"] = _preflight(compiled, root, scene)
    compiled["ready_to_submit"] = compiled["preflight"]["compatible"]
    return Contract.seal_preview(compiled)


def _existing(root, plan_id, expected_fingerprint):
    """An exact retry returns its original job, never re-executes a recipe."""
    import render_unified_queue as Queue
    folder = Path(root) / "StudioPlans"
    path = folder / (plan_id + ".json")
    if Path(root).is_symlink() or folder.is_symlink() or path.is_symlink():
        raise ValueError("STUDIO_COMMAND_QUEUE_SYMLINK")
    if not path.exists():
        return None
    record = Queue._load_file(path)
    if record["fingerprint"] != expected_fingerprint:
        raise ValueError("STUDIO_COMMAND_REPLAY_CONFLICT")
    return dict(Queue.C.public(record), idempotent=True)


def submit(payload, root, scene):
    request = Contract.validate("studio.command.submit", payload)
    expected_sha = request.pop("preview_sha256")
    compiled = Contract.compile_request(request)
    import render_unified_contract as Unified
    plan = {"name": compiled["name"], "steps": compiled["steps"]}
    # Generic plan validation ensures the current queue accepts all operations.
    fingerprint = Unified.plan(plan)["fingerprint"]
    identifier = Contract.plan_id(compiled["request"], expected_sha)
    existing = _existing(root, identifier, fingerprint)
    if existing is not None:
        return _submission_result(existing, compiled, expected_sha)
    reviewed = preview(request, root, scene)
    if not hmac.compare_digest(reviewed["preview_sha256"], expected_sha):
        raise ValueError("STUDIO_COMMAND_PREVIEW_STALE")
    if not reviewed["ready_to_submit"]:
        raise ValueError("STUDIO_COMMAND_PREFLIGHT_BLOCKED: " +
                         ", ".join(reviewed["preflight"]["issues"]))
    plan["plan_id"] = identifier
    # Import late: preview/catalog neither install timers nor create queue files.
    import render_unified_workspace as Studio
    result = Studio.execute("studio.plan.submit", plan, root, scene)
    return _submission_result(result, reviewed, expected_sha)


def _submission_result(result, compiled, sha):
    return dict(result, contract=Contract.VERSION, recipe_id=compiled["recipe"]["id"],
                preview_sha256=sha, submitted_to_queue=True,
                scene_modified_by_command=False,
                completion_source="studio.plan.status and verified native queue receipts",
                status_operation="studio.plan.status")


def execute(op, payload, root, scene):
    if op == "studio.command.catalog":
        Contract.validate(op, payload)
        return Contract.catalog()
    if op == "studio.command.preview":
        return preview(payload, root, scene)
    if op == "studio.command.submit":
        return submit(payload, root, scene)
    raise ValueError("STUDIO_COMMAND_OPERATION_UNAVAILABLE")
