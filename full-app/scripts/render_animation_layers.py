# SPDX-License-Identifier: GPL-2.0-or-later
"""Editable native cutout layers, a real parallax camera, and animated morphs.

The production dispatcher supplies the checkpoint and scene serialization.
Only newly created IDs and explicit assignments are rolled back on failure.
"""
import math

import bpy
from mathutils import Vector
import render_animation_layers_contract as C
from render_creator_ops import _Transaction, _mesh_object, _new_name, _object, _action, _curves


def _layer(tx, scene, p):
    _new_name(p["name"])
    if p["shape"] == "rectangle":
        points = [(-1,-1), (1,-1), (1,1), (-1,1)]
    elif p["shape"] == "ellipse":
        points = [(math.cos(i*math.tau/64), math.sin(i*math.tau/64)) for i in range(64)]
    else:
        points = p["points"]
    vertices = [(x*p["width"]/2, y*p["height"]/2, 0) for x,y in points]
    ob = _mesh_object(tx, scene, p["name"], vertices, [tuple(range(len(vertices)))])
    ob.location = (p["x"], p["y"], p["depth"])
    uv = ob.data.uv_layers.new(name="CutoutUV")
    for loop in ob.data.loops:
        x, y = points[loop.vertex_index]
        uv.data[loop.index].uv = ((x+1)/2, (y+1)/2)
    mat = tx.add("materials", bpy.data.materials.new(p["name"]+"_FlatColor"))
    mat.diffuse_color = (*p["color"], 1)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    output = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    emission = mat.node_tree.nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*p["color"], 1)
    emission.inputs["Strength"].default_value = 1
    mat.node_tree.links.new(emission.outputs["Emission"], output.inputs["Surface"])
    ob.data.materials.append(mat)
    ob["render_animation_layer"] = C.VERSION
    ob["render_animation_layer_shape"] = p["shape"]
    return {"object": ob.name, "shape": p["shape"], "vertices": len(vertices),
            "depth": p["depth"], "editable_mesh": True, "native_uv": True,
            "material": mat.name, "flat_color_shader": True, "plane": "XY"}


def _parallax(tx, scene, p):
    _new_name(p["name"])
    layers = [_object(scene, n, "MESH", editable=False) for n in p["layers"]]
    # Use actual evaluated world bounds, including parents and existing animation.
    # Depth must remain safe throughout this bounded shot, not only at the current frame.
    previous_frame, subframe = scene.frame_current, scene.frame_subframe
    depths = []
    try:
        for frame in (p["start"], (p["start"]+p["end"])/2, p["end"]):
            scene.frame_set(int(frame), subframe=frame-int(frame))
            depsgraph = bpy.context.evaluated_depsgraph_get()
            sample = []
            for ob in layers:
                evaluated = ob.evaluated_get(depsgraph)
                corners = [evaluated.matrix_world @ Vector(v) for v in evaluated.bound_box]
                if any(not math.isfinite(v) for point in corners for v in point):
                    raise ValueError("ANIMATION_LAYER_NONFINITE_BOUNDS")
                if any(p["distance"]-point.z <= .1 for point in corners):
                    raise ValueError("ANIMATION_CAMERA_MUST_BE_IN_FRONT_OF_LAYERS")
                sample.append(sum(point.z for point in corners)/8)
            depths.append(sample)
        if max(depths[0])-min(depths[0]) < .001:
            raise ValueError("ANIMATION_PARALLAX_REQUIRES_DISTINCT_DEPTHS")
        camera = tx.add("cameras", bpy.data.cameras.new(p["name"]+"_Data"))
        ob = tx.add("objects", bpy.data.objects.new(p["name"], camera))
        scene.collection.objects.link(ob)
        camera.type = "PERSP"
        camera.lens = p["lens_mm"]
        camera.clip_start = .01
        camera.clip_end = 2200
        action = _action(tx, ob, p["name"]+"_Parallax")
        ob.location = (-p["travel_x"]/2, -p["travel_y"]/2, p["distance"])
        ob.keyframe_insert(data_path="location", frame=p["start"])
        ob.location = (p["travel_x"]/2, p["travel_y"]/2, p["distance"])
        ob.keyframe_insert(data_path="location", frame=p["end"])
        for curve in _curves(action):
            for key in curve.keyframe_points:
                key.interpolation = p["interpolation"]
                if p["interpolation"] == "BEZIER":
                    key.handle_left_type = key.handle_right_type = "AUTO_CLAMPED"
            curve.update()
        old_camera = scene.camera
        tx.defer(lambda: setattr(scene, "camera", old_camera))
        scene.camera = ob
        ob["render_animation_parallax"] = C.VERSION
        return {"camera": ob.name, "object": ob.name, "action": action.name,
                "layers": p["layers"], "start_layer_depths": depths[0],
                "frame_range": [p["start"],p["end"]],
                "travel": [p["travel_x"],p["travel_y"],0],
                "projection": "perspective", "native_camera_keyframes": True,
                "layer_animations_unchanged": True,
                "depth_preflight_sample_frames": [p["start"],(p["start"]+p["end"])/2,p["end"]],
                "full_shot_collision_audit": False}
    finally:
        scene.frame_set(previous_frame, subframe=subframe)


def _morph(tx, scene, p):
    ob = _object(scene, p["object"], "MESH")
    if ob.data.shape_keys is not None:
        raise ValueError("ANIMATION_EXISTING_SHAPE_KEYS_PRESERVED")
    if not ob.data.polygons or not 4 <= len(ob.data.vertices) <= C.MAX_MORPH_VERTICES:
        raise ValueError("ANIMATION_MORPH_VERTEX_BUDGET")
    points = [v.co.copy() for v in ob.data.vertices]
    if any(not math.isfinite(v) for point in points for v in point):
        raise ValueError("ANIMATION_MORPH_NONFINITE_GEOMETRY")
    lower = Vector(tuple(min(v[i] for v in points) for i in range(3)))
    upper = Vector(tuple(max(v[i] for v in points) for i in range(3)))
    center, extent = (lower+upper)*.5, upper-lower
    size = max(extent)
    if size < .0001:
        raise ValueError("ANIMATION_MORPH_GEOMETRY_TOO_SMALL")
    axis = max(range(3), key=lambda i: extent[i])
    radial = [i for i in range(3) if i != axis]
    deformed = []
    for point in points:
        value = point.copy()
        relative = point-center
        t = (point[axis]-lower[axis])/extent[axis]
        if p["preset"] == "breathe":
            # Bulge through the middle, leaving both axial ends in place.
            factor = 1+p["amount"]*math.sin(math.pi*t)
            for i in radial:
                value[i] = center[i]+relative[i]*factor
        elif p["preset"] == "twist":
            angle = p["amount"]*math.pi*t
            c, s = math.cos(angle), math.sin(angle)
            a, b = radial
            value[a] = center[a]+relative[a]*c-relative[b]*s
            value[b] = center[b]+relative[a]*s+relative[b]*c
        else:
            # A half-wave displaces the middle while retaining anchored ends.
            value[radial[0]] += p["amount"]*size*.25*math.sin(math.pi*t)
        deformed.append(value)
    largest = max((a-b).length for a,b in zip(points,deformed))
    if largest <= 1e-7:
        raise ValueError("ANIMATION_MORPH_REQUIRES_INTERIOR_GEOMETRY")
    original = ob.data
    mesh = tx.add("meshes", original.copy())
    mesh.name = ob.name+"_MorphMesh"
    original_fake_user = original.use_fake_user
    tx.defer(lambda: setattr(original, "use_fake_user", original_fake_user))
    original.use_fake_user = True
    tx.defer(lambda: setattr(ob, "data", original))
    ob.data = mesh
    # Remove the newly created shape-key datablock before transaction cleanup on failure.
    tx.defer(lambda: ob.shape_key_clear())
    basis = ob.shape_key_add(name="Basis", from_mix=False)
    key = ob.shape_key_add(name=p["name"], from_mix=False)
    for dst, co in zip(key.data, deformed):
        dst.co = co
    shape_keys = mesh.shape_keys
    action = _action(tx, shape_keys, ob.name+"_"+p["name"])
    key.value = 0
    key.keyframe_insert(data_path="value", frame=p["start"])
    key.value = 1
    key.keyframe_insert(data_path="value", frame=(p["start"]+p["end"])/2)
    key.value = 0
    key.keyframe_insert(data_path="value", frame=p["end"])
    for curve in _curves(action):
        for frame_key in curve.keyframe_points:
            frame_key.interpolation = "BEZIER"
            frame_key.handle_left_type = frame_key.handle_right_type = "AUTO_CLAMPED"
        if p["loop"]:
            curve.modifiers.new("CYCLES")
        curve.update()
    scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
    return {"object": ob.name, "mesh": mesh.name, "preserved_original_mesh": original.name,
            "original_mesh_preserved_on_save": True,
            "shape_key": key.name, "basis": basis.name, "preset": p["preset"],
            "action": action.name, "vertices": len(points),
            "max_local_displacement": largest, "frame_range": [p["start"],p["end"]],
            "loop": p["loop"], "native_shape_keys": True,
            "object_transform_animation_preserved": True, "time_varying_3d": True}


_HANDLERS = {"studio.animation.layer.create": _layer,
             "studio.animation.parallax.create": _parallax,
             "studio.animation.morph.create": _morph}


def execute(operation, payload, root, scene):
    p = C.validate(operation, payload)
    if operation == "studio.animation.catalog":
        return C.catalog()
    if scene != bpy.context.scene:
        raise ValueError("ANIMATION_ACTIVE_SCENE_REQUIRED")
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        raise ValueError("ANIMATION_OBJECT_MODE_REQUIRED")
    with _Transaction() as tx:
        return _HANDLERS[operation](tx, scene, p)


dispatch = execute
