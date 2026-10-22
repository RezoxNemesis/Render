# SPDX-License-Identifier: GPL-2.0-or-later
"""OMEGA P09: bounded native Blender PBR + non-destructive RAW/FINAL grade.

Pure validation can run without Blender. execute/audit use actual scene
RNA on Blender's main thread, as invoked by the P10 allowlisted dispatcher.
No render engine, output dimensions, samples, color management, or user-owned
compositor graph is replaced. Cache inspection is read-only and app-scoped.
"""

import hashlib
import json
import math
from pathlib import Path
import re

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.vfx.create_grade", "omega.vfx.cache_inspect")
_OWNER = "RENDER-OMEGA-P09"
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NODES = {
    "layer": "OMEGA09_RenderLayers",
    "bright": "OMEGA09_BrightContrast",
    "gamma": "OMEGA09_Gamma",
    "output": "OMEGA09_Composite",
}


def _number(value, minimum, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("INVALID_ARGUMENTS")
    return float(value)


def _name(value):
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ValueError("INVALID_ARGUMENTS")
    return value


def _rgb(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("INVALID_ARGUMENTS")
    return [_number(component, 0.0, 1.0) for component in value]


def _int(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("INVALID_ARGUMENTS")
    return value


def validate(operation: str, payload: dict) -> dict:
    """Return a normalized, strictly allowlisted copy; never import bpy."""
    if operation not in OPERATION_NAMES or not isinstance(payload, dict):
        raise ValueError("INVALID_ARGUMENTS")
    if operation == "omega.vfx.cache_inspect":
        if set(payload) - {"cache_id", "frame_start", "frame_end"} or "cache_id" not in payload:
            raise ValueError("INVALID_ARGUMENTS")
        cache_id = _name(payload["cache_id"])
        start = _int(payload.get("frame_start", 1), 1, 100000)
        end = _int(payload.get("frame_end", start), start, min(100000, start + 239))
        return {"cache_id": cache_id, "frame_start": start, "frame_end": end}
    allowed = {"object", "material", "base_color", "metallic", "roughness",
               "bump_strength", "mode", "contrast", "gamma", "view_layer",
               "replace_first_slot", "expected_scene_revision"}
    if set(payload) - allowed or "object" not in payload:
        raise ValueError("INVALID_ARGUMENTS")
    mode = payload.get("mode", "FINAL")
    if mode not in ("RAW", "FINAL"):
        raise ValueError("INVALID_ARGUMENTS")
    replace = payload.get("replace_first_slot", False)
    if type(replace) is not bool:
        raise ValueError("INVALID_ARGUMENTS")
    rev = payload.get("expected_scene_revision")
    if rev is not None and (not isinstance(rev, str) or not _HEX.fullmatch(rev)):
        raise ValueError("INVALID_ARGUMENTS")
    spec = {
        "object": _name(payload["object"]),
        "material": _name(payload.get("material", "Omega09Surface")),
        "base_color": _rgb(payload.get("base_color", [0.55, 0.4, 0.25])),
        "metallic": _number(payload.get("metallic", 0.15), 0, 1),
        "roughness": _number(payload.get("roughness", 0.42), 0.02, 1),
        "bump_strength": _number(payload.get("bump_strength", 0), 0, 1),
        "mode": mode,
        "contrast": _number(payload.get("contrast", 15), -100, 100),
        "gamma": _number(payload.get("gamma", 0.82), 0.1, 4),
        "replace_first_slot": replace,
    }
    if "view_layer" in payload:
        spec["view_layer"] = _name(payload["view_layer"])
    if rev is not None:
        spec["expected_scene_revision"] = rev
    return spec


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _bpy():
    try:
        import bpy
    except ImportError as exc:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE: bpy not installed") from exc
    return bpy


def _scene(context):
    if not isinstance(context, dict):
        raise ValueError("INVALID_ARGUMENTS")
    scene = context.get("scene")
    if scene is None or not hasattr(scene, "view_layers") or not hasattr(scene, "render"):
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE: native scene required")
    return scene


def _quality(scene):
    render = scene.render
    settings = {"engine": render.engine, "resolution_x": render.resolution_x,
                "resolution_y": render.resolution_y,
                "resolution_percentage": render.resolution_percentage,
                "fps": render.fps, "fps_base": render.fps_base,
                "frame_current": scene.frame_current,
                "view_transform": scene.view_settings.view_transform,
                "look": scene.view_settings.look,
                "exposure": scene.view_settings.exposure,
                "view_gamma": scene.view_settings.gamma}
    cycles = getattr(scene, "cycles", None)
    if cycles is not None:
        settings["cycles_samples"] = cycles.samples
    eevee = getattr(scene, "eevee", None)
    if eevee is not None and hasattr(eevee, "taa_render_samples"):
        settings["eevee_samples"] = eevee.taa_render_samples
    return settings


def _scene_revision(scene):
    """A bounded structural fingerprint, not a .blend-file content hash."""
    objects = []
    for ob in sorted(scene.objects, key=lambda item: item.name):
        objects.append((ob.name, ob.type, getattr(ob.data, "name", ""),
                        len(ob.data.vertices) if ob.type == "MESH" else None,
                        [round(float(v), 7) for row in ob.matrix_world for v in row]))
    return _digest({"scene": scene.name, "objects": objects,
                    "settings": _quality(scene)})


def _node_link(tree, source, source_socket, target, target_socket):
    return any(l.from_node == source and l.from_socket == source_socket and
               l.to_node == target and l.to_socket == target_socket for l in tree.links)


def _preflight_graph(scene):
    if not scene.use_nodes:
        return "NEW"
    tree = scene.node_tree
    if tree is None:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE: compositor unavailable")
    names = set(_NODES.values())
    owned = [node for node in tree.nodes if node.name in names]
    if owned:
        if len(owned) != 4 or any(node.get("omega_owner") != _OWNER for node in owned):
            raise ValueError("CHECKPOINT_CONFLICT: incomplete Omega graph")
        if len(tree.nodes) != 4:
            raise ValueError("CHECKPOINT_CONFLICT: user compositor graph changed")
        return "OWNED"
    if any(node.bl_idname not in ("CompositorNodeRLayers", "CompositorNodeComposite")
           for node in tree.nodes) or len(tree.nodes) > 2:
        raise ValueError("CHECKPOINT_CONFLICT: user compositor graph must be preserved")
    if any(link.from_node.bl_idname != "CompositorNodeRLayers" or
           link.to_node.bl_idname != "CompositorNodeComposite" or
           link.from_socket.name != "Image" or link.to_socket.name != "Image"
           for link in tree.links):
        raise ValueError("CHECKPOINT_CONFLICT: user compositor links must be preserved")
    return "NEW"


def _preflight_material(bpy, scene, spec):
    ob = scene.objects.get(spec["object"])
    if ob is None or ob.type != "MESH":
        raise ValueError("MISSING_REFERENCE: named mesh not in scene")
    if ob.data.users > 1:
        raise ValueError("CHECKPOINT_CONFLICT: shared mesh material slots")
    material = bpy.data.materials.get(spec["material"])
    if material and material.get("omega_owner") != _OWNER:
        raise ValueError("CHECKPOINT_CONFLICT: existing user material")
    if material and material.get("omega_target") != ob.name:
        raise ValueError("CHECKPOINT_CONFLICT: material belongs to another object")
    if material and material.users > 1:
        raise ValueError("CHECKPOINT_CONFLICT: shared material")
    slots = ob.data.materials
    if len(slots) and (material is None or slots[0] != material) and not spec["replace_first_slot"]:
        raise ValueError("CHECKPOINT_CONFLICT: existing first material slot")
    return ob, material


def _make_material(bpy, spec, ob, material):
    if material is None:
        material = bpy.data.materials.new(spec["material"])
    material.use_nodes = True
    tree = material.node_tree
    # Only Omega-owned materials reach this branch (or freshly created ones).
    tree.nodes.clear()
    shader = tree.nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "OMEGA09_Principled"
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    output.name = "OMEGA09_MaterialOutput"
    for name in ("Base Color", "Metallic", "Roughness"):
        if name not in shader.inputs:
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE: Principled socket " + name)
    shader.inputs["Base Color"].default_value = (*spec["base_color"], 1.0)
    shader.inputs["Metallic"].default_value = spec["metallic"]
    shader.inputs["Roughness"].default_value = spec["roughness"]
    tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    if spec["bump_strength"] > 0:
        if "Normal" not in shader.inputs:
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE: Principled Normal")
        noise = tree.nodes.new("ShaderNodeTexNoise")
        bump = tree.nodes.new("ShaderNodeBump")
        noise.name, bump.name = "OMEGA09_Noise", "OMEGA09_Bump"
        bump.inputs["Strength"].default_value = spec["bump_strength"]
        tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        tree.links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    material["omega_owner"] = _OWNER
    material["omega_target"] = ob.name
    slots = ob.data.materials
    if not len(slots):
        slots.append(material)
    else:
        slots[0] = material
    return material


def _make_graph(scene, spec):
    scene.use_nodes = True
    tree = scene.node_tree
    nodes = tree.nodes
    def owned(key, type_name):
        node = nodes.get(_NODES[key])
        if node is None:
            candidate = next((item for item in nodes if item.bl_idname == type_name), None)
            node = candidate if candidate is not None else nodes.new(type_name)
            node.name = _NODES[key]
        node["omega_owner"] = _OWNER
        return node
    layer = owned("layer", "CompositorNodeRLayers")
    bright = owned("bright", "CompositorNodeBrightContrast")
    gamma = owned("gamma", "CompositorNodeGamma")
    output = owned("output", "CompositorNodeComposite")
    view_layer = spec.get("view_layer", scene.view_layers[0].name)
    layer.layer = view_layer
    bright.inputs["Bright"].default_value = 0
    bright.inputs["Contrast"].default_value = spec["contrast"]
    gamma.inputs["Gamma"].default_value = spec["gamma"]
    tree.links.new(layer.outputs["Image"], bright.inputs["Image"])
    tree.links.new(bright.outputs["Image"], gamma.inputs["Image"])
    selected = gamma if spec["mode"] == "FINAL" else layer
    tree.links.new(selected.outputs["Image"], output.inputs["Image"])
    if not (_node_link(tree, layer, layer.outputs["Image"], bright, bright.inputs["Image"]) and
            _node_link(tree, bright, bright.outputs["Image"], gamma, gamma.inputs["Image"]) and
            _node_link(tree, selected, selected.outputs["Image"], output, output.inputs["Image"])):
        raise ValueError("NATIVE_RENDER_UNCONFIRMED: compositor links")
    return (layer, bright, gamma, output)


def _read_grade(bpy, scene, spec):
    ob, mat = _preflight_material(bpy, scene, dict(spec, replace_first_slot=True))
    if mat is None or len(ob.data.materials) < 1 or ob.data.materials[0] != mat:
        raise ValueError("MISSING_REFERENCE: assigned native Omega material")
    shader = mat.node_tree.nodes.get("OMEGA09_Principled") if mat.use_nodes else None
    if shader is None or not any(link.from_node == shader and link.to_node.bl_idname == "ShaderNodeOutputMaterial"
                              for link in mat.node_tree.links):
        raise ValueError("MISSING_REFERENCE: Principled native link")
    if _preflight_graph(scene) != "OWNED":
        raise ValueError("MISSING_REFERENCE: native compositor")
    tree = scene.node_tree
    layer, bright, gamma, output = (tree.nodes[_NODES[key]] for key in ("layer", "bright", "gamma", "output"))
    expected = gamma if spec["mode"] == "FINAL" else layer
    if not _node_link(tree, expected, expected.outputs["Image"], output, output.inputs["Image"]):
        raise ValueError("CHECKPOINT_CONFLICT: compositor mode differs")
    if not _node_link(tree, layer, layer.outputs["Image"], bright, bright.inputs["Image"]) or not _node_link(tree, bright, bright.outputs["Image"], gamma, gamma.inputs["Image"]):
        raise ValueError("CHECKPOINT_CONFLICT: altered grade chain")
    return {"material": mat.name, "material_nodes": sorted(n.bl_idname for n in mat.node_tree.nodes),
            "base_color": list(shader.inputs["Base Color"].default_value),
            "metallic": float(shader.inputs["Metallic"].default_value),
            "roughness": float(shader.inputs["Roughness"].default_value),
            "mode": spec["mode"], "raw_source_linked": True,
            "grade_contrast": float(bright.inputs["Contrast"].default_value),
            "grade_gamma": float(gamma.inputs["Gamma"].default_value),
            "view_layer": layer.layer, "node_count": len(tree.nodes),
            "has_active_composite": True}


def _receipt(operation, scene, source_revision, created, details, native=False):
    return {"operation": operation, "state": "succeeded", "scene": scene.name if scene else None,
            "source_revision": source_revision, "created": created,
            "artifact": {"kind": "none", "sha256": None},
            "native_execution_verified": native,
            "visual_quality_verified": False, "quality_reduced": False,
            "warnings": ["Pixel grading remains unverified until a real render is inspected"],
            "details": details}


def _cache_dir(context, cache_id):
    if not isinstance(context, dict) or not context.get("production_root"):
        raise ValueError("MISSING_REFERENCE: app-owned production root not provided")
    root = Path(context["production_root"]).resolve(strict=True)
    folder = root / "omega_vfx_caches" / cache_id
    if folder.is_symlink() or not folder.is_dir() or folder.resolve(strict=True).parent != (root / "omega_vfx_caches").resolve():
        raise ValueError("MISSING_REFERENCE: app-owned cache directory missing")
    return folder


def _sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_cache(spec, context):
    folder = _cache_dir(context, spec["cache_id"])
    manifest = folder / "manifest.json"
    if manifest.is_symlink() or not manifest.is_file() or manifest.stat().st_size > (1 << 20):
        raise ValueError("MISSING_REFERENCE: bounded cache manifest missing")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError("INVALID_ARGUMENTS: cache manifest JSON") from exc
    if type(data) is not dict or set(data) != {"cache_id", "source_revision", "frames"}:
        raise ValueError("INVALID_ARGUMENTS: cache manifest schema")
    if data["cache_id"] != spec["cache_id"] or not isinstance(data["source_revision"], str) or not _HEX.fullmatch(data["source_revision"]):
        raise ValueError("CHECKPOINT_CONFLICT: cache revision/identity")
    frames = data["frames"]
    if type(frames) is not list or len(frames) > 240:
        raise ValueError("INVALID_ARGUMENTS: cache frame count")
    by_frame = {}
    total_bytes = 0
    for item in frames:
        if type(item) is not dict or set(item) != {"frame", "filename", "sha256", "bytes", "kind"}:
            raise ValueError("INVALID_ARGUMENTS: cache entry schema")
        frame = _int(item["frame"], 1, 100000)
        filename = item["filename"]
        if type(filename) is not str or not re.fullmatch(r"frame_[0-9]{6}\.(?:obj|ply|abc)", filename):
            raise ValueError("INVALID_ARGUMENTS: unsafe cache filename")
        if not filename.startswith("frame_%06d." % frame) or item["kind"] not in ("mesh", "particles", "foam"):
            raise ValueError("INVALID_ARGUMENTS: wrong cache frame/type")
        if type(item["sha256"]) is not str or not _HEX.fullmatch(item["sha256"]):
            raise ValueError("INVALID_ARGUMENTS: missing cache hash")
        _int(item["bytes"], 1, 128 * (1 << 20))
        total_bytes += item["bytes"]
        if total_bytes > 256 * (1 << 20):
            raise ValueError("UNSUPPORTED_NATIVE_FEATURE: cache inspection exceeds 256MiB admission budget")
        if frame in by_frame:
            raise ValueError("INVALID_ARGUMENTS: duplicate cache frame")
        by_frame[frame] = item
    expected = range(spec["frame_start"], spec["frame_end"] + 1)
    inspected = []
    for frame in expected:
        if frame not in by_frame:
            raise ValueError("MISSING_REFERENCE: cache gap at frame %d" % frame)
        item = by_frame[frame]
        file = folder / item["filename"]
        if file.is_symlink() or not file.is_file() or file.resolve(strict=True).parent != folder:
            raise ValueError("MISSING_REFERENCE: missing owner cache frame")
        if file.stat().st_size != item["bytes"] or _sha256_file(file) != item["sha256"]:
            raise ValueError("CHECKPOINT_CONFLICT: corrupt cache frame %d" % frame)
        inspected.append({"frame": frame, "file": file.name, "sha256": item["sha256"],
                          "bytes": item["bytes"], "kind": item["kind"]})
    return {"cache_id": spec["cache_id"], "source_revision": data["source_revision"],
            "frame_start": spec["frame_start"], "frame_end": spec["frame_end"],
            "verified_frames": len(inspected), "frames": inspected,
            "native_simulation_executed": False, "cache_imported_into_blender": False,
            "interchange_only": True}


def audit(operation: str, payload: dict, context: dict) -> dict:
    spec = validate(operation, payload)
    if operation == "omega.vfx.cache_inspect":
        return _inspect_cache(spec, context)
    scene = _scene(context)
    bpy = _bpy()
    return {"scene": scene.name, "source_revision": _scene_revision(scene),
            "native": _read_grade(bpy, scene, spec), "unchanged_final_render": _quality(scene),
            "visual_quality_verified": False}


def execute(operation: str, payload: dict, context: dict) -> dict:
    spec = validate(operation, payload)
    if operation == "omega.vfx.cache_inspect":
        details = _inspect_cache(spec, context)
        return _receipt(operation, None, details["source_revision"], [], details)
    scene = _scene(context)
    bpy = _bpy()
    if scene.get("production_frozen_job"):
        raise ValueError("CHECKPOINT_CONFLICT: immutable production snapshot")
    if context.get("cancellation_requested"):
        raise ValueError("CHECKPOINT_CONFLICT: cancellation requested")
    if context.get("dry_run"):
        return {"operation": operation, "state": "validated", "native_execution_verified": False,
                "quality_reduced": False, "scene": scene.name}
    view_layer = spec.get("view_layer", scene.view_layers[0].name)
    if view_layer not in scene.view_layers:
        raise ValueError("MISSING_REFERENCE: requested native view layer")
    job_id = context.get("job_id")
    if job_id is not None and (type(job_id) is not str or not re.fullmatch(r"[0-9a-f]{32}", job_id)):
        raise ValueError("INVALID_ARGUMENTS: invalid job id")
    _preflight_graph(scene)
    ob, mat = _preflight_material(bpy, scene, spec)
    current_revision = _scene_revision(scene)
    if "expected_scene_revision" in spec and current_revision != spec["expected_scene_revision"]:
        raise ValueError("CHECKPOINT_CONFLICT: source scene revision")
    config_hash = _digest(spec)
    if job_id and scene.get("omega09_last_job") == job_id:
        if scene.get("omega09_last_spec") != config_hash:
            raise ValueError("CHECKPOINT_CONFLICT: idempotency key reused")
        details = _read_grade(bpy, scene, spec)
        return _receipt(operation, scene, scene.get("omega09_last_source_revision"), [],
                        dict(details, replayed=True), native=True)
    before_settings = _quality(scene)
    original_material = ob.data.materials[0] if len(ob.data.materials) else None
    original_nodes = scene.use_nodes
    fresh_mat = mat is None
    try:
        applied = _make_material(bpy, spec, ob, mat)
        _make_graph(scene, spec)
        details = _read_grade(bpy, scene, spec)
        if before_settings != _quality(scene):
            raise ValueError("CHECKPOINT_CONFLICT: render quality settings changed")
    except Exception:
        if original_material is None and len(ob.data.materials):
            ob.data.materials.pop(index=0)
        elif original_material is not None and len(ob.data.materials):
            ob.data.materials[0] = original_material
        if fresh_mat:
            to_remove = bpy.data.materials.get(spec["material"])
            if to_remove is not None and to_remove.get("omega_owner") == _OWNER and to_remove.users == 0:
                bpy.data.materials.remove(to_remove)
        if not original_nodes:
            scene.use_nodes = False
        raise
    if job_id:
        scene["omega09_last_job"] = job_id
        scene["omega09_last_spec"] = config_hash
        scene["omega09_last_source_revision"] = current_revision
    details["replayed"] = False
    details["scene_frame"] = scene.frame_current
    details["revision_kind"] = "structural_scene_fingerprint_not_blend_checksum"
    return _receipt(operation, scene, current_revision,
                    [applied.name] if fresh_mat else [], details, native=True)
