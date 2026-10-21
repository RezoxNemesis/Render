# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed and bounded one-command Blender mesh assembly for Render Android.

No arbitrary Python operator names, arbitrary filesystem paths, script eval,
network access, Gallery, or cloud Blender. The existing authenticated Blender
main-thread timer invokes this function. All parts are prevalidated before any
mesh creation and only newly-owned scene collection objects may be rolled back.
"""
import hashlib
import json
import math
import re

import bpy

VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
KINDS = frozenset(("CUBE", "CYLINDER", "CONE", "UV_SPHERE", "PLANE"))
PART_FIELDS = frozenset((
    "name", "kind", "location", "scale", "color", "metallic", "roughness", "bevel"
))


def _number(value, minimum, maximum):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def _triple(value, minimum, maximum):
    return (type(value) is list and len(value) == 3 and
            all(_number(x, minimum, maximum) for x in value))


def validate_assembly(args):
    """Preflight all fields before any Blender state mutation."""
    if type(args) is not dict or set(args) != {"assembly", "parts"}:
        raise ValueError("INVALID_ASSEMBLY_FIELDS")
    assembly = args["assembly"]
    parts = args["parts"]
    if type(assembly) is not str or not VALID_NAME.fullmatch(assembly):
        raise ValueError("INVALID_ASSEMBLY_NAME")
    if type(parts) is not list or not 1 <= len(parts) <= 96:
        raise ValueError("INVALID_ASSEMBLY_SIZE")
    seen = set()
    clean = []
    for part in parts:
        if type(part) is not dict or not {"name", "kind", "location", "scale"} <= set(part):
            raise ValueError("INVALID_ASSEMBLY_PART")
        if set(part) - PART_FIELDS:
            raise ValueError("UNKNOWN_ASSEMBLY_PART_FIELD")
        name, kind = part["name"], part["kind"]
        if type(name) is not str or not VALID_NAME.fullmatch(name) or name in seen:
            raise ValueError("INVALID_OR_DUPLICATE_PART_NAME")
        seen.add(name)
        if type(kind) is not str or kind not in KINDS:
            raise ValueError("INVALID_PART_KIND")
        if not _triple(part["location"], -10000, 10000):
            raise ValueError("INVALID_PART_LOCATION")
        if not _triple(part["scale"], .001, 1000):
            raise ValueError("INVALID_PART_SCALE")
        color = part.get("color", [.72, .73, .75])
        if not _triple(color, 0, 1):
            raise ValueError("INVALID_PART_COLOR")
        metal = part.get("metallic", 0)
        rough = part.get("roughness", .52)
        bevel = part.get("bevel", 0)
        if not (_number(metal, 0, 1) and _number(rough, 0, 1) and
                _number(bevel, 0, .25)):
            raise ValueError("INVALID_PART_SURFACE")
        clean.append({
            "name": name, "kind": kind,
            "location": list(map(float, part["location"])),
            "scale": list(map(float, part["scale"])),
            "color": list(map(float, color)), "metallic": float(metal),
            "roughness": float(rough), "bevel": float(bevel)
        })
    canonical = {"assembly": assembly, "parts": clean}
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return assembly, clean, digest


def _operator(kind):
    if kind == "CUBE":
        return bpy.ops.mesh.primitive_cube_add(size=2)
    if kind == "CYLINDER":
        return bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1, depth=2)
    if kind == "CONE":
        return bpy.ops.mesh.primitive_cone_add(vertices=24, radius1=1, depth=2)
    if kind == "UV_SPHERE":
        return bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24, ring_count=12, radius=1)
    return bpy.ops.mesh.primitive_plane_add(size=2)


def _material(part, material_name):
    material = bpy.data.materials.new(material_name)
    material.diffuse_color = (*part["color"], 1)
    material.use_nodes = True
    surface = material.node_tree.nodes.get("Principled BSDF")
    if surface:
        surface.inputs["Base Color"].default_value = (*part["color"], 1)
        surface.inputs["Metallic"].default_value = part["metallic"]
        surface.inputs["Roughness"].default_value = part["roughness"]
    return material


def apply_assembly(scene, args):
    key, parts, digest = validate_assembly(args)
    # A stable digest guards against duplicate edits after lost MCP receipts.
    prior = next((collection for collection in scene.collection.children
                  if collection.get("render_assembly_key") == key), None)
    if prior is not None:
        if prior.get("render_assembly_digest") != digest:
            raise ValueError("ASSEMBLY_NAME_REVISION_CONFLICT")
        if prior.get("render_assembly_complete", False):
            return {
                "assembly": key, "created_count": len(prior.objects),
                "already_complete": True, "digest": digest,
                "executed_by": "bpy-main-thread-on-android",
                "native_scene": scene.name
            }
        # The previous Blender operation was interrupted. Only undo objects
        # belonging to our incomplete collection; never touch user geometry.
        for ob in list(prior.objects):
            if ob.get("render_part_owner") != digest:
                raise RuntimeError("UNOWNED_INCOMPLETE_PART_REQUIRES_RECOVERY")
        for ob in list(prior.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        scene.collection.children.unlink(prior)
        bpy.data.collections.remove(prior)

    collection = bpy.data.collections.new("RA_Assembly_" + key)
    scene.collection.children.link(collection)
    collection["render_assembly_key"] = key
    collection["render_assembly_digest"] = digest
    collection["render_assembly_complete"] = False
    built = []
    created_materials = []
    try:
        for part in parts:
            result = _operator(part["kind"])
            if "FINISHED" not in result:
                raise RuntimeError("NATIVE_MESH_OPERATOR_FAILED")
            ob = bpy.context.object
            if ob is None or ob.type != "MESH":
                raise RuntimeError("NATIVE_MESH_OBJECT_MISSING")
            ob.name = "RA_" + part["name"]
            # Move the object from the Blender default collection into our
            # scene-owned assembly; the user's other scene is unaffected.
            for parent in list(ob.users_collection):
                parent.objects.unlink(ob)
            collection.objects.link(ob)
            ob["render_part_owner"] = digest
            ob.location = part["location"]
            ob.scale = part["scale"]
            mat = _material(part, "RA_Material_" + key + "_" + part["name"])
            created_materials.append(mat)
            ob.data.materials.clear()
            ob.data.materials.append(mat)
            if part["kind"] in ("UV_SPHERE", "CYLINDER"):
                for polygon in ob.data.polygons:
                    polygon.use_smooth = True
            if part["bevel"] > 0:
                modifier = ob.modifiers.new("Render_EdgeBevel", "BEVEL")
                modifier.width = part["bevel"]
                modifier.segments = 3
            built.append(ob)
        bpy.context.view_layer.update()
        collection["render_assembly_complete"] = True
        return {
            "assembly": key, "created_count": len(built),
            "mesh_count": len(built), "material_count": len(created_materials),
            "objects": [ob.name for ob in built],
            "already_complete": False, "digest": digest,
            "native_scene": scene.name,
            "executed_by": "bpy-main-thread-on-android"
        }
    except Exception:
        # Roll back only owned new parts. Never delete another scene or the
        # existing user's Blender building.
        for ob in list(collection.objects):
            if ob.get("render_part_owner") == digest:
                bpy.data.objects.remove(ob, do_unlink=True)
        for mat in created_materials:
            if mat.users == 0:
                bpy.data.materials.remove(mat)
        scene.collection.children.unlink(collection)
        bpy.data.collections.remove(collection)
        raise
