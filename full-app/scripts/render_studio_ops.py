# SPDX-License-Identifier: GPL-2.0-or-later
"""Registered reference-guided visual authoring actions on native Android bpy.

All camera/object edits run on Blender's main thread through the existing spool.
No arbitrary Python/eval, remote execution, filesystem paths or fake pointer taps.
"""
import math
import importlib.util
from pathlib import Path
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

_contract=Path(__file__).with_name('render_studio_contract.py')
_spec=importlib.util.spec_from_file_location('render_studio_contract',_contract)
C=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(C)

_ALLOWED={
    'object.shade_smooth': {'fields':('object',)},
    'object.shade_flat': {'fields':('object',)},
    'object.add_modifier': {'fields':('object','type','name','levels','width','thickness')},
    'object.origin_to_geometry': {'fields':('object',)},
    'object.transform_apply': {'fields':('object','location','rotation','scale')},
    'object.modifier_apply': {'fields':('object','modifier')},
    'object.modifier_remove': {'fields':('object','modifier')},
    'mesh.subdivide': {'fields':('object','cuts')},
    'mesh.recalculate_normals': {'fields':('object',)},
    'mesh.merge_by_distance': {'fields':('object','distance')},
    'uv.smart_project': {'fields':('object','angle_degrees','island_margin')},
}
_MODIFIERS={'SUBSURF','BEVEL','SOLIDIFY','MIRROR','WEIGHTED_NORMAL','DECIMATE','ARRAY','CLOTH'}
def _check(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError('INVALID_STUDIO_ARGUMENTS')
def _name(v):
    if not isinstance(v,str) or not C.NAME.fullmatch(v):raise ValueError('INVALID_NAME')
    return v
def _object(scene,p,kind=None):
    ob=scene.objects.get(_name(p))
    if ob is None or kind is not None and ob.type!=kind:raise ValueError('TARGET_OBJECT_MISSING_OR_WRONG_TYPE')
    return ob
def _areas():
    window=bpy.context.window
    if window is None:return []
    return [(area,area.spaces.active) for area in window.screen.areas if area.type=='VIEW_3D']
def _info(area,space):
    region=space.region_3d
    return {'width_pixels':area.width,'height_pixels':area.height,
            'clip_start':space.clip_start,'clip_end':space.clip_end,
            'clip_ratio':space.clip_end/space.clip_start if space.clip_start else None,
            'view_distance':region.view_distance,'view_location':list(region.view_location),
            'perspective':region.view_perspective,'viewport_render_engine_unchanged':True}
def _bounding(ob):
    if ob.type in ('MESH','CURVE','SURFACE','FONT'):
        corners=[ob.matrix_world @ Vector(corner) for corner in ob.bound_box]
        center=sum(corners,Vector())/8
        radius=max((p-center).length for p in corners)
        return center,max(radius,1e-6)
    return ob.matrix_world.translation,1
def _register_property(ob,key,value):
    ob[key]=value
def _asset(root,filename):
    if not isinstance(filename,str) or '.' not in filename:raise ValueError('INVALID_ASSET_NAME')
    stem,ext=filename.rsplit('.',1)
    filename=C.asset_name(stem,ext)
    path=C.owned_path(root/'Assets',filename)
    if not path.is_file():raise ValueError('OWNER_REFERENCE_NOT_IMPORTED')
    import hashlib
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):h.update(chunk)
    if h.hexdigest()!=stem:raise ValueError('OWNER_REFERENCE_HASH_MISMATCH')
    return path
def _board(scene,root,p):
    _check(p,C.SCHEMAS['reference.bind']['fields'],('asset','name'))
    name=_name(p['name'])
    if name in bpy.data.objects:raise ValueError('REFERENCE_NAME_EXISTS')
    imagepath=_asset(root,p['asset'])
    if imagepath.suffix.lower()=='.mp4':raise ValueError('BIND_VIDEO_SAMPLE_PNG_FIRST')
    crop=C.crop_rect(p.get('crop',[0,0,1,1]))
    center=p.get('location',[0,-1,1])
    if not isinstance(center,list) or len(center)!=3:raise ValueError('INVALID_LOCATION')
    center=[C.finite(v,-1e6,1e6) for v in center]
    size=C.finite(p.get('size',1.8),.001,10000)
    opacity=C.finite(p.get('opacity',.72),.02,1)
    mode=p.get('mode','BOARD')
    if mode not in ('BOARD','CAMERA_BACKGROUND'):raise ValueError('INVALID_REFERENCE_MODE')
    image=bpy.data.images.load(str(imagepath),check_existing=True)
    if not image.packed_file:image.pack()
    if image.size[0]<1 or image.size[1]<1:raise ValueError('CORRUPT_REFERENCE_IMAGE')
    if mode=='CAMERA_BACKGROUND':
        if scene.camera is None:raise ValueError('CAMERA_REQUIRED')
        cam=scene.camera.data
        cam.show_background_images=True
        background=cam.background_images.new()
        background.image=image
        background.alpha=opacity
        background.display_depth='BACK'
        return {'mode':mode,'camera':scene.camera.name,'asset':imagepath.name,
                'packed':image.packed_file is not None,
                'crop_supported_in_camera_background':False,
                'unseen_geometry':'inferred','image_is_3d_model':False}
    cropped_aspect=(image.size[0]*(crop[2]-crop[0]))/(image.size[1]*(crop[3]-crop[1]))
    sx=size;sy=size/cropped_aspect
    mesh=bpy.data.meshes.new(name+'Mesh')
    mesh.from_pydata([(-sx/2,0,-sy/2),(sx/2,0,-sy/2),
                      (sx/2,0,sy/2),(-sx/2,0,sy/2)],[],[(0,1,2,3)])
    mesh.update()
    uv=mesh.uv_layers.new(name='ReferenceCrop')
    u0,v0,u1,v1=crop
    coords=((u0,1-v1),(u1,1-v1),(u1,1-v0),(u0,1-v0))
    for loop,coord in zip(mesh.polygons[0].loop_indices,coords):uv.data[loop].uv=coord
    mat=bpy.data.materials.new(name+'ImageMaterial')
    mat.use_nodes=True
    nt=mat.node_tree;nt.nodes.clear()
    tex=nt.nodes.new('ShaderNodeTexImage');tex.image=image
    emission=nt.nodes.new('ShaderNodeEmission');emission.inputs['Strength'].default_value=1
    output=nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tex.outputs['Color'],emission.inputs['Color'])
    nt.links.new(emission.outputs[0],output.inputs['Surface'])
    mesh.materials.append(mat)
    ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
    ob.location=center
    ob.hide_render=True
    ob.hide_select=False
    _register_property(ob,'render_source_hash',imagepath.name.split('.')[0])
    _register_property(ob,'render_crop_top_left',list(crop))
    _register_property(ob,'render_reference_only',True)
    _register_property(ob,'render_unseen_geometry','inferred')
    return {'object':ob.name,'mode':mode,'asset':imagepath.name,
            'native_uv_crop':crop,'reference_aspect':cropped_aspect,'packed':image.packed_file is not None,
            'visible_in_viewport':True,'included_in_final_render':False,
            'is_3d_reconstruction':False,'likeness_verified':False}
def _compare(scene,p):
    _check(p,C.SCHEMAS['reference.landmarks']['fields'],('object','reference','model'))
    ob=_object(scene,p['object'],'MESH')
    if scene.camera is None:raise ValueError('CAMERA_REQUIRED')
    marks=C.landmarks(p['reference']);model=p['model']
    if not isinstance(model,dict) or set(model)!=set(marks):raise ValueError('LANDMARKS_MISMATCH')
    bpy.context.view_layer.update()
    projected={}
    for label,index in model.items():
        if type(index) is not int or not 0<=index<len(ob.data.vertices):raise ValueError('INVALID_MESH_LANDMARK_INDEX')
        position=ob.matrix_world @ ob.data.vertices[index].co
        ndc=world_to_camera_view(scene,scene.camera,position)
        if ndc.z<=0 or not (0<=ndc.x<=1 and 0<=ndc.y<=1):
            raise ValueError('MODEL_LANDMARK_OUTSIDE_CAMERA')
        projected[label]=[float(ndc.x),float(1-ndc.y)]
    result=C.landmark_error(marks,projected)
    result.update(camera=scene.camera.name,model=ob.name,source_landmarks=marks,
                  projected_model_landmarks=projected,
                  screenshot_verified=False,photorealism_verified=False)
    return result
def _view_inspect(scene):
    areas=[_info(area,space) for area,space in _areas()]
    polygons=sum(len(ob.data.polygons) for ob in scene.objects if ob.type=='MESH')
    try:
        import render_native_hud
        native_ui=render_native_hud.snapshot()
    except Exception:
        native_ui={'installed_in_blender_viewport':False}
    return {'viewports':areas,'total_mesh_polygons':polygons,
            'native_artist_ui':native_ui,
            'active_object':bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None,
            'render_quality_modified':False,'driver_jitter_measured':False,
            'viewport_clip_precision_is_not_texture_fidelity':True}
def _view_configure(p):
    _check(p,C.SCHEMAS['viewport.configure']['fields'])
    spaces=_areas()
    if not spaces:raise ValueError('NATIVE_VIEWPORT_NOT_OPEN')
    auto=False
    if 'radius' in p or 'distance' in p:
        if 'radius' not in p or 'distance' not in p:raise ValueError('NEED_RADIUS_AND_DISTANCE')
        plan=C.clip_plan(p['radius'],p['distance'])
        start,end=plan['clip_start'],plan['clip_end']
    else:
        start=C.finite(p.get('clip_start',spaces[0][1].clip_start),1e-7,1e8)
        end=C.finite(p.get('clip_end',spaces[0][1].clip_end),start,1e11)
        if end/start>100000:raise ValueError('DEPTH_PRECISION_RATIO_EXCESSIVE')
        plan={'viewport_only':True,'render_settings_changed':False,'geometry_decimated':False}
    if 'anti_alias' in p:
        requested=p['anti_alias']
        if not isinstance(requested,str) or requested not in ('OFF','FXAA','8','16','32'):
            raise ValueError('INVALID_ANTI_ALIAS_OPTION')
        system=bpy.context.preferences.system
        if not hasattr(system,'viewport_aa'):
            raise ValueError('VIEWPORT_ANTI_ALIAS_UNAVAILABLE')
        permitted={item.identifier for item in system.bl_rna.properties['viewport_aa'].enum_items}
        if requested not in permitted:raise ValueError('VIEWPORT_ANTI_ALIAS_UNSUPPORTED')
        system.viewport_aa=requested
        auto=True
    for area,space in spaces:
        space.clip_start=start;space.clip_end=end
    return dict(plan,viewports=[_info(a,s) for a,s in spaces],
                anti_alias_setting_changed=auto,
                final_render_samples_unchanged=True,
                requested_hardware_jitter_fix_verified=False)
def _view_focus(scene,p):
    _check(p,C.SCHEMAS['viewport.focus']['fields'],('object',))
    ob=_object(scene,p['object'])
    center,radius=_bounding(ob)
    margin=C.finite(p.get('margin',1.6),1,10)
    views=_areas()
    if not views:raise ValueError('NATIVE_VIEWPORT_NOT_OPEN')
    distance=max(radius*2.4*margin,.01)
    plan=C.clip_plan(radius,distance)
    for area,space in views:
        space.region_3d.view_location=center
        space.region_3d.view_distance=distance
        space.clip_start=plan['clip_start'];space.clip_end=plan['clip_end']
    return {'target':ob.name,'viewports_focused':len(views),'radius':radius,
            'view_distance':distance,'clip_start':plan['clip_start'],
            'clip_end':plan['clip_end'],'pointer_tap_simulated':False,
            'selection_changed':False,'render_quality_unchanged':True}
def _geometry(scene,p):
    _check(p,C.SCHEMAS['object.geometry']['fields'],('object',))
    ob=_object(scene,p['object'],'MESH')
    offset=p.get('offset',0);limit=p.get('limit',32)
    if type(offset) is not int or not 0<=offset<=100000000:raise ValueError('INVALID_OFFSET')
    if type(limit) is not int or not 1<=limit<=64:raise ValueError('INVALID_LIMIT')
    from itertools import islice
    vertices=[{'index':v.index,'co':list(v.co)} for v in
              islice(ob.data.vertices,offset,offset+limit)]
    return {'object':ob.name,'total_vertices':len(ob.data.vertices),
            'polygons':len(ob.data.polygons),'vertex_page':vertices,
            'materials':[m.name for m in ob.data.materials if m],
            'uv_layers':[layer.name for layer in ob.data.uv_layers],
            'next_offset':offset+limit if offset+limit<len(ob.data.vertices) else None,
            'visual_likeness_verified':False}
def _describe(p):
    _check(p,C.SCHEMAS['operator.describe']['fields'],('operator',))
    name=p['operator']
    if name not in _ALLOWED:raise ValueError('OPERATOR_NOT_AVAILABLE_THROUGH_NATIVE_BRIDGE')
    return {'operator':name,'parameters':list(_ALLOWED[name]['fields']),
            'arbitrary_python_allowed':False,'filesystem_access':False,
            'preconditions':['Blender object mode','named object exists'],
            'source':'Explicit Render Android operator registry, not every Blender operator',
            'always_successful':False}
def _operator(scene,p):
    _check(p,C.SCHEMAS['operator.execute']['fields'],('operator','parameters','expected_object'))
    name=p['operator']
    if name not in _ALLOWED:raise ValueError('OPERATOR_NOT_AVAILABLE_THROUGH_NATIVE_BRIDGE')
    arg=p['parameters'];allowed=_ALLOWED[name]['fields']
    _check(arg,allowed,('object',))
    ob=_object(scene,arg['object'],'MESH')
    if _name(p['expected_object'])!=ob.name:raise ValueError('OPERATOR_EXPECTED_OBJECT_MISMATCH')
    if bpy.context.object and bpy.context.object.mode!='OBJECT':
        raise ValueError('BLENDER_OBJECT_MODE_REQUIRED')
    previous=bpy.context.view_layer.objects.active
    selected=list(bpy.context.selected_objects)
    try:
        for obj in selected:obj.select_set(False)
        ob.select_set(True);bpy.context.view_layer.objects.active=ob
        if name=='object.shade_smooth':
            for poly in ob.data.polygons:poly.use_smooth=True
        elif name=='object.shade_flat':
            for poly in ob.data.polygons:poly.use_smooth=False
        elif name=='object.add_modifier':
            typ=arg.get('type')
            if typ not in _MODIFIERS:raise ValueError('MODIFIER_TYPE_NOT_ALLOWED')
            if len(ob.modifiers)>=32:raise ValueError('MODIFIER_LIMIT_REACHED')
            label=_name(arg.get('name','RenderModifier'))
            # Validate first: a rejected command must not leave a modifier behind.
            if typ=='SUBSURF':
                value=arg.get('levels',2)
                if type(value) is not int or not 0<=value<=5:raise ValueError('INVALID_SUBSURF_LEVEL')
            width=C.finite(arg.get('width',.02),0,100) if typ=='BEVEL' else None
            thickness=C.finite(arg.get('thickness',.02),-.5,.5) if typ=='SOLIDIFY' else None
            mod=ob.modifiers.new(label,typ)
            if typ=='SUBSURF':
                mod.levels=value;mod.render_levels=value
            if typ=='BEVEL':
                mod.width=width
                mod.segments=3
            if typ=='SOLIDIFY':mod.thickness=thickness
        elif name=='object.origin_to_geometry':
            with bpy.context.temp_override(object=ob,active_object=ob,selected_objects=[ob]):
                result=bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY',center='BOUNDS')
            if 'FINISHED' not in result:raise RuntimeError('ORIGIN_SET_NOT_EXECUTED')
        elif name=='object.transform_apply':
            flags={key:arg.get(key,key=='scale') for key in ('location','rotation','scale')}
            if any(type(value) is not bool for value in flags.values()):raise ValueError('INVALID_TRANSFORM_FLAGS')
            result=bpy.ops.object.transform_apply(**flags)
            if 'FINISHED' not in result:raise RuntimeError('TRANSFORM_NOT_APPLIED')
        elif name in ('object.modifier_apply','object.modifier_remove'):
            label=_name(arg.get('modifier'))
            modifier=ob.modifiers.get(label)
            if modifier is None:raise ValueError('MODIFIER_NOT_FOUND')
            if name.endswith('remove'):ob.modifiers.remove(modifier)
            elif 'FINISHED' not in bpy.ops.object.modifier_apply(modifier=label):
                raise RuntimeError('MODIFIER_NOT_APPLIED')
        elif name.startswith('mesh.'):
            import bmesh
            cuts=arg.get('cuts',1)
            if name=='mesh.subdivide' and (type(cuts) is not int or not 1<=cuts<=8):raise ValueError('INVALID_SUBDIVISION_CUTS')
            distance=C.finite(arg.get('distance',.0001),.0000001,1) if name.endswith('distance') else None
            if name=='mesh.subdivide' and len(ob.data.edges)*(cuts+1)**2>2_000_000:
                raise ValueError('SUBDIVISION_MEMORY_BUDGET_EXCEEDED')
            mesh=bmesh.new()
            try:
                mesh.from_mesh(ob.data)
                if name=='mesh.subdivide':bmesh.ops.subdivide_edges(mesh,edges=list(mesh.edges),cuts=cuts,use_grid_fill=True)
                elif name=='mesh.recalculate_normals':bmesh.ops.recalc_face_normals(mesh,faces=list(mesh.faces))
                elif name=='mesh.merge_by_distance':bmesh.ops.remove_doubles(mesh,verts=list(mesh.verts),dist=distance)
                if ob.data.users>1:ob.data=ob.data.copy()
                mesh.to_mesh(ob.data);ob.data.update()
            finally:mesh.free()
        elif name=='uv.smart_project':
            angle=C.finite(arg.get('angle_degrees',66),1,89)
            margin=C.finite(arg.get('island_margin',.02),0,.5)
            try:
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.select_all(action='SELECT')
                result=bpy.ops.uv.smart_project(angle_limit=math.radians(angle),island_margin=margin)
                if 'FINISHED' not in result:raise RuntimeError('UV_PROJECT_NOT_EXECUTED')
            finally:
                if ob.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        return {'object':ob.name,'operator':name,'executed_on_native_blender':True,
                'performed_visible_pointer_click':False,
                'vertices':len(ob.data.vertices),'polygons':len(ob.data.polygons),
                'modifiers':[m.name for m in ob.modifiers]}
    finally:
        if ob.name in bpy.data.objects:ob.select_set(False)
        for prev in selected:
            if prev.name in bpy.data.objects:prev.select_set(True)
        if previous and previous.name in bpy.data.objects:
            bpy.context.view_layer.objects.active=previous

def execute(operation,p,root,scene):
    if operation not in C.SCHEMAS:raise ValueError('STUDIO_OPERATION_UNAVAILABLE')
    if scene is None:raise ValueError('NO_ACTIVE_SCENE')
    if operation=='reference.bind':return _board(scene,root,p)
    if operation=='reference.landmarks':return _compare(scene,p)
    if operation=='viewport.inspect':return _view_inspect(scene)
    if operation=='viewport.configure':return _view_configure(p)
    if operation=='viewport.focus':return _view_focus(scene,p)
    if operation=='object.geometry':return _geometry(scene,p)
    if operation=='operator.describe':return _describe(p)
    if operation=='operator.execute':return _operator(scene,p)
    raise ValueError('ANDROID_OWNED_STUDIO_OPERATION')
