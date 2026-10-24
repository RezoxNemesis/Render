# SPDX-License-Identifier: GPL-2.0-or-later
"""Staged review/sculpt controls. Native geometry work runs only inside Android bpy."""
import math
import contextlib

VIEWS = ('FRONT', 'BACK', 'LEFT', 'RIGHT', 'THREE_QUARTER')


def _number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('CHARACTER_VALUE_OUT_OF_RANGE')
    return float(value)


def review_options(p):
    view = p.get('view', 'FRONT')
    if view not in VIEWS:
        raise ValueError('CHARACTER_REVIEW_VIEW_UNAVAILABLE')
    return view, _number(p.get('aspect', 1), .1, 10), _number(p.get('margin', 1.15), 1.01, 3)


def sculpt_plan(dimensions, scale_length, voxel_size_m, max_voxels, available_bytes):
    if not isinstance(dimensions, (list, tuple)) or len(dimensions) != 3:
        raise ValueError('INVALID_SCULPT_BOUNDS')
    scale = _number(scale_length, 1e-9, 1e9)
    voxel = _number(voxel_size_m, .0001, .1) / scale
    if type(max_voxels) is not int or not 1000 <= max_voxels <= 32_000_000:
        raise ValueError('INVALID_SCULPT_VOXEL_BUDGET')
    cells = math.prod(math.ceil(_number(d, 1e-9, 1e12) / voxel) + 4 for d in dimensions)
    if cells > max_voxels:
        raise ValueError('SCULPT_VOXEL_BUDGET_EXCEEDED: choose an explicit voxel size or budget; no automatic coarsening')
    estimate = cells * 192 + 256 * 1024 * 1024
    if available_bytes is not None:
        if type(available_bytes) is not int or available_bytes <= 0:
            raise ValueError('INVALID_SCULPT_MEMORY_SIGNAL')
        if estimate > available_bytes:
            raise ValueError('SCULPT_MEMORY_PRESSURE: preserve checkpoint and free memory; no automatic coarsening')
    return {'voxel_size_m': voxel_size_m, 'voxel_size_scene_units': voxel,
            'estimated_voxel_cells': cells, 'estimated_working_bytes_with_reserve': estimate,
            'memory_available_bytes': available_bytes, 'memory_estimate_is_heuristic': True,
            'automatic_quality_reduction': False}


def mesh_components(vertices, edges):
    parent = list(range(vertices))
    def find(v):
        while parent[v] != v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v
    count = vertices
    for a, b in edges:
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b
            count -= 1
    return count


def _bounds(ob):
    import bpy
    from mathutils import Vector
    bpy.context.view_layer.update()
    evaluated = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
    center = sum(points, Vector()) / 8
    radius = max((point-center).length for point in points)
    if not math.isfinite(radius) or radius <= 1e-9:
        raise ValueError('CHARACTER_REVIEW_EMPTY_OR_INVALID_BOUNDS')
    return points, center, radius


def _rotation(view):
    from mathutils import Vector
    offset = Vector({'FRONT': (0,-1,0), 'BACK': (0,1,0), 'LEFT': (-1,0,0),
                     'RIGHT': (1,0,0), 'THREE_QUARTER': (1,-2,.2)}[view]).normalized()
    return offset, (-offset).to_track_quat('-Z', 'Y')


def camera_frame(scene, ob, name, p):
    import bpy
    view, aspect, margin = review_options(dict({'aspect': scene.render.resolution_x * scene.render.pixel_aspect_x /
        (scene.render.resolution_y * scene.render.pixel_aspect_y)}, **p))
    points, center, radius = _bounds(ob)
    offset, rotation = _rotation(view)
    local = [rotation.inverted() @ (point-center) for point in points]
    width = max(v.x for v in local)-min(v.x for v in local)
    height = max(v.y for v in local)-min(v.y for v in local)
    scale = max(height, width/aspect) * margin
    if name in bpy.data.objects:
        raise ValueError('REVIEW_CAMERA_NAME_EXISTS')
    camera = bpy.data.cameras.new(name)
    created = None
    previous = scene.camera
    try:
        created = bpy.data.objects.new(name, camera)
        scene.collection.objects.link(created)
        camera.type = 'ORTHO'
        camera.sensor_fit = 'VERTICAL'  # ortho_scale is the vertical span at every requested aspect.
        camera.ortho_scale = scale
        if not math.isclose(camera.ortho_scale, scale, rel_tol=1e-6):
            raise ValueError('NATIVE_ORTHOGRAPHIC_SCALE_WAS_CLAMPED')
        camera.clip_start = max(radius/1000, .000001)
        camera.clip_end = radius*8
        created.location = center + offset * (radius*4)
        created.rotation_euler = rotation.to_euler()
        scene.camera = created
        return {'camera': created.name, 'target': ob.name, 'view': view,
                'projection': camera.type, 'ortho_scale': camera.ortho_scale,
                'framing_aspect': aspect, 'margin': margin,
                'previous_camera': previous.name if previous else None,
                'geometry_changed': False, 'render_quality_changed': False,
                'visual_proportions_verified': False}
    except Exception:
        scene.camera = previous
        if created is not None:
            bpy.data.objects.remove(created, do_unlink=True)
        if camera.users == 0:
            bpy.data.cameras.remove(camera)
        raise


def viewport_orient(scene, ob, p):
    import bpy
    view, _, margin = review_options(p)
    _, center, radius = _bounds(ob)
    _, rotation = _rotation(view)
    window = bpy.context.window
    areas = [a for a in window.screen.areas if a.type == 'VIEW_3D'] if window else []
    if not areas:
        raise ValueError('NATIVE_VIEWPORT_NOT_OPEN')
    for area in areas:
        space = area.spaces.active
        space.region_3d.view_rotation = rotation
        space.region_3d.view_location = center
        space.region_3d.view_distance = radius*2.4*margin
        space.region_3d.view_perspective = 'ORTHO'
        space.clip_start = max(radius/1000, .000001)
        space.clip_end = radius*10
        area.tag_redraw()
    return {'object': ob.name, 'view': view, 'projection': 'ORTHO',
            'native_viewports_oriented': len(areas), 'render_quality_changed': False,
            'performed_visible_pointer_click': False, 'visual_proportions_verified': False}


def _available_memory():
    try:
        with open('/proc/meminfo') as stream:
            for line in stream:
                if line.startswith('MemAvailable:'):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def sculpt_prepare(scene, source, name, p, target_context):
    import bpy
    if name in bpy.data.objects:
        raise ValueError('SCULPT_OBJECT_NAME_EXISTS')
    if (source.data.shape_keys or source.vertex_groups or source.data.uv_layers or source.animation_data
            or any(mod.type == 'ARMATURE' for mod in source.modifiers)):
        raise ValueError('SCULPT_PREPARE_REQUIRES_UNRIGGED_UNTEXTURED_SOURCE: original remains editable')
    if p.get('hide_source', False) and len(source.users_scene) > 1:
        raise ValueError('SCULPT_SOURCE_SHARED_WITH_ANOTHER_SCENE')
    for key in ('hide_source', 'require_connected'):
        if key in p and type(p[key]) is not bool:
            raise ValueError('INVALID_SCULPT_BOOLEAN')
    points, _, _ = _bounds(source)
    dimensions = [max(point[i] for point in points)-min(point[i] for point in points) for i in range(3)]
    memory = _available_memory()
    if memory is None:
        raise ValueError('SCULPT_MEMORY_TELEMETRY_UNAVAILABLE')
    plan = sculpt_plan(dimensions, scene.unit_settings.scale_length, p['voxel_size_m'],
                       p.get('max_voxels', 8_000_000), memory)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    previous_hide_render, previous_hide_view = source.hide_render, source.hide_get()
    mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    created = None
    try:
        mesh.transform(evaluated.matrix_world)
        created = bpy.data.objects.new(name, mesh)
        created.color = source.color
        scene.collection.objects.link(created)
        mesh.remesh_voxel_size = plan['voxel_size_scene_units']
        mesh.remesh_voxel_adaptivity = 0
        mesh.use_remesh_preserve_volume = True
        with target_context(scene, created):
            if not bpy.ops.object.voxel_remesh.poll():
                raise ValueError('NATIVE_VOXEL_REMESH_CONTEXT_UNAVAILABLE')
            if 'FINISHED' not in bpy.ops.object.voxel_remesh():
                raise RuntimeError('NATIVE_VOXEL_REMESH_NOT_FINISHED')
        if not len(created.data.vertices) or not len(created.data.polygons):
            raise RuntimeError('NATIVE_SCULPT_SURFACE_EMPTY')
        components = mesh_components(len(created.data.vertices), (edge.vertices for edge in created.data.edges))
        if p.get('require_connected', True) and components != 1:
            raise ValueError('SCULPT_VOLUMES_STILL_DISCONNECTED: correct overlap before union')
        for polygon in created.data.polygons:
            polygon.use_smooth = True
        created['render_work_stage'] = '02_sculpt_preparation'
        created['render_sculpt_union_pending'] = components != 1
        created['render_likeness_verified'] = False
        if p.get('hide_source', False):
            source.hide_render = True
            source.hide_set(True)
        return dict(plan, object=created.name, source_object=source.name,
                    source_geometry_preserved=True, source_hidden=p.get('hide_source', False),
                    vertices=len(created.data.vertices), polygons=len(created.data.polygons),
                    connected_components=components, sculpt_union_pending=components != 1,
                    topology_changed_explicitly=True, body_sculpt_completed=False,
                    facial_likeness_verified=False, native_voxel_remesh_completed=True)
    except Exception:
        source.hide_render = previous_hide_render
        with contextlib.suppress(RuntimeError):
            source.hide_set(previous_hide_view)
        replacement = created.data if created is not None else None
        if created is not None:
            bpy.data.objects.remove(created, do_unlink=True)
        if replacement is not None and replacement != mesh and replacement.users == 0:
            bpy.data.meshes.remove(replacement)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise
