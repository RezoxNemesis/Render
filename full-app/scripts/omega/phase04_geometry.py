# SPDX-License-Identifier: GPL-2.0-or-later
"""RENDER OMEGA P04: bounded, transactional native Blender/BMesh loop bridging.

Import is safe in ordinary CPython; execute/audit require real bpy and bmesh on
Blender's main thread. Phase 10 registers the two exact public operations. No
remote eval, dynamic operator name, filesystem path, or scene-wide edit exists.

Workflow: inspect mesh -> submit its source_revision and ordered rings -> bridge
on a *copy* -> inspect the native BMesh -> atomically swap object mesh pointers.
Original meshes are kept as .blend-serialized, bounded undo checkpoints; restore
is a typed sub-action of bridge_loops (not a custom bpy operator).
"""

import hashlib
import importlib
import json
import math
import re
import struct
import threading

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.geometry.bridge_loops", "omega.geometry.inspect")
MAX_VERTICES = 65536
MAX_FACES = 131072
MAX_RINGS = 48
MAX_LOOP = 256
MAX_CHECKPOINTS = 8
MAX_LEDGER = 32
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_. -]{0,63}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_KEY = re.compile(r"^[0-9a-f]{32}$")
_CHECKPOINTS = "omega_p04_checkpoints"
_LEDGER = "omega_p04_jobs"


def _error(code):
    raise ValueError(code)


def _dict(value, allowed, required):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        _error("INVALID_ARGUMENTS")


def _boolean(value):
    if type(value) is not bool:
        _error("INVALID_ARGUMENTS")
    return value


def _object_name(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        _error("INVALID_OBJECT_NAME")
    return value


def _revision(value):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        _error("INVALID_SOURCE_REVISION")
    return value


def validate(operation, payload):
    """Pure validation, no imports of Blender or project mutation."""
    if operation not in OPERATION_NAMES:
        _error("UNSUPPORTED_NATIVE_FEATURE")
    if operation == "omega.geometry.inspect":
        _dict(payload, ("object",), ("object",))
        return {"object": _object_name(payload["object"])}
    _dict(payload,
          ("object", "action", "expected_revision", "loops", "closed",
           "smooth", "require_manifold"),
          ("object", "expected_revision"))
    result = {"object": _object_name(payload["object"]),
              "action": payload.get("action", "bridge"),
              "expected_revision": _revision(payload["expected_revision"])}
    if result["action"] == "restore":
        if set(payload) - {"object", "action", "expected_revision"}:
            _error("INVALID_ARGUMENTS")
        return result
    if result["action"] != "bridge":
        _error("INVALID_ARGUMENTS")
    if "loops" not in payload:
        _error("INVALID_ARGUMENTS")
    rings = payload["loops"]
    if not isinstance(rings, list) or not 2 <= len(rings) <= MAX_RINGS:
        _error("INVALID_EDGE_LOOPS")
    closed = _boolean(payload.get("closed", True))
    bound = 3 if closed else 2
    first_length = None
    seen = set()
    validated = []
    for ring in rings:
        if not isinstance(ring, list) or not bound <= len(ring) <= MAX_LOOP:
            _error("INVALID_EDGE_LOOPS")
        if first_length is None:
            first_length = len(ring)
        if len(ring) != first_length:
            _error("LOOP_VERTEX_COUNT_MISMATCH")
        clean = []
        for vertex in ring:
            if type(vertex) is not int or not 0 <= vertex < MAX_VERTICES or vertex in seen:
                _error("INVALID_EDGE_LOOPS")
            seen.add(vertex)
            clean.append(vertex)
        validated.append(clean)
    result.update(loops=validated, closed=closed,
                  smooth=_boolean(payload.get("smooth", False)),
                  require_manifold=_boolean(payload.get("require_manifold", False)))
    return result


def _native():
    if threading.current_thread() is not threading.main_thread():
        _error("BLENDER_MAIN_THREAD_REQUIRED")
    try:
        bpy = importlib.import_module("bpy")
        bmesh = importlib.import_module("bmesh")
    except ImportError:
        _error("UNSUPPORTED_NATIVE_FEATURE")
    if not hasattr(bpy, "data") or not hasattr(bmesh, "ops"):
        _error("UNSUPPORTED_NATIVE_FEATURE")
    return bpy, bmesh


def _scene_object(bpy, context, name, write=False):
    if not isinstance(context, dict):
        _error("INVALID_CONTEXT")
    scene = context.get("scene")
    if scene is None or not isinstance(scene, bpy.types.Scene):
        _error("INVALID_CONTEXT")
    ob = scene.objects.get(name)
    if ob is None:
        _error("OBJECT_NOT_FOUND")
    if ob.type != "MESH":
        _error("MESH_REQUIRED")
    if ob.mode != "OBJECT":
        _error("OBJECT_MODE_REQUIRED")
    if ob.library or ob.data.library or ob.data.is_editmode:
        # In EDIT mode, bpy mesh coordinates may be stale; do not edit data.
        _error("OBJECT_MODE_REQUIRED")
    if write and scene.get("production_frozen_job"):
        _error("RENDER_SNAPSHOT_IMMUTABLE")
    if write and ob.data.shape_keys:
        _error("UNSUPPORTED_SHAPE_KEY_EDIT")
    if len(ob.data.vertices) > MAX_VERTICES or len(ob.data.polygons) > MAX_FACES:
        _error("TOPOLOGY_BUDGET_EXCEEDED")
    return scene, ob


def _mesh_revision(mesh):
    """Stable fingerprint of raw native mesh topology, coordinates and shading."""
    digest = hashlib.sha256()
    digest.update(struct.pack("<III", len(mesh.vertices), len(mesh.edges), len(mesh.polygons)))
    for vert in mesh.vertices:
        digest.update(struct.pack("<3d", *map(float, vert.co)))
    for edge in mesh.edges:
        digest.update(struct.pack("<II", *edge.vertices))
    for face in mesh.polygons:
        indices = tuple(face.vertices)
        digest.update(struct.pack("<I", len(indices)))
        digest.update(struct.pack("<%dI" % len(indices), *indices))
        digest.update(struct.pack("<I?", face.material_index, bool(face.use_smooth)))
    for material in mesh.materials:
        # Slot identity is a user-visible part of the shading state.
        digest.update((material.name_full if material else "<none>").encode("utf8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _mesh_audit(bmesh, mesh):
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        return _bmesh_audit(bm)
    finally:
        bm.free()


def _bmesh_audit(bm):
    bm.normal_update()
    vertices = len(bm.verts)
    edges = len(bm.edges)
    faces = len(bm.faces)
    boundary = sum(len(e.link_faces) == 1 for e in bm.edges)
    wire = sum(len(e.link_faces) == 0 for e in bm.edges)
    nonmanifold = sum(len(e.link_faces) > 2 for e in bm.edges)
    tiny = sum(f.calc_area() <= 1e-10 for f in bm.faces)
    reversed_edges = sum(
        len(e.link_loops) == 2 and e.link_loops[0].vert == e.link_loops[1].vert
        for e in bm.edges
    )
    invalid_normals = sum(not math.isfinite(f.normal.length) or
                          (f.normal.length < 0.9 and f.calc_area() > 1e-10)
                          for f in bm.faces)
    remaining = set(bm.verts)
    components = 0
    while remaining:
        components += 1
        seed = remaining.pop()
        stack = [seed]
        while stack:
            vertex = stack.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other in remaining:
                    remaining.remove(other)
                    stack.append(other)
    return {
        "vertices": vertices, "edges": edges, "polygons": faces,
        "boundary_edges": boundary, "wire_edges": wire,
        "nonmanifold_edges": nonmanifold,
        "degenerate_faces": tiny, "winding_conflicts": reversed_edges,
        "invalid_face_normals": invalid_normals,
        "connected_components": components,
        "euler_characteristic": vertices - edges + faces,
        "watertight": (vertices > 0 and faces > 0 and boundary == 0 and
                       wire == 0 and nonmanifold == 0 and tiny == 0 and
                       reversed_edges == 0 and invalid_normals == 0 and components == 1),
    }


def _receipt(operation, scene, revision, data, native_verified=True):
    return {
        "operation": operation, "state": "succeeded", "scene": scene.name,
        "source_revision": revision, "created": [],
        "artifact": {"kind": "none", "sha256": None},
        "native_execution_verified": native_verified,
        "visual_quality_verified": False, "quality_reduced": False,
        "warnings": [], "result": data,
    }


def audit(operation, payload, context):
    p = validate(operation, payload)
    bpy, bmesh = _native()
    scene, ob = _scene_object(bpy, context, p["object"])
    revision = _mesh_revision(ob.data)
    return _receipt(operation, scene, revision, {
        "object": ob.name, "mesh": ob.data.name,
        "topology": _mesh_audit(bmesh, ob.data),
        "modifiers": [m.name for m in ob.modifiers],
        "material_slots": len(ob.data.materials),
        "mesh_users": ob.data.users,
        "stored_undo_checkpoints": len(_saved_array(ob, _CHECKPOINTS, MAX_CHECKPOINTS)),
    })


def _saved_array(ob, prop, maximum):
    try:
        result = json.loads(ob.get(prop, "[]"))
    except (TypeError, ValueError):
        _error("CHECKPOINT_CONFLICT")
    if not isinstance(result, list) or len(result) > maximum:
        _error("CHECKPOINT_CONFLICT")
    return result


def _job(context):
    if not isinstance(context, dict):
        _error("INVALID_CONTEXT")
    key = context.get("job_id")
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        _error("INVALID_JOB_ID")
    return key


def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf8")).hexdigest()


def _cancelled(context):
    value = context.get("cancellation_requested", False)
    return bool(value() if callable(value) else value)


def _check_budget(context, count, faces):
    free = context.get("available_memory_bytes")
    if free is None:
        return
    if type(free) is not int or free < 0:
        _error("INVALID_CONTEXT")
    # Conservative admission for duplicate mesh + BMesh scratch + derived data.
    if free < 3 * (count * 1024 + faces * 2048 + 8 * 1024 * 1024):
        _error("OUT_OF_MEMORY_PAUSED")


def _ordered_edges(bm, indices, closed):
    bm.verts.ensure_lookup_table()
    selected = [bm.verts[i] for i in indices]
    if len(set(selected)) != len(selected):
        _error("INVALID_EDGE_LOOPS")
    found = []
    for i in range(len(selected) if closed else len(selected)-1):
        a = selected[i]
        b = selected[(i+1) % len(selected)]
        edge = next((e for e in a.link_edges if e.other_vert(a) == b), None)
        if edge is None or len(edge.link_faces) > 1:
            _error("INVALID_EDGE_LOOPS")
        found.append(edge)
    if len(set(found)) != len(found):
        _error("INVALID_EDGE_LOOPS")
    # No branching at ring vertices or sharing edges with other chosen rings.
    return found


def _bridge(bmesh, bm, p):
    bm.verts.ensure_lookup_table()
    if any(i >= len(bm.verts) for loop in p["loops"] for i in loop):
        _error("INVALID_EDGE_LOOPS")
    # Perform *all* preflight topology checks before any BMesh bridge mutation.
    pairs = [_ordered_edges(bm, ring, p["closed"]) for ring in p["loops"]]
    if not p["closed"]:
        # Bridge pairs of open polylines only, never a chain with ambiguous ends.
        if len(pairs) != 2:
            _error("INVALID_EDGE_LOOPS")
    created = []
    for i in range(len(pairs)-1):
        result = bmesh.ops.bridge_loops(
            bm, edges=pairs[i]+pairs[i+1], use_pairs=False,
            use_cyclic=False, use_merge=False, twist_offset=0)
        faces = result.get("faces", [])
        if len(faces) < len(pairs[i]):
            _error("NATIVE_BRIDGE_FAILED")
        created.extend(faces)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if p["smooth"]:
        for f in created:
            f.smooth = True
    return len(created)


def execute(operation, payload, context):
    p = validate(operation, payload)
    if operation == "omega.geometry.inspect":
        return audit(operation, p, context)
    bpy, bmesh = _native()
    scene, ob = _scene_object(bpy, context, p["object"], write=True)
    job = _job(context)
    digest = _fingerprint(p)
    current = _mesh_revision(ob.data)
    ledger = _saved_array(ob, _LEDGER, MAX_LEDGER)
    for item in ledger:
        if item.get("job") == job:
            if item.get("digest") != digest or item.get("revision") != current:
                _error("CHECKPOINT_CONFLICT")
            result = audit("omega.geometry.inspect", {"object": ob.name}, context)["result"]
            receipt = _receipt(operation, scene, current, result)
            receipt["result"]["already_complete"] = True
            receipt["result"]["job_id"] = job
            return receipt
    if current != p["expected_revision"]:
        _error("MESH_REVISION_CONFLICT")
    if _cancelled(context):
        _error("CANCELLED")
    if context.get("dry_run", False):
        # Read native topology, but never claim to have bridged anything.
        return {
            "operation": operation, "state": "validated", "scene": scene.name,
            "source_revision": current, "created": [],
            "artifact": {"kind": "none", "sha256": None},
            "native_execution_verified": False, "visual_quality_verified": False,
            "quality_reduced": False, "warnings": ["DRY_RUN_NO_MESH_CHANGE"],
            "result": {"object": ob.name, "action": p["action"],
                       "topology": _mesh_audit(bmesh, ob.data)},
        }
    stack = _saved_array(ob, _CHECKPOINTS, MAX_CHECKPOINTS)
    _check_budget(context, len(ob.data.vertices), len(ob.data.polygons))
    if p["action"] == "restore":
        if not stack:
            _error("CHECKPOINT_NOT_FOUND")
        prior = stack[-1]
        if not isinstance(prior, dict) or not isinstance(prior.get("mesh"), str) or \
                not isinstance(prior.get("revision"), str):
            _error("CHECKPOINT_CONFLICT")
        backup = bpy.data.meshes.get(prior["mesh"])
        if backup is None or _mesh_revision(backup) != prior["revision"]:
            _error("CHECKPOINT_CONFLICT")
        old_mesh = ob.data
        old_checkpoints = ob.get(_CHECKPOINTS)
        old_ledger = ob.get(_LEDGER)
        try:
            ob.data = backup
            new_rev = _mesh_revision(ob.data)
            ob[_CHECKPOINTS] = json.dumps(stack[:-1], separators=(",", ":"))
            ledger.append({"job": job, "digest": digest, "revision": new_rev})
            ob[_LEDGER] = json.dumps(ledger[-MAX_LEDGER:], separators=(",", ":"))
        except Exception:
            ob.data = old_mesh
            for name, prior_value in ((_CHECKPOINTS, old_checkpoints), (_LEDGER, old_ledger)):
                if prior_value is None:
                    if name in ob:
                        del ob[name]
                else:
                    ob[name] = prior_value
            raise
        # The restored mesh remains native, including original materials/UVs.
        out = audit("omega.geometry.inspect", {"object": ob.name}, context)["result"]
        out.update({"restored": True, "job_id": job, "previous_revision": current})
        return _receipt(operation, scene, new_rev, out)
    if len(stack) >= MAX_CHECKPOINTS:
        _error("CHECKPOINT_LIMIT_REACHED")
    count = len(ob.data.vertices)
    expected_added_faces = sum(len(ring) if p["closed"] else len(ring)-1
                               for ring in p["loops"][:-1])
    if count + expected_added_faces * 2 > MAX_VERTICES or len(ob.data.polygons) + expected_added_faces > MAX_FACES:
        _error("TOPOLOGY_BUDGET_EXCEEDED")
    _check_budget(context, count + expected_added_faces * 2, len(ob.data.polygons) + expected_added_faces)
    original = ob.data
    candidate = original.copy()
    candidate.use_fake_user = False
    bm = bmesh.new()
    try:
        bm.from_mesh(candidate)
        before = _bmesh_audit(bm)
        added = _bridge(bmesh, bm, p)
        after = _bmesh_audit(bm)
        if after["degenerate_faces"] or after["winding_conflicts"] or after["nonmanifold_edges"] or after["invalid_face_normals"]:
            _error("INVALID_RESULT_TOPOLOGY")
        if p["require_manifold"] and not after["watertight"]:
            _error("NON_MANIFOLD_RESULT")
        if after["polygons"] <= before["polygons"] or added <= 0:
            _error("NATIVE_BRIDGE_FAILED")
        if _cancelled(context):
            _error("CANCELLED")
        bm.to_mesh(candidate)
        candidate.update()
        after_revision = _mesh_revision(candidate)
        if after_revision == current:
            _error("NATIVE_BRIDGE_FAILED")
        if len(candidate.materials) != len(original.materials):
            _error("NATIVE_BRIDGE_FAILED")
        # New mesh pointer assignment is the commit point. The pre-edit mesh
        # persists via fake-user so save/reopen still permits exact rollback.
        old_fake_user = original.use_fake_user
        old_checkpoints = ob.get(_CHECKPOINTS)
        old_ledger = ob.get(_LEDGER)
        try:
            original.use_fake_user = True
            ob.data = candidate
            stack.append({"mesh": original.name, "revision": current})
            ob[_CHECKPOINTS] = json.dumps(stack, separators=(",", ":"))
            ledger.append({"job": job, "digest": digest, "revision": after_revision})
            ob[_LEDGER] = json.dumps(ledger[-MAX_LEDGER:], separators=(",", ":"))
        except Exception:
            ob.data = original
            original.use_fake_user = old_fake_user
            for name, prior in ((_CHECKPOINTS, old_checkpoints), (_LEDGER, old_ledger)):
                if prior is None:
                    if name in ob:
                        del ob[name]
                else:
                    ob[name] = prior
            raise
        result = {
            "object": ob.name, "job_id": job, "already_complete": False,
            "native_operator": "bmesh.ops.bridge_loops", "bridged_ring_pairs": len(p["loops"])-1,
            "new_faces": added, "before": before, "after": after,
            "checkpoint_mesh": original.name,
            "checkpoint_revision": current, "new_revision": after_revision,
            "material_slots_preserved": len(candidate.materials) == len(original.materials),
        }
        if not result["material_slots_preserved"]:
            _error("NATIVE_BRIDGE_FAILED")
        return _receipt(operation, scene, after_revision, result)
    except Exception:
        if ob.data == candidate:
            ob.data = original
        if candidate.users == 0:
            bpy.data.meshes.remove(candidate)
        raise
    finally:
        bm.free()
