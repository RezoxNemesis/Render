# SPDX-License-Identifier: GPL-2.0-or-later
"""Live native Blender Sculpt Mode, real brush strokes and measured receipts.

This does not simulate human pointer events. The owner may sculpt in Blender's
actual viewport, or an authorised MCP command can supply a bounded projected
stroke to bpy.ops.sculpt.brush_stroke. Never replace a failed stroke with an
object-space approximation or claim photo likeness from a successful operator.
"""
import hashlib
import struct

import bpy
import render_artist_direct_contract as Contract

_LAST_STROKE = None

def _mesh(scene, name):
    ob = scene.objects.get(name)
    if ob is None or ob.type != "MESH":
        raise ValueError("DIRECT_SCULPT_MESH_NOT_FOUND")
    if not ob.visible_get() or ob.hide_get():
        raise ValueError("DIRECT_SCULPT_MESH_NOT_VISIBLE")
    if ob.data.users != 1:
        raise ValueError("DIRECT_SCULPT_SHARED_MESH_COPY_FIRST")
    return ob

def _view(index):
    win = bpy.context.window
    if win is None or win.screen is None or getattr(bpy.app,"background",False):
        raise ValueError("DIRECT_SCULPT_VISIBLE_BLENDER_REQUIRED")
    areas = [a for a in win.screen.areas if a.type == "VIEW_3D"]
    if index >= len(areas):
        raise ValueError("DIRECT_SCULPT_VIEWPORT_UNAVAILABLE")
    area = areas[index]
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    if region is None or region.width < 2 or region.height < 2:
        raise ValueError("DIRECT_SCULPT_VIEWPORT_UNAVAILABLE")
    space = area.spaces.active
    if space.region_3d is None:
        raise ValueError("DIRECT_SCULPT_VIEW_MATRIX_UNAVAILABLE")
    revision = Contract.view_digest(region.width,region.height,space.region_3d.view_matrix)
    return win, area, region, revision

def _revision(obj):
    mesh = obj.data
    n = len(mesh.vertices)
    if n > Contract.MAX_HASH_VERTICES:
        raise ValueError("DIRECT_SCULPT_MESH_TOO_DENSE_FOR_VERIFIED_STROKE")
    digest = hashlib.sha256()
    digest.update(struct.pack("!QQ", n, len(mesh.polygons)))
    for vertex in mesh.vertices:
        digest.update(struct.pack("!fff",float(vertex.co.x),float(vertex.co.y),float(vertex.co.z)))
    return digest.hexdigest()

def _components(obj):
    mesh = obj.data
    n = len(mesh.vertices)
    if n > 250000 or len(mesh.edges) > 1000000:
        return {"connected_components":None,"connectivity_verified":False,
                "reason":"TOPOLOGY_AUDIT_BUDGET","connected_character_claimed":False}
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for edge in mesh.edges:
        a,b = edge.vertices
        ra, rb = find(a), find(b)
        if ra != rb:parent[rb] = ra
    roots = {find(i) for i in range(n)}
    return {"connected_components":len(roots),"connectivity_verified":True,
            "connected_character_claimed":len(roots)==1,
            "disconnected_shells_require_join_or_retessellation":len(roots)>1}

def _brush_info():
    sculpt = getattr(bpy.context.tool_settings,"sculpt",None)
    brush = getattr(sculpt,"brush",None)
    return ({"active_brush":getattr(brush,"name",None),
             "active_sculpt_brush_loaded":brush is not None,
             "brush_size_px":getattr(brush,"size",None),
             "brush_strength":getattr(brush,"strength",None)}
            if brush is not None else {
                "active_brush":None,"active_sculpt_brush_loaded":False})

def inspect(scene,p):
    Contract.validate(Contract.OPS[0],p)
    obj = _mesh(scene,p["object"])
    win,area,region,view_sha = _view(p.get("viewport_index",0))
    return {"object":obj.name,
            "native_scene":scene.name,"native_window_open":True,
            "mode":obj.mode,"active_object":getattr(bpy.context.active_object,"name",None),
            "viewport_width":region.width,"viewport_height":region.height,
            "view_revision_sha256":view_sha,
            "mesh_revision_sha256":_revision(obj),
            "base_vertices":len(obj.data.vertices),"base_polygons":len(obj.data.polygons),
            "modifier_types":[m.type for m in obj.modifiers][:64],
            "shape_keys_present":obj.data.shape_keys is not None,
            **_components(obj),**_brush_info(),
            "real_brush_stroke_requires_active_sculpt_mode":True,
            "surface_beauty_or_likeness_verified":False,
            "live_touch_mapping_on_this_phone_verified":False,
            "no_arbitrary_python":True}

def enter(scene,p):
    Contract.validate(Contract.OPS[1],p)
    obj = _mesh(scene,p["object"])
    win,area,region,sha = _view(p.get("viewport_index",0))
    if bpy.app.is_job_running("RENDER"):
        raise ValueError("DIRECT_SCULPT_RENDER_BUSY")
    with bpy.context.temp_override(window=win,area=area,region=region,scene=scene):
        active=bpy.context.view_layer.objects.active
        if active and active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for selected in list(bpy.context.selected_objects):
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        if not bpy.ops.object.mode_set.poll():
            raise ValueError("DIRECT_SCULPT_MODE_UNAVAILABLE")
        bpy.ops.object.mode_set(mode="SCULPT")
    if obj.mode != "SCULPT":
        raise ValueError("DIRECT_SCULPT_MODE_NOT_ENTERED")
    area.tag_redraw()
    return {"object":obj.name,"native_mode":obj.mode,
            "real_blender_sculpt_mode_active":True,
            "user_touch_uses_native_blender_input":True,
            "simulated_pointer_taps":False,
            "live_touch_mapping_on_this_phone_verified":False,
            "visual_outcome_verified":False}

def leave(scene,p):
    Contract.validate(Contract.OPS[3],p)
    obj = _mesh(scene,p["object"])
    win,area,region,_ = _view(p.get("viewport_index",0))
    if obj is not bpy.context.view_layer.objects.active or obj.mode!="SCULPT":
        raise ValueError("DIRECT_SCULPT_TARGET_NOT_ACTIVE")
    with bpy.context.temp_override(window=win,area=area,region=region,scene=scene):
        bpy.ops.object.mode_set(mode="OBJECT")
    area.tag_redraw()
    return {"object":obj.name,"mode":obj.mode,"mesh_preserved":True}

def stroke(scene,p):
    """Commit exactly one visible Blender brush stroke; reject unproven effects."""
    global _LAST_STROKE
    Contract.validate(Contract.OPS[2],p)
    obj=_mesh(scene,p["object"])
    win,area,region,view_sha=_view(p.get("viewport_index",0))
    if bpy.app.is_job_running("RENDER"):
        raise ValueError("DIRECT_SCULPT_RENDER_BUSY")
    if obj.mode!="SCULPT" or bpy.context.view_layer.objects.active is not obj:
        raise ValueError("DIRECT_SCULPT_ENTER_TARGET_FIRST")
    if p["expected_view_sha256"]!=view_sha:
        raise ValueError("DIRECT_SCULPT_VIEW_REVISION_CONFLICT")
    prior=_revision(obj)
    if p["expected_mesh_sha256"]!=prior:
        raise ValueError("DIRECT_SCULPT_MESH_REVISION_CONFLICT")
    if not _brush_info()["active_sculpt_brush_loaded"]:
        raise ValueError("DIRECT_SCULPT_BRUSH_NOT_SELECTED")
    from render_artist_ops import _operator
    op=_operator("sculpt.brush_stroke")
    points=Contract.to_operator_stroke(p["points"],region.width,region.height)
    before=len(obj.data.vertices)
    coords=[(float(v.co.x),float(v.co.y),float(v.co.z)) for v in obj.data.vertices]
    with bpy.context.temp_override(window=win,area=area,region=region,scene=scene):
        if not op.poll():
            raise ValueError("DIRECT_SCULPT_BRUSH_CONTEXT_UNAVAILABLE")
        # This invokes Blender's own brush kernel. No object-space fake brush.
        completed=op(stroke=points,mode="NORMAL",override_location=True,ignore_background_click=True)
    if "FINISHED" not in completed:
        raise ValueError("DIRECT_SCULPT_BRUSH_NOT_FINISHED")
    obj.data.update()
    bpy.context.view_layer.update()
    after=_revision(obj)
    if after==prior:
        raise ValueError("DIRECT_SCULPT_NO_MEASURED_MESH_CHANGE")
    count=len(obj.data.vertices)
    edited=(sum(
        1 for old,v in zip(coords,obj.data.vertices)
        if old!=(float(v.co.x),float(v.co.y),float(v.co.z))
    ) if count==before else None)
    if edited==0:
        raise ValueError("DIRECT_SCULPT_NO_MEASURED_MESH_CHANGE")
    for window in bpy.context.window_manager.windows:
        for part in window.screen.areas:
            if part.type=="VIEW_3D":part.tag_redraw()
    _LAST_STROKE={"object":obj.name,"before":prior,"after":after,
                  "changed_vertices":edited,"viewport_sha256":view_sha}
    return {"object":obj.name,"native_blender_brush_stroke_completed":True,
            "sculpt_kernel":"bpy.ops.sculpt.brush_stroke",
            "screen_stroke_points":len(points),
            "geometry_revision_before":prior,"geometry_revision_after":after,
            "vertices_before":before,"vertices_after":count,
            "base_vertices_changed":edited,
            "mesh_change_verified":True,
            "native_viewport_redraw_requested":True,
            "same_visible_view_used":True,
            "human_pointer_events_fabricated":False,
            "native_touch_replay_claimed":False,
            "photorealism_or_anatomical_quality_verified":False}

def execute(op,p,root,scene):
    if op==Contract.OPS[0]:return inspect(scene,p)
    if op==Contract.OPS[1]:return enter(scene,p)
    if op==Contract.OPS[2]:return stroke(scene,p)
    if op==Contract.OPS[3]:return leave(scene,p)
    raise ValueError("DIRECT_SCULPT_OPERATION_UNAVAILABLE")

def last_stroke():
    return dict(_LAST_STROKE) if _LAST_STROKE else None
