# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed native Blender production operations. No eval, shell or remote renderer."""
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import uuid
import time
import bpy
from mathutils import Vector

_path = Path(__file__).with_name('render_production_contract.py')
_spec = importlib.util.spec_from_file_location('render_production_contract', _path)
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

def _phase2():
    # Blender runtime packaging/registration belongs to P10. In installed
    # Blender the 'omega' package lives on the actual startup search path.
    # Headless bpy tests sometimes load this file with spec_from_file_location
    # (rather than as a package), so use only the adjacent pinned module as
    # a safe, deterministic fallback; never import user-requested code.
    try:
        from omega import phase02_render
        return phase02_render
    except ModuleNotFoundError as error:
        if error.name not in ('omega', 'omega.phase02_render'):
            raise
    adjacent = Path(__file__).resolve().parent / 'omega' / 'phase02_render.py'
    if not adjacent.is_file():
        raise ValueError('RENDER_PHASE02_MODULE_NOT_INSTALLED')
    spec = importlib.util.spec_from_file_location('render_omega_phase02_local', adjacent)
    if spec is None or spec.loader is None:
        raise ValueError('RENDER_PHASE02_MODULE_NOT_INSTALLED')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _write(path, value):
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf8') as out:
        json.dump(value,out,sort_keys=True,allow_nan=False);out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)
    # Directory durability after the atomic rename is filesystem-dependent.
    try:
        fd=os.open(str(path.parent),os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
        try:os.fsync(fd)
        finally:os.close(fd)
    except OSError:pass

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
    if asset is not None and (not asset.is_file() or asset.suffix.lower() not in ('.png','.jpg','.jpeg','.webp')):raise ValueError('REFERENCE_IMAGE_UNAVAILABLE')
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
    # Omitting a setting means keep the artist's scene setting. A minimal MCP
    # request must never silently replace its engine, resolution or samples.
    import render_execution_settings
    plan, profile, quality = render_execution_settings.profile_plan(scene,p)
    spec=C.render_spec(plan)
    spec['sample_control']=render_execution_settings._samples(scene,spec['engine'])[1]
    spec['profile']=profile
    spec['quality_overrides']=quality
    image_settings=scene.render.image_settings
    if image_settings.file_format in ('OPEN_EXR','OPEN_EXR_MULTILAYER','HDR') or image_settings.color_depth=='32':
        raise ValueError('HDR_OUTPUT_REQUIRES_NATIVE_BLENDER_RENDER_MENU')
    spec['image_color_depth']=image_settings.color_depth
    spec['image_color_mode']=image_settings.color_mode
    unpacked=[image for image in bpy.data.images if image.source=='FILE' and not image.packed_file]
    if unpacked:raise ValueError('PACK_EXTERNAL_IMAGES_BEFORE_CHECKPOINT')
    if scene.camera is None:raise ValueError('CAMERA_REQUIRED')
    ident=uuid.uuid4().hex;folder=_job(root,ident);folder.mkdir(mode=0o700)
    checkpoint=folder/'snapshot.blend'
    # Snapshot all referenced native Blender data; source project path is unchanged.
    if 'FINISHED' not in bpy.ops.wm.save_as_mainfile(filepath=str(checkpoint),copy=True,compress=False,check_existing=False):raise RuntimeError('CHECKPOINT_FAILED')
    _phase2().sync_file(checkpoint)
    _phase2().sync_directory(folder)
    receipt=C.file_receipt(checkpoint)
    # Fractional frame time belongs to the real scene, not a guessed Android
    # integer fps. Existing typed render.plan payload stays backward compatible.
    spec['fps_base']=float(quality.get('fps_base',scene.render.fps_base))
    manifest={'version':1,'job_id':ident,'source_scene':scene.name,'spec':spec,'snapshot':receipt,
              'fingerprint':C.fingerprint({'spec':spec,'snapshot':receipt}),'state':'ready',
              'frames':{},'next_frame':spec['start'],'quality_reduced':False}
    _write(folder/'manifest.json',manifest)
    return _status(manifest)

def _status(manifest):
    return {'job_id':manifest['job_id'],'state':manifest['state'],'completed_frames':len(manifest['frames']),
            'total_frames':manifest['spec']['frame_count'],'next_frame':manifest['next_frame'],
            'spec':manifest['spec'],'fingerprint':manifest['fingerprint'],'quality_reduced':False,
            'video_created':manifest['state']=='encoded','native_execution_verified':True,
            'timing':manifest.get('timing',{}),
            'render_settings_compatibility':manifest.get('render_settings_compatibility',{})}

def _render_exact(scene, frame):
    # A render operator can inherit the active window frame despite scene=.
    window=bpy.context.window
    original=window.scene if window else None
    try:
        if window:window.scene=scene
        scene.frame_set(frame)
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            result=bpy.ops.render.render(write_still=True,scene=scene.name)
        if scene.frame_current!=frame:
            raise RuntimeError('RENDER_FRAME_CONTEXT_MISMATCH')
        return result
    finally:
        if window and original is not None:window.scene=original


def _release_snapshot(scene):
    """Release only unreferenced data belonging to a finished cached snapshot."""
    if not scene.get('production_frozen_job') or scene==bpy.context.scene:
        return
    if any(window.scene==scene for window in bpy.context.window_manager.windows):
        return
    objects=[ob for ob in scene.objects if len(ob.users_scene)==1]
    collections=list(scene.collection.children_recursive)
    data={ob.data for ob in objects if ob.data is not None}
    materials={m for item in data for m in getattr(item,'materials',()) if m is not None}
    images={n.image for m in materials if m.use_nodes for n in m.node_tree.nodes
            if hasattr(n,'image') and n.image is not None}
    bpy.data.scenes.remove(scene)
    # Parent collections precede their children; preserve anything still linked
    # elsewhere and never run a global orphan purge on an artist's project.
    for collection in collections:
        if collection.users==0 and not collection.use_fake_user:bpy.data.collections.remove(collection)
    for ob in objects:
        if ob.users==0 and not ob.use_fake_user:bpy.data.objects.remove(ob)
    for item in data:
        if item.users==0 and not item.use_fake_user:
            if isinstance(item,bpy.types.Mesh):bpy.data.meshes.remove(item)
            elif isinstance(item,bpy.types.Curve):bpy.data.curves.remove(item)
            elif isinstance(item,bpy.types.Armature):bpy.data.armatures.remove(item)
    for material in materials:
        if material.users==0 and not material.use_fake_user:bpy.data.materials.remove(material)
    for image in images:
        if image.users==0 and not image.use_fake_user:bpy.data.images.remove(image)

def _step(root,p):
    C.fields(p,('job_id',),('job_id',));folder=_job(root,p['job_id']);path=folder/'manifest.json'
    manifest=json.loads(path.read_text());spec=manifest['spec']
    if manifest['fingerprint']!=C.fingerprint({'spec':spec,'snapshot':manifest['snapshot']}):raise ValueError('RENDER_MANIFEST_CONFLICT')
    # Phase 02's reconciliation verifies the SHA-bound snapshot once per
    # native session rather than twice for every potentially huge frame.
    # A stale next_frame after power loss or an earlier corrupt PNG must not
    # skip a gap. Two-phase sidecars can adopt valid frames committed between
    # the PNG rename and the manifest rename without re-rendering them.
    manifest, verification = _phase2().reconcile_manifest(folder,manifest,persist=True,cached=True)
    frame=manifest['next_frame']
    if frame>spec['end']:return _status(manifest)
    scene=next((s for s in bpy.data.scenes if s.get('production_frozen_job')==manifest['job_id']),None)
    if scene is None:
        for prior in list(bpy.data.scenes):
            if prior.get('production_frozen_job') and prior.get('production_frozen_job')!=manifest['job_id']:
                _release_snapshot(prior)
        with bpy.data.libraries.load(str(folder/'snapshot.blend'),link=False) as (src,dst):
            if manifest['source_scene'] not in src.scenes:raise ValueError('CHECKPOINT_SCENE_MISSING')
            dst.scenes=[manifest['source_scene']]
        scene=dst.scenes[0]
        import render_execution_settings
        render_execution_settings.configure(scene,render_execution_settings.snapshot_overrides(spec))
        scene['production_frozen_job']=manifest['job_id']
    render=scene.render
    engine=spec['engine']
    try:
        if render.engine!=engine:render.engine=engine
    except (TypeError,ValueError):
        # Never silently replace the user's renderer with a different engine.
        # A different shading backend can change pixels even with identical
        # samples, so prefer an explicit, recoverable unsupported-engine error.
        raise ValueError('REQUESTED_RENDER_ENGINE_UNAVAILABLE')
    for key,value in (('resolution_x',spec['width']),('resolution_y',spec['height']),
                      ('resolution_percentage',100),('fps',spec['fps']),('fps_base',spec.get('fps_base',render.fps_base))):
        if getattr(render,key)!=value:setattr(render,key,value)
        if abs(getattr(render,key)-value)>1e-5:raise ValueError('NATIVE_RENDER_SETTING_WAS_CLAMPED')
    import render_execution_settings
    sample_compatibility=render_execution_settings.apply_job_samples(scene,spec)
    if sample_compatibility.get('legacy_workbench_snapshot_antialiasing_preserved'):
        manifest['render_settings_compatibility']=sample_compatibility
    if render.image_settings.file_format!='PNG':render.image_settings.file_format='PNG'
    for key, value in (('color_depth',spec.get('image_color_depth',render.image_settings.color_depth)),
                       ('color_mode',spec.get('image_color_mode',render.image_settings.color_mode))):
        if getattr(render.image_settings,key)!=value:setattr(render.image_settings,key,value)
        if getattr(render.image_settings,key)!=value:raise ValueError('NATIVE_OUTPUT_PRECISION_UNAVAILABLE')
    tmp=folder/('frame_%06d.partial.png'%frame);final=folder/('frame_%06d.png'%frame)
    render.filepath=str(tmp)
    manifest['state']='rendering';_write(path,manifest)
    try:
        frame_started=time.monotonic()
        result=_render_exact(scene,frame)
        if 'FINISHED' not in result or not tmp.is_file():
            raise RuntimeError('FRAME_RENDER_FAILED')
        # CRC and expected dimensions are checked BEFORE making the PNG
        # immutable. Sidecar -> fsynced rename -> manifest prevents false
        # completion after a crash between filesystem operations.
        duration=max(1,round((time.monotonic()-frame_started)*1000))
        timing=manifest.setdefault('timing',{})
        timing['rendered_frames']=timing.get('rendered_frames',0)+1
        timing['render_active_ms']=timing.get('render_active_ms',0)+duration
        timing['last_frame_ms']=duration
        timing['estimated_frame_ms']=round(.25*duration+.75*timing.get('estimated_frame_ms',duration))
        timing['estimate_scope']='remaining native frames; excludes encoding, pauses and exports'
        _phase2().commit_png(folder,manifest,frame,tmp)
    except Exception:
        manifest['state']='paused_error';_write(path,manifest);raise
    if manifest['next_frame']>spec['end']:_release_snapshot(scene)
    return _status(manifest)

def execute(args, spool, command_id):
    operation,p=C.validate_envelope(args);root=_root(spool)
    scene=bpy.context.scene
    if scene is None:raise RuntimeError('NO_ACTIVE_SCENE')
    if operation in ('file.importers','file.inspect','file.import'):
        import render_file_ops
        return render_file_ops.execute(operation,scene,root,p)
    import render_artist_ops
    if operation in render_artist_ops.SCHEMAS:
        return render_artist_ops.execute(operation,scene,root,p)
    if operation in ('operator.execute','asset.import','project.restore','rig.bind','mesh.edit',
                     'animation.clip.create','reference.workspace.open'):
        render_artist_ops.checkpoint(scene,root,operation)

    if operation in ('asset.search','asset.details','asset.preview','asset.download','asset.download.status','asset.download.pause','asset.import'):
        import render_asset_library
        return render_asset_library.execute(operation,scene,root,p)
    if operation in ('render.profile.inspect','render.profile.configure','render.quality.inspect','render.quality.configure',
                     'render.performance.inspect','render.performance.configure'):
        import render_execution_settings
        return render_execution_settings.execute(operation,scene,p)
    if operation in ('project.list','project.restore','mesh.edit','curve.create','shape.create','shape.keys','rig.create','rig.bind','rig.keys'):
        import render_production_detail
        return render_production_detail.execute(operation,p,root,scene,C)
    if operation in ('reference.workspace.open','reference.workspace.inspect',
                     'reference.compare.multiview','animation.clip.create',
                     'animation.clip.inspect','animation.motion.audit'):
        import render_reference_motion
        return render_reference_motion.execute(operation,p,root,scene)
    if operation in ('reference.bind','reference.landmarks','viewport.inspect',
                     'viewport.configure','viewport.focus','object.geometry',
                     'operator.describe','operator.execute'):
        import render_studio_ops
        return render_studio_ops.execute(operation,p,root,scene)
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
        C.fields(p,('job_id',),('job_id',))
        folder=_job(root,p['job_id'])
        manifest=json.loads((folder/'manifest.json').read_text())
        verified,details=_phase2().reconcile_manifest(folder,manifest,persist=False)
        return dict(_status(verified),verification=details)
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
        import render_session_tools
        receipt=render_session_tools.save_copy_atomic(file,compress=True)
        return dict(receipt,category='Projects',scene=scene.name,source_unchanged=True)
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
        if not asset.is_file() or asset.suffix.lower() not in ('.png','.jpg','.jpeg','.webp'):raise ValueError('REFERENCE_IMAGE_UNAVAILABLE')
        name=_new_name(p['name']);location=C.triple(p.get('location',[0,0,0]));size=C.number(p.get('size',4),0.001,10000)
        image=bpy.data.images.load(str(asset),check_existing=True);image.pack();ob=bpy.data.objects.new(name,None);ob.empty_display_type='IMAGE';ob.data=image;ob.empty_display_size=size;ob.location=location;scene.collection.objects.link(ob)
        return {'object':name,'image':image.name,'packed':True,'is_3d_reconstruction':False}
    if operation=='render.plan':return _plan_render(scene,p,root)
    raise ValueError('OPERATION_REQUIRES_ANDROID_DISPATCH')
