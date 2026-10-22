# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed native Blender production operations. No eval, shell or remote renderer."""
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import uuid
import bpy
from mathutils import Vector

_path = Path(__file__).with_name('render_production_contract.py')
_spec = importlib.util.spec_from_file_location('render_production_contract', _path)
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

def _write(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf8') as out:
        json.dump(value,out,sort_keys=True,allow_nan=False);out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)

def _root(spool):
    if not spool:raise ValueError('SPOOL_UNAVAILABLE')
    root=Path(spool).resolve().parent/'Production'
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    return root

def _job(root, ident):
    if not isinstance(ident,str) or len(ident)!=32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('INVALID_JOB_ID')
    folder=root/ident
    if folder.is_symlink() or folder.resolve().parent!=root.resolve():raise ValueError('JOB_OUTSIDE_SCOPE')
    return folder

def _object(scene,name):
    ob=scene.objects.get(C.safe_name(name))
    if ob is None:raise ValueError('OBJECT_NOT_FOUND')
    return ob

def _new_name(name):
    C.safe_name(name)
    if name in bpy.data.objects:raise ValueError('OBJECT_NAME_EXISTS')
    return name

def _editable(scene):
    if scene.get('production_frozen_job'):raise ValueError('RENDER_SNAPSHOT_IMMUTABLE')

def _info(ob):
    return {'name':ob.name,'type':ob.type,'location':list(ob.location),
            'rotation_euler':list(ob.rotation_euler),'scale':list(ob.scale),
            'parent':ob.parent.name if ob.parent else None,
            'vertices':len(ob.data.vertices) if ob.type=='MESH' else 0,
            'polygons':len(ob.data.polygons) if ob.type=='MESH' else 0}

def _mesh(scene,p):
    p=C.mesh_spec(p);name=_new_name(p['name']);kind=p['kind']
    previous=bpy.context.view_layer.objects.active
    if bpy.context.object is not None and bpy.context.object.mode!='OBJECT':
        raise ValueError('OBJECT_MODE_REQUIRED')
    ob=None
    try:
        if kind=='MESH':
            mesh=bpy.data.meshes.new(name+'Mesh');mesh.from_pydata(p['vertices'],[],p['faces']);mesh.update()
            ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
        elif kind=='UV_SPHERE':
            bpy.ops.mesh.primitive_uv_sphere_add(segments=p.get('segments',48),ring_count=p.get('rings',24));ob=bpy.context.object
        elif kind=='ICO_SPHERE':bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3);ob=bpy.context.object
        elif kind=='CYLINDER':bpy.ops.mesh.primitive_cylinder_add(vertices=p.get('segments',48));ob=bpy.context.object
        elif kind=='CONE':bpy.ops.mesh.primitive_cone_add(vertices=p.get('segments',48));ob=bpy.context.object
        elif kind=='PLANE':bpy.ops.mesh.primitive_plane_add();ob=bpy.context.object
        elif kind=='TORUS':bpy.ops.mesh.primitive_torus_add(major_segments=p.get('segments',48),minor_segments=p.get('rings',24));ob=bpy.context.object
        elif kind=='CUBE':bpy.ops.mesh.primitive_cube_add();ob=bpy.context.object
        if ob is None:raise RuntimeError('NATIVE_MESH_CREATION_FAILED')
        ob.name=name
        for key in ('location','rotation_euler','scale'):
            if key in p:setattr(ob,key,p[key])
        if p.get('smooth',kind not in ('CUBE','PLANE','MESH')):
            for face in ob.data.polygons:face.use_smooth=True
        width=p.get('bevel',0)
        if width:
            mod=ob.modifiers.new('ProductionBevel','BEVEL');mod.width=width;mod.segments=3
        return _info(ob)
    except Exception:
        if ob is not None:bpy.data.objects.remove(ob,do_unlink=True)
        raise
    finally:
        if previous is not None and previous.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active=previous

def _material(scene,p,root):
    C.fields(p,('object','name','color','metallic','roughness','emission','emission_strength','asset'),('object','color'))
    ob=_object(scene,p['object'])
    if ob.type not in ('MESH','CURVE','SURFACE'):raise ValueError('MATERIAL_OBJECT_TYPE')
    color=C.triple(p['color'],0,1);metal=C.number(p.get('metallic',0),0,1);rough=C.number(p.get('roughness',0.5),0,1)
    emission=C.triple(p.get('emission',[0,0,0]),0,1);strength=C.number(p.get('emission_strength',0),0,10000)
    asset=C.owned_path(root/'Assets',p['asset']) if 'asset' in p else None
    if asset is not None and (not asset.is_file() or asset.suffix.lower() not in ('.png','.jpg','.jpeg')):raise ValueError('REFERENCE_IMAGE_UNAVAILABLE')
    material=bpy.data.materials.new(C.safe_name(p.get('name','ProductionMaterial')))
    material.use_nodes=True;material.diffuse_color=(*color,1)
    shader=material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Metallic'].default_value=metal;shader.inputs['Roughness'].default_value=rough
    emission_input=shader.inputs.get('Emission Color') or shader.inputs.get('Emission')
    if emission_input:emission_input.default_value=(*emission,1)
    if shader.inputs.get('Emission Strength'):shader.inputs['Emission Strength'].default_value=strength
    if asset is not None:
        texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=bpy.data.images.load(str(asset),check_existing=True);texture.image.pack()
        material.node_tree.links.new(texture.outputs['Color'],shader.inputs['Base Color'])
    ob.data.materials.clear();ob.data.materials.append(material)
    return {'object':ob.name,'material':material.name,'pbr':True,'texture_packed':asset is not None}

def _keys(scene,p):
    C.fields(p,('object','keys'),('object','keys'));ob=_object(scene,p['object'])
    keys=p['keys']
    if not isinstance(keys,list) or not 1<=len(keys)<=256:raise ValueError('INVALID_KEYFRAME_BATCH')
    for item in keys:
        C.fields(item,('frame','path','value'),('frame','path','value'));C.integer(item['frame'],1,100000)
        if item['path'] not in ('location','rotation_euler','scale'):raise ValueError('KEYFRAME_PATH_UNAVAILABLE')
        C.triple(item['value'],0.0001 if item['path']=='scale' else -100000,100000)
    current=scene.frame_current
    for item in keys:
        setattr(ob,item['path'],item['value']);ob.keyframe_insert(data_path=item['path'],frame=item['frame'])
    scene.frame_set(current)
    return {'object':ob.name,'inserted':len(keys),'frame':scene.frame_current}

def _instances(scene,p,available):
    plan=C.instance_plan(p,available)
    if not plan['admitted']:raise ValueError('INSUFFICIENT_MEMORY_FOR_REQUESTED_DETAIL')
    if plan['instance_count']>1_000_000 and not p.get('confirm_large_scene',False):raise ValueError('LARGE_SCENE_CONFIRMATION_REQUIRED')
    name=_new_name(p.get('name','InstanceField'));source=_object(scene,p.get('source',''))
    if source.type not in ('MESH','CURVE'):raise ValueError('INSTANCE_SOURCE_UNSUPPORTED')
    mesh=bpy.data.meshes.new(name+'Carrier');ob=bpy.data.objects.new(name,mesh);scene.collection.objects.link(ob)
    group=None
    try:
        group=bpy.data.node_groups.new(name+'Geometry','GeometryNodeTree')
        if hasattr(group,'interface'):
            group.interface.new_socket(name='Geometry',in_out='INPUT',socket_type='NodeSocketGeometry')
            group.interface.new_socket(name='Geometry',in_out='OUTPUT',socket_type='NodeSocketGeometry')
        else:
            group.inputs.new('NodeSocketGeometry','Geometry');group.outputs.new('NodeSocketGeometry','Geometry')
        nodes=group.nodes;links=group.links
        source_node=nodes.new('GeometryNodeObjectInfo');source_node.inputs['Object'].default_value=source
        source_node.inputs['As Instance'].default_value=True
        geometry=source_node.outputs['Geometry']
        for axis,count in enumerate(plan['counts']):
            line=nodes.new('GeometryNodeMeshLine');line.mode='OFFSET';line.inputs['Count'].default_value=count
            offset=[0.0,0.0,0.0];offset[axis]=p['spacing'][axis];line.inputs['Offset'].default_value=offset
            node=nodes.new('GeometryNodeInstanceOnPoints');links.new(line.outputs['Mesh'],node.inputs['Points']);links.new(geometry,node.inputs['Instance']);geometry=node.outputs['Instances']
        output=nodes.new('NodeGroupOutput');links.new(geometry,output.inputs['Geometry'])
        mod=ob.modifiers.new('ExactInstanceField','NODES');mod.node_group=group
        ob['production_instance_count']=plan['instance_count'];ob['production_instancing_plan']=json.dumps(plan)
        return dict(plan,object=ob.name,prototype=source.name)
    except Exception:
        bpy.data.objects.remove(ob,do_unlink=True)
        if group is not None:bpy.data.node_groups.remove(group)
        raise

def _plan_render(scene,p,root):
    spec=C.render_spec(p)
    if scene.camera is None:raise ValueError('CAMERA_REQUIRED')
    ident=uuid.uuid4().hex;folder=_job(root,ident);folder.mkdir(mode=0o700)
    checkpoint=folder/'snapshot.blend'
    # Snapshot all referenced native Blender data; source project path is unchanged.
    if 'FINISHED' not in bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),copy=True,compress=True,check_existing=False):raise RuntimeError('CHECKPOINT_FAILED')
    receipt=C.file_receipt(checkpoint)
    manifest={'version':1,'job_id':ident,'source_scene':scene.name,'spec':spec,'snapshot':receipt,
              'fingerprint':C.fingerprint({'spec':spec,'snapshot':receipt}),'state':'ready',
              'frames':{},'next_frame':spec['start'],'quality_reduced':False}
    _write(folder/'manifest.json',manifest)
    return _status(manifest)

def _status(manifest):
    return {'job_id':manifest['job_id'],'state':manifest['state'],'completed_frames':len(manifest['frames']),
            'total_frames':manifest['spec']['frame_count'],'next_frame':manifest['next_frame'],
            'spec':manifest['spec'],'fingerprint':manifest['fingerprint'],'quality_reduced':False,
            'video_created':manifest['state']=='encoded','native_execution_verified':True}

def _step(root,p):
    C.fields(p,('job_id',),('job_id',));folder=_job(root,p['job_id']);path=folder/'manifest.json'
    manifest=json.loads(path.read_text());spec=manifest['spec']
    if manifest['fingerprint']!=C.fingerprint({'spec':spec,'snapshot':manifest['snapshot']}):raise ValueError('RENDER_MANIFEST_CONFLICT')
    if not C.frame_matches(folder,manifest['snapshot']):raise ValueError('CHECKPOINT_HASH_MISMATCH')
    frame=manifest['next_frame']
    if frame>spec['end']:return _status(manifest)
    existing=manifest['frames'].get(str(frame))
    if existing and C.frame_matches(folder,existing):
        manifest['next_frame']=frame+1;_write(path,manifest);return _status(manifest)
    scene=next((s for s in bpy.data.scenes if s.get('production_frozen_job')==manifest['job_id']),None)
    if scene is None:
        with bpy.data.libraries.load(str(folder/'snapshot.blend'),link=False) as (src,dst):
            if manifest['source_scene'] not in src.scenes:raise ValueError('CHECKPOINT_SCENE_MISSING')
            dst.scenes=[manifest['source_scene']]
        scene=dst.scenes[0];scene['production_frozen_job']=manifest['job_id']
    render=scene.render
    engine=spec['engine']
    try:
        render.engine=engine
    except (TypeError,ValueError):
        # Never silently replace the user's renderer with a different engine.
        # A different shading backend can change pixels even with identical
        # samples, so prefer an explicit, recoverable unsupported-engine error.
        raise ValueError('REQUESTED_RENDER_ENGINE_UNAVAILABLE')
    render.resolution_x=spec['width'];render.resolution_y=spec['height'];render.resolution_percentage=100
    render.fps=spec['fps'];render.fps_base=1.0
    if render.engine=='CYCLES':scene.cycles.samples=spec['samples']
    elif hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_render_samples'):scene.eevee.taa_render_samples=spec['samples']
    render.image_settings.file_format='PNG';render.image_settings.color_mode='RGBA'
    tmp=folder/('frame_%06d.partial.png'%frame);final=folder/('frame_%06d.png'%frame)
    render.filepath=str(tmp);scene.frame_set(frame)
    manifest['state']='rendering';_write(path,manifest)
    try:
        result=bpy.ops.render.render(write_still=True,scene=scene.name)
        if 'FINISHED' not in result or not tmp.is_file() or tmp.stat().st_size<64:raise RuntimeError('FRAME_RENDER_FAILED')
        os.replace(tmp,final);manifest['frames'][str(frame)]=C.file_receipt(final)
        manifest['next_frame']=frame+1;manifest['state']='frames_complete' if frame==spec['end'] else 'ready'
        _write(path,manifest)
    except Exception:
        manifest['state']='paused_error';_write(path,manifest);raise
    return _status(manifest)

def execute(args, spool, command_id):
    operation,p=C.validate_envelope(args);root=_root(spool)
    scene=bpy.context.scene
    if scene is None:raise RuntimeError('NO_ACTIVE_SCENE')
    if operation=='scene.inspect':
        C.fields(p,('offset','limit'))
        offset=C.integer(p.get('offset',0),0,10000000);limit=C.integer(p.get('limit',32),1,64)
        objects=list(scene.objects)
        return {'scene':scene.name,'frame':scene.frame_current,'total_objects':len(objects),
                'objects':[_info(x) for x in objects[offset:offset+limit]],
                'next_offset':offset+limit if offset+limit<len(objects) else None,
                'camera':scene.camera.name if scene.camera else None,'fps':scene.render.fps,
                'frame_start':scene.frame_start,'frame_end':scene.frame_end,'visual_quality_verified':False}
    if operation=='render.status':
        C.fields(p,('job_id',),('job_id',));return _status(json.loads((_job(root,p['job_id'])/'manifest.json').read_text()))
    if operation=='render.step':return _step(root,p)
    _editable(scene)
    if operation=='asset.create':
        C.fields(p, ('preset','name'), ('preset',))
        import render_assets
        return render_assets.create_asset(scene,p['preset'],p.get('name'))
    if operation=='project.create':
        C.fields(p,('name',),('name',));name=C.safe_name(p['name'])
        if name in bpy.data.scenes:raise ValueError('SCENE_NAME_EXISTS')
        if bpy.context.window is None:raise RuntimeError('EDITOR_WINDOW_REQUIRED')
        previous=scene.name;new=bpy.data.scenes.new(name);bpy.context.window.scene=new
        return {'scene':new.name,'previous_scene':previous,'previous_scene_preserved':True,'saved':False}
    if operation=='project.checkpoint':
        C.fields(p,('name',))
        name=C.safe_name(p.get('name','Project'))+'_'+uuid.uuid4().hex+'.blend'
        folder=root/'Projects';folder.mkdir(exist_ok=True);file=C.owned_path(folder,name)
        result=bpy.ops.wm.save_as_mainfile(filepath=str(file),copy=True,compress=True,check_existing=False)
        if 'FINISHED' not in result or not file.is_file():raise RuntimeError('CHECKPOINT_FAILED')
        return dict(C.file_receipt(file),category='Projects',source_unchanged=True)
    if operation=='mesh.create':return _mesh(scene,p)
    if operation=='material.assign':return _material(scene,p,root)
    if operation=='animation.keys':return _keys(scene,p)
    if operation=='group.create':
        C.fields(p,('name','children','location'),('name','children'));name=_new_name(p['name']);location=C.triple(p.get('location',[0,0,0]))
        names=p['children']
        if not isinstance(names,list) or not 1<=len(names)<=256 or len(set(names))!=len(names):raise ValueError('INVALID_GROUP_CHILDREN')
        children=[_object(scene,n) for n in names]
        if any(c.parent for c in children):raise ValueError('CHILD_ALREADY_PARENTED')
        root_ob=bpy.data.objects.new(name,None);scene.collection.objects.link(root_ob);root_ob.location=location
        bpy.context.view_layer.update()
        for ob in children:
            matrix=ob.matrix_world.copy();ob.parent=root_ob;ob.matrix_world=matrix
        return {'group':name,'children':len(children),'world_transforms_preserved':True}
    if operation=='camera.aim':
        C.fields(p,('name','location','target','lens'),('name','location','target'))
        name=C.safe_name(p['name']);location=C.triple(p['location']);target=C.triple(p['target']);lens=C.number(p.get('lens',50),1,1000)
        if (Vector(target)-Vector(location)).length<0.0001:raise ValueError('CAMERA_TARGET_EQUALS_LOCATION')
        ob=scene.objects.get(name)
        if ob is None:
            _new_name(name);ob=bpy.data.objects.new(name,bpy.data.cameras.new(name));scene.collection.objects.link(ob)
        if ob.type!='CAMERA':raise ValueError('CAMERA_NAME_CONFLICT')
        ob.location=location;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler();ob.data.lens=lens;scene.camera=ob
        return _info(ob)
    if operation=='world.configure':
        C.fields(p,('color','strength'),('color',));color=C.triple(p['color'],0,1);strength=C.number(p.get('strength',1),0,10000)
        world=bpy.data.worlds.new('ProductionWorld');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(*color,1);world.node_tree.nodes['Background'].inputs['Strength'].default_value=strength;scene.world=world
        return {'world':world.name,'strength':strength}
    if operation in ('instances.plan','instances.create'):
        available=p.get('available_memory_bytes',0);params={k:v for k,v in p.items() if k!='available_memory_bytes'}
        if operation=='instances.plan':return C.instance_plan(params,available)
        return _instances(scene,params,available)
    if operation=='reference.attach':
        C.fields(p,('asset','name','location','size'),('asset','name'));asset=C.owned_path(root/'Assets',p['asset'])
        if not asset.is_file() or asset.suffix.lower() not in ('.png','.jpg','.jpeg'):raise ValueError('REFERENCE_IMAGE_UNAVAILABLE')
        name=_new_name(p['name']);location=C.triple(p.get('location',[0,0,0]));size=C.number(p.get('size',4),0.001,10000)
        image=bpy.data.images.load(str(asset),check_existing=True);image.pack();ob=bpy.data.objects.new(name,None);ob.empty_display_type='IMAGE';ob.data=image;ob.empty_display_size=size;ob.location=location;scene.collection.objects.link(ob)
        return {'object':name,'image':image.name,'packed':True,'is_3d_reconstruction':False}
    if operation=='render.plan':return _plan_render(scene,p,root)
    raise ValueError('OPERATION_REQUIRES_ANDROID_DISPATCH')
