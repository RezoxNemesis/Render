# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed detail operations; deliberately not an arbitrary Python operator bridge."""
import bpy
from mathutils import Vector

OPERATIONS=frozenset(('project.list','project.restore','mesh.edit','curve.create','shape.create','shape.keys','rig.create','rig.bind','rig.keys'))

def _object(scene,name,C,kind=None):
    ob=scene.objects.get(C.safe_name(name))
    if ob is None or kind is not None and ob.type!=kind:raise ValueError('DETAIL_OBJECT_NOT_FOUND')
    return ob

def _patches(p,count,C):
    if not isinstance(p,list) or not 1<=len(p)<=2048:raise ValueError('INVALID_VERTEX_PATCHES')
    seen=set()
    for item in p:
        C.fields(item,('index','coordinate'),('index','coordinate'))
        index=C.integer(item['index'],0,count-1)
        if index in seen:raise ValueError('DUPLICATE_VERTEX_PATCH')
        seen.add(index);C.triple(item['coordinate'])
    return p

def execute(operation,p,root,scene,C):
    if operation=='project.list':
        C.fields(p,('offset','limit'));offset=C.integer(p.get('offset',0),0,100000);limit=C.integer(p.get('limit',32),1,64)
        folder=root/'Projects';files=sorted(folder.glob('*.blend'),key=lambda f:f.name) if folder.is_dir() else []
        files=[f for f in files if not f.is_symlink() and f.is_file()]
        return {'projects':[C.file_receipt(f) for f in files[offset:offset+limit]],'total':len(files),
                'next_offset':offset+limit if offset+limit<len(files) else None}
    if scene.get('production_frozen_job'):raise ValueError('RENDER_SNAPSHOT_IMMUTABLE')
    if operation=='project.restore':
        C.fields(p,('filename','sha256','scene'),('filename','sha256','scene'))
        path=C.owned_path(root/'Projects',p['filename'])
        if not path.is_file() or path.suffix!='.blend' or C.file_receipt(path)['sha256']!=p['sha256']:raise ValueError('PROJECT_CHECKPOINT_HASH_MISMATCH')
        if bpy.context.window is None:raise RuntimeError('EDITOR_WINDOW_REQUIRED')
        previous=scene.name
        with bpy.data.libraries.load(str(path),link=False) as (source,target):
            if p['scene'] not in source.scenes:raise ValueError('CHECKPOINT_SCENE_NOT_FOUND')
            target.scenes=[p['scene']]
        restored=target.scenes[0]
        if restored is None:raise RuntimeError('PROJECT_RESTORE_FAILED')
        bpy.context.window.scene=restored
        return {'scene':restored.name,'source_checkpoint':path.name,'previous_scene':previous,'previous_scene_preserved':True}
    if operation=='mesh.edit':
        C.fields(p,('object','expected_vertices','patches'),('object','expected_vertices','patches'))
        ob=_object(scene,p['object'],C,'MESH');count=len(ob.data.vertices)
        if C.integer(p['expected_vertices'],1,100000000)!=count:raise ValueError('MESH_REVISION_CONFLICT')
        if ob.data.shape_keys:raise ValueError('EDIT_SHAPE_KEYS_INSTEAD_OF_BASE_MESH')
        patches=_patches(p['patches'],count,C)
        if ob.data.users>1:ob.data=ob.data.copy()
        for item in patches:ob.data.vertices[item['index']].co=item['coordinate']
        ob.data.update();return {'object':ob.name,'updated_vertices':len(patches),'total_vertices':count}
    if operation=='curve.create':
        C.fields(p,('name','strands','radius','resolution','location'),('name','strands'))
        name=C.safe_name(p['name']);radius=C.number(p.get('radius',0.01),0.00001,10);resolution=C.integer(p.get('resolution',3),0,8)
        location=C.triple(p.get('location',[0,0,0]));strands=p['strands']
        if name in bpy.data.objects:raise ValueError('OBJECT_NAME_EXISTS')
        if not isinstance(strands,list) or not 1<=len(strands)<=256:raise ValueError('INVALID_STRANDS')
        total=0
        for strand in strands:
            if not isinstance(strand,list) or not 2<=len(strand)<=256:raise ValueError('INVALID_STRAND_POINTS')
            total+=len(strand)
            for point in strand:
                if not isinstance(point,list) or len(point)!=4:raise ValueError('STRAND_REQUIRES_XYZ_RADIUS')
                C.triple(point[:3]);C.number(point[3],0.001,100)
        if total>4096:raise ValueError('CURVE_POINT_BUDGET_EXCEEDED')
        curve=bpy.data.curves.new(name+'Curves','CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=resolution;curve.resolution_u=12
        for strand in strands:
            spline=curve.splines.new('POLY');spline.points.add(len(strand)-1)
            for target,point in zip(spline.points,strand):target.co=(*point[:3],1);target.radius=point[3]
        ob=bpy.data.objects.new(name,curve);scene.collection.objects.link(ob);ob.location=location
        return {'object':name,'editable_strands':len(strands),'control_points':total,'radius':radius,'hair_simulation':False}
    if operation=='shape.create':
        C.fields(p,('object','name','expected_vertices','patches'),('object','name','expected_vertices','patches'))
        ob=_object(scene,p['object'],C,'MESH');name=C.safe_name(p['name']);count=len(ob.data.vertices)
        if C.integer(p['expected_vertices'],1,100000000)!=count:raise ValueError('MESH_REVISION_CONFLICT')
        patches=_patches(p['patches'],count,C)
        if ob.data.shape_keys and name in ob.data.shape_keys.key_blocks:raise ValueError('SHAPE_KEY_EXISTS')
        if ob.data.users>1:raise ValueError('SHAPE_REQUIRES_SINGLE_USER_MESH')
        if ob.data.shape_keys is None:ob.shape_key_add(name='Basis',from_mix=False)
        key=ob.shape_key_add(name=name,from_mix=False)
        for item in patches:key.data[item['index']].co=item['coordinate']
        return {'object':ob.name,'shape':key.name,'edited_vertices':len(patches)}
    if operation=='shape.keys':
        C.fields(p,('object','shape','keys'),('object','shape','keys'));ob=_object(scene,p['object'],C,'MESH')
        if not ob.data.shape_keys:raise ValueError('SHAPE_KEY_NOT_FOUND')
        shape=ob.data.shape_keys.key_blocks.get(C.safe_name(p['shape']))
        if shape is None or shape.name=='Basis':raise ValueError('SHAPE_KEY_NOT_FOUND')
        keys=p['keys']
        if not isinstance(keys,list) or not 1<=len(keys)<=256:raise ValueError('INVALID_KEYFRAME_BATCH')
        for item in keys:C.fields(item,('frame','value'),('frame','value'));C.integer(item['frame'],1,100000);C.number(item['value'],0,1)
        current=scene.frame_current
        for item in keys:shape.value=item['value'];shape.keyframe_insert(data_path='value',frame=item['frame'])
        scene.frame_set(current);return {'object':ob.name,'shape':shape.name,'inserted':len(keys)}
    if operation=='rig.create':
        C.fields(p,('name','bones'),('name','bones'));name=C.safe_name(p['name']);bones=p['bones']
        if name in bpy.data.objects:raise ValueError('OBJECT_NAME_EXISTS')
        if not isinstance(bones,list) or not 1<=len(bones)<=128:raise ValueError('INVALID_BONE_COUNT')
        seen=set()
        for bone in bones:
            C.fields(bone,('name','head','tail','parent','roll'),('name','head','tail'));bone_name=C.safe_name(bone['name'])
            if bone_name in seen:raise ValueError('DUPLICATE_BONE')
            head=C.triple(bone['head']);tail=C.triple(bone['tail']);C.number(bone.get('roll',0),-100,100)
            if (Vector(tail)-Vector(head)).length<0.00001:raise ValueError('ZERO_LENGTH_BONE')
            if bone.get('parent') is not None and bone['parent'] not in seen:raise ValueError('BONE_PARENT_MUST_PRECEDE_CHILD')
            seen.add(bone_name)
        if bpy.context.object and bpy.context.object.mode!='OBJECT':raise ValueError('OBJECT_MODE_REQUIRED')
        previous=bpy.context.view_layer.objects.active;selected=list(bpy.context.selected_objects)
        arm=bpy.data.armatures.new(name+'Armature');ob=bpy.data.objects.new(name,arm);scene.collection.objects.link(ob)
        try:
            for item in selected:item.select_set(False)
            ob.select_set(True);bpy.context.view_layer.objects.active=ob;bpy.ops.object.mode_set(mode='EDIT')
            for source in bones:
                bone=arm.edit_bones.new(source['name']);bone.head=source['head'];bone.tail=source['tail'];bone.roll=source.get('roll',0)
                if source.get('parent'):bone.parent=arm.edit_bones[source['parent']]
            bpy.ops.object.mode_set(mode='OBJECT')
            return {'object':name,'bones':len(arm.bones),'native_armature':True}
        except Exception:
            if ob.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
            bpy.data.objects.remove(ob,do_unlink=True);raise
        finally:
            if ob.name in bpy.data.objects:ob.select_set(False)
            for item in selected:
                if item.name in bpy.context.view_layer.objects:item.select_set(True)
            if previous and previous.name in bpy.context.view_layer.objects:bpy.context.view_layer.objects.active=previous
    if operation=='rig.bind':
        C.fields(p,('object','rig','expected_vertices','weights'),('object','rig','expected_vertices','weights'))
        ob=_object(scene,p['object'],C,'MESH');rig=_object(scene,p['rig'],C,'ARMATURE');count=len(ob.data.vertices)
        if C.integer(p['expected_vertices'],1,100000000)!=count:raise ValueError('MESH_REVISION_CONFLICT')
        if any(mod.type=='ARMATURE' for mod in ob.modifiers):raise ValueError('MESH_ALREADY_SKINNED')
        weights=p['weights']
        if not isinstance(weights,list) or not 1<=len(weights)<=4096:raise ValueError('INVALID_WEIGHT_BATCH')
        seen=set();bone_names=set()
        for row in weights:
            C.fields(row,('index','influences'),('index','influences'));index=C.integer(row['index'],0,count-1)
            if index in seen:raise ValueError('DUPLICATE_VERTEX_WEIGHT')
            seen.add(index);influences=row['influences']
            if not isinstance(influences,list) or not 1<=len(influences)<=8:raise ValueError('INVALID_INFLUENCES')
            total=0;used=set()
            for influence in influences:
                if not isinstance(influence,list) or len(influence)!=2:raise ValueError('INVALID_INFLUENCE')
                name=C.safe_name(influence[0]);weight=C.number(influence[1],0,1)
                if name not in rig.data.bones or name in used or name in ob.vertex_groups:raise ValueError('INVALID_OR_EXISTING_BONE_GROUP')
                used.add(name);bone_names.add(name);total+=weight
            if abs(total-1)>0.0001:raise ValueError('WEIGHTS_MUST_SUM_TO_ONE')
        if len(seen)!=count:raise ValueError('COMPLETE_SKIN_WEIGHTS_REQUIRED')
        groups={name:ob.vertex_groups.new(name=name) for name in bone_names}
        for row in weights:
            for name,weight in row['influences']:groups[name].add([row['index']],weight,'REPLACE')
        mod=ob.modifiers.new('ProductionArmature','ARMATURE');mod.object=rig
        return {'object':ob.name,'rig':rig.name,'weighted_vertices':len(seen),'native_deformation':True}
    if operation=='rig.keys':
        C.fields(p,('rig','keys'),('rig','keys'));rig=_object(scene,p['rig'],C,'ARMATURE');keys=p['keys']
        if not isinstance(keys,list) or not 1<=len(keys)<=256:raise ValueError('INVALID_POSE_KEYS')
        for item in keys:
            C.fields(item,('bone','frame','rotation_euler','location'),('bone','frame','rotation_euler'))
            if C.safe_name(item['bone']) not in rig.pose.bones:raise ValueError('POSE_BONE_NOT_FOUND')
            C.integer(item['frame'],1,100000);C.triple(item['rotation_euler'],-100,100)
            if 'location' in item:C.triple(item['location'])
        current=scene.frame_current
        for item in keys:
            bone=rig.pose.bones[item['bone']];bone.rotation_mode='XYZ';bone.rotation_euler=item['rotation_euler'];bone.keyframe_insert(data_path='rotation_euler',frame=item['frame'])
            if 'location' in item:bone.location=item['location'];bone.keyframe_insert(data_path='location',frame=item['frame'])
        scene.frame_set(current);return {'rig':rig.name,'inserted_pose_keys':len(keys)}
    raise ValueError('DETAIL_OPERATION_UNAVAILABLE')
