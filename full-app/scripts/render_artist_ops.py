# SPDX-License-Identifier: GPL-2.0-or-later
"""Discoverable typed artist tools, executed only by Android Blender's bpy timer."""
import contextlib
import json
import math
from pathlib import Path
import re
import uuid
import bpy

SCHEMAS = {
    'artist.capabilities': [],
    'artist.inspect': [],
    'body.blockout': ['name', 'proportions', 'subdivision_levels'],
    'object.duplicate': ['object', 'name', 'linked'],
    'object.remove': ['object'],
    'sculpt.mask': ['object', 'vertices', 'weights'],
    'sculpt.stroke': ['object', 'points'],
    'facial.expression': ['object', 'weights'],
    'material.inspect': ['material'],
    'light.configure': ['object', 'energy', 'color', 'size'],
    'camera.configure': ['object', 'lens', 'clip_start', 'clip_end'],
    'media.import': ['asset', 'name', 'mode', 'start_frame', 'channel'],
    'project.export': ['format'],
}
READ_ONLY = {'artist.capabilities', 'artist.inspect', 'material.inspect'}
_FIELDS = {
    'proportions': {'type':'object'},
    'subdivision_levels': {'type':'integer','minimum':0,'maximum':3},
    'object': {'type':'string','minLength':1,'maxLength':255},
    'material': {'type':'string','minLength':1,'maxLength':255},
    'name': {'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_-]{0,63}$'},
    'linked': {'type':'boolean'},
    'vertices': {'type':'array','minItems':1,'maxItems':50000,'items':{'type':'integer','minimum':0}},
    'weights': {'type':'object','additionalProperties':{'type':'number'},'maxProperties':64},
    'points': {'type':'array','minItems':1,'maxItems':128,'items':{'type':'object',
        'required':['x','y'],'additionalProperties':False,'properties':{
            'x':{'type':'number','minimum':0},'y':{'type':'number','minimum':0},
            'pressure':{'type':'number','minimum':0,'maximum':1},'size':{'type':'number','minimum':1,'maximum':2048}}}},
    'energy': {'type':'number','minimum':0,'maximum':1e9},
    'color': {'type':'array','minItems':3,'maxItems':3,'items':{'type':'number','minimum':0,'maximum':1}},
    'size': {'type':'number','minimum':.0001,'maximum':1e6},
    'lens': {'type':'number','minimum':1,'maximum':5000},
    'clip_start': {'type':'number','minimum':.000001,'maximum':1e6},
    'clip_end': {'type':'number','minimum':.001,'maximum':1e9},
    'asset': {'type':'string','pattern':'^[a-f0-9]{64}\\.(png|jpg|jpeg|webp|mp4)$'},
    'mode': {'enum':['IMAGE_REFERENCE','VIDEO_SEQUENCE']},
    'start_frame': {'type':'integer','minimum':1,'maximum':1000000},
    'channel': {'type':'integer','minimum':1,'maximum':128},
    'format': {'enum':['BLEND','GLB']},
}
_REQUIRED = {'object.duplicate':['object','name'],'object.remove':['object'],
             'body.blockout':['name','proportions'],
             'sculpt.mask':['object','vertices','weights'],'sculpt.stroke':['object','points'],
             'facial.expression':['object','weights'],'material.inspect':['material'],
             'light.configure':['object'],'camera.configure':['object'],'media.import':['asset']}


def _fields(p, operation):
    if not isinstance(p, dict) or set(p) - set(SCHEMAS[operation]):
        raise ValueError('UNKNOWN_ARTIST_ARGUMENT')


def _number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('ARTIST_VALUE_OUT_OF_RANGE')
    return value


def _object(scene, name, kind=None):
    if not isinstance(name, str) or not 1 <= len(name) <= 255:
        raise ValueError('INVALID_ARTIST_OBJECT_NAME')
    ob = scene.objects.get(name)
    if ob is None or kind is not None and ob.type != kind:
        raise ValueError('ARTIST_OBJECT_MISSING_OR_WRONG_TYPE')
    return ob


def _operator(path):
    group, name = path.split('.')
    op = getattr(getattr(bpy.ops, group), name)
    op.get_rna_type()  # getattr alone also returns wrappers for nonexistent ops.
    return op


def checkpoint(scene, root, reason):
    if scene.get('production_frozen_job'):
        raise ValueError('RENDER_SNAPSHOT_IMMUTABLE')
    folder = Path(root) / 'Projects'
    if folder.is_symlink():
        raise ValueError('CHECKPOINT_FOLDER_SYMLINK')
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    import shutil
    if shutil.disk_usage(folder).free < 256*1024*1024:
        raise ValueError('CHECKPOINT_STORAGE_PRESSURE')
    path = folder / ('Before_' + uuid.uuid4().hex + '.blend')
    import render_session_tools
    receipt=render_session_tools.save_copy_atomic(path,compress=False)
    return dict(receipt, category='Projects', reason=reason, source_project_unchanged=True)


@contextlib.contextmanager
def _target(scene, ob, sculpt=False):
    active = bpy.context.view_layer.objects.active
    selected = list(bpy.context.selected_objects)
    previous_mode = active.mode if active else 'OBJECT'
    if active and active.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    try:
        for item in selected:
            item.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        window = bpy.context.window
        area = next((a for a in window.screen.areas if a.type == 'VIEW_3D'), None) if window else None
        region = next((r for r in area.regions if r.type == 'WINDOW'), None) if area else None
        if sculpt and (not area or not region):
            raise ValueError('SCULPT_REQUIRES_NATIVE_VIEWPORT')
        if sculpt:
            with bpy.context.temp_override(window=window, area=area, region=region, scene=scene):
                bpy.ops.object.mode_set(mode='SCULPT')
                yield region
        else:
            yield None
    finally:
        if ob.name in bpy.data.objects and ob.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if ob.name in bpy.data.objects:
            ob.select_set(False)
        for item in selected:
            if item.name in bpy.data.objects:
                item.select_set(True)
        if active and active.name in bpy.data.objects:
            bpy.context.view_layer.objects.active = active
            if previous_mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode=previous_mode)


def execute(operation, scene, root, p):
    _fields(p, operation)
    if operation == 'artist.capabilities':
        operations = []
        for op, fields in SCHEMAS.items():
            available, reason = True, ''
            native = {'sculpt.stroke': 'sculpt.brush_stroke', 'project.export': 'wm.save_as_mainfile'}.get(op)
            if native:
                try:
                    _operator(native)
                except (AttributeError, RuntimeError):
                    available, reason = False, 'NATIVE_OPERATOR_NOT_BUNDLED'
            properties={field:_FIELDS[field] for field in fields}
            if op=='body.blockout':
                from render_body_blockout import profile_schema
                properties['proportions']=profile_schema()
            if op=='sculpt.mask':properties['weights']={'type':'array','minItems':1,'maxItems':50000,
                'items':{'type':'number','minimum':0,'maximum':1}}
            operations.append({'operation': op, 'fields': fields, 'read_only': op in READ_ONLY,
                               'available': available, 'reason': reason,
                               'input_schema':{'type':'object','properties':properties,
                                               'additionalProperties':False,'required':_REQUIRED.get(op,[])},
                               'checkpoint_before_change': op not in READ_ONLY})
        try:
            _operator('export_scene.gltf')
            glb = True
        except (AttributeError, RuntimeError):
            glb = False
        return {'operations': operations, 'blender_version': bpy.app.version_string,
                'export_formats': ['BLEND'] + (['GLB'] if glb else []),
                'sculpt_stroke_requires': 'active native sculpt brush and VIEW_3D context',
                'arbitrary_python_allowed': False,
                'runtime_acceptance_not_established_by_capabilities': True}
    if operation == 'artist.inspect':
        return {'scene': scene.name, 'mode': bpy.context.mode,
                'selected': [ob.name for ob in bpy.context.selected_objects][:128],
                'objects': len(scene.objects), 'materials': len(bpy.data.materials),
                'images': len(bpy.data.images), 'collections': [c.name for c in scene.collection.children][:128],
                'armatures': [ob.name for ob in scene.objects if ob.type == 'ARMATURE'][:128],
                'frame': scene.frame_current, 'frame_start': scene.frame_start, 'frame_end': scene.frame_end,
                'camera': scene.camera.name if scene.camera else None,
                'units': scene.unit_settings.system, 'native_execution_verified': True}
    if operation == 'material.inspect':
        material = bpy.data.materials.get(p.get('material', ''))
        if material is None:
            raise ValueError('MATERIAL_NOT_FOUND')
        return {'material': material.name, 'use_nodes': material.use_nodes,
                'nodes': [{'name': n.name, 'type': n.bl_idname} for n in material.node_tree.nodes][:256]
                    if material.use_nodes else [], 'native_execution_verified': True}

    # Checkpoint before consequential native edits/import/export. Failures preserve
    # a concrete .blend receipt and never cause automatic command replay.
    saved = checkpoint(scene, root, operation)
    try:
        result = _mutate(operation, scene, root, p)
    except Exception as error:
        error.render_checkpoint=saved
        failure = {'operation': operation, 'checkpoint': saved, 'error': str(error)[:160],
                   'safe_to_replay': False, 'recovery': 'inspect scene and restore checkpoint explicitly'}
        failure_path = Path(root) / 'Projects' / ('Failure_' + uuid.uuid4().hex + '.json')
        from render_production import _write
        _write(failure_path, failure)
        raise
    return dict(result, checkpoint=saved, native_execution_verified=True)


def _mutate(operation, scene, root, p):
    if operation == 'body.blockout':
        import render_body_blockout
        return render_body_blockout.create(scene,p.get('name'),p.get('proportions'),p.get('subdivision_levels',2))
    if operation == 'object.duplicate':
        ob = _object(scene, p.get('object'))
        name = p.get('name')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', name) or name in bpy.data.objects:
            raise ValueError('INVALID_OR_EXISTING_OBJECT_NAME')
        if type(p.get('linked', False)) is not bool:
            raise ValueError('INVALID_LINKED_DUPLICATE_SETTING')
        copy = ob.copy()
        if ob.data and not p.get('linked', False):
            copy.data = ob.data.copy()
        copy.name = name
        scene.collection.objects.link(copy)
        return {'object': copy.name, 'linked': p.get('linked', False), 'editable': True}
    if operation == 'object.remove':
        ob = _object(scene, p.get('object'))
        if len(ob.users_scene) > 1:
            raise ValueError('OBJECT_SHARED_WITH_ANOTHER_SCENE')
        name = ob.name
        bpy.data.objects.remove(ob, do_unlink=True)
        return {'removed_object': name, 'checkpoint_required_for_restore': True}
    if operation == 'sculpt.mask':
        ob = _object(scene, p.get('object'), 'MESH')
        indices, weights = p.get('vertices'), p.get('weights')
        if (not isinstance(indices, list) or not isinstance(weights, list) or not 1 <= len(indices) <= 50000
                or len(indices) != len(weights) or len(set(indices)) != len(indices)):
            raise ValueError('INVALID_SCULPT_MASK')
        for index, weight in zip(indices, weights):
            if type(index) is not int or not 0 <= index < len(ob.data.vertices):
                raise ValueError('SCULPT_VERTEX_OUT_OF_RANGE')
            _number(weight, 0, 1)
        if ob.mode != 'OBJECT' or ob.data.users > 1:
            raise ValueError('SCULPT_MASK_REQUIRES_UNSHARED_OBJECT_MODE_MESH')
        mask = ob.data.attributes.get('.sculpt_mask')
        if mask and (mask.domain != 'POINT' or mask.data_type != 'FLOAT'):
            raise ValueError('INCOMPATIBLE_SCULPT_MASK_ATTRIBUTE')
        mask = mask or ob.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
        for index, weight in zip(indices, weights):
            mask.data[index].value = weight
        ob.data.update()
        return {'object': ob.name, 'masked_vertices': len(indices), 'geometry_quality_changed': False}
    if operation == 'sculpt.stroke':
        ob = _object(scene, p.get('object'), 'MESH')
        points = p.get('points')
        if not isinstance(points, list) or not 1 <= len(points) <= 128 or ob.data.users > 1:
            raise ValueError('INVALID_SCULPT_STROKE_OR_SHARED_MESH')
        op = _operator('sculpt.brush_stroke')
        with _target(scene, ob, True) as region:
            if not op.poll():
                raise ValueError('NATIVE_SCULPT_BRUSH_UNAVAILABLE_IN_CONTEXT')
            stroke = []
            for i, point in enumerate(points):
                if not isinstance(point, dict) or set(point) - {'x','y','pressure','size'}:
                    raise ValueError('INVALID_SCULPT_POINT')
                x, y = _number(point.get('x'), 0, region.width-1), _number(point.get('y'), 0, region.height-1)
                stroke.append({'name': 'RenderNativeStroke', 'mouse': (x,y), 'mouse_event': (x,y),
                               'pressure': _number(point.get('pressure', 1), 0, 1),
                               'size': _number(point.get('size', 24), 1, 2048),
                               'time': i / 60, 'is_start': i == 0, 'pen_flip': False, 'location': (0,0,0)})
            if 'FINISHED' not in op(stroke=stroke, mode='NORMAL'):
                raise RuntimeError('NATIVE_SCULPT_STROKE_NOT_FINISHED')
        return {'object': ob.name, 'native_brush_stroke_completed': True, 'stroke_points': len(stroke)}
    if operation == 'facial.expression':
        ob = _object(scene, p.get('object'), 'MESH')
        keys = ob.data.shape_keys
        weights = p.get('weights')
        if keys is None or not isinstance(weights, dict) or not 1 <= len(weights) <= 64:
            raise ValueError('FACIAL_SHAPE_KEYS_REQUIRED')
        if ob.data.users>1:
            raise ValueError('FACIAL_KEYS_SHARED_DUPLICATE_MESH_FIRST')
        checked = []
        for name, value in weights.items():
            key = keys.key_blocks.get(name)
            if key is None or key == keys.key_blocks[0]:
                raise ValueError('FACIAL_SHAPE_KEY_NOT_FOUND')
            checked.append((key, _number(value, key.slider_min, key.slider_max)))
        for key, value in checked:
            key.value = value
        return {'object': ob.name, 'expression_weights': weights, 'rig_and_shape_keys_preserved': True}
    if operation in ('light.configure', 'camera.configure'):
        if set(p)=={'object'}:raise ValueError('ARTIST_SETTING_REQUIRED')
        ob = _object(scene, p.get('object'), 'LIGHT' if operation.startswith('light') else 'CAMERA')
        if ob.data.users>1:raise ValueError('TARGET_DATA_SHARED_DUPLICATE_DATA_FIRST')
        ranges = {'energy': (0,1e9), 'size': (.0001,1e6), 'lens': (1,5000),
                  'clip_start': (.000001,1e6), 'clip_end': (.001,1e9)}
        changes = []
        for key, value in p.items():
            if key == 'object':
                continue
            if key == 'color':
                if not isinstance(value,list) or len(value)!=3:
                    raise ValueError('INVALID_LIGHT_COLOR')
                value = [_number(v,0,1) for v in value]
            else:
                _number(value,*ranges[key])
            if not hasattr(ob.data,key):
                raise ValueError('NATIVE_PROPERTY_UNAVAILABLE_FOR_OBJECT')
            changes.append((key,value))
        start = p.get('clip_start', getattr(ob.data, 'clip_start', 0))
        end = p.get('clip_end', getattr(ob.data, 'clip_end', 1))
        if operation.startswith('camera') and end <= start:
            raise ValueError('INVALID_CAMERA_CLIP_RANGE')
        for key,value in changes:
            setattr(ob.data,key,value)
        return {'object':ob.name,'changed_fields':[key for key,_ in changes]}
    if operation == 'media.import':
        from render_studio_ops import _asset
        path = _asset(Path(root), p.get('asset'))
        mode = p.get('mode', 'IMAGE_REFERENCE')
        name=p.get('name','ImportedMedia_'+uuid.uuid4().hex[:8])
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',name) or name in bpy.data.objects:
            raise ValueError('INVALID_OR_EXISTING_MEDIA_NAME')
        if mode == 'VIDEO_SEQUENCE':
            if path.suffix != '.mp4':
                raise ValueError('VIDEO_SEQUENCE_REQUIRES_ORIGINAL_MP4')
            start, channel = p.get('start_frame',scene.frame_current),p.get('channel',1)
            if type(start) is not int or not 1<=start<=1000000 or type(channel) is not int or not 1<=channel<=128:
                raise ValueError('INVALID_VIDEO_SEQUENCE_LOCATION')
            editor=scene.sequence_editor_create()
            strips=getattr(editor,'strips',None)
            if strips is None:strips=getattr(editor,'sequences',None)
            if strips is None:raise ValueError('NATIVE_VIDEO_SEQUENCER_UNAVAILABLE')
            if strips.get(name):raise ValueError('MEDIA_STRIP_NAME_EXISTS')
            strip=strips.new_movie(name,str(path),channel,start)
            return {'strip':strip.name,'source_asset':path.name,'audio_imported':False,'original_preserved':True,
                    'start_frame':strip.frame_start,'channel':strip.channel}
        if mode != 'IMAGE_REFERENCE' or path.suffix == '.mp4':
            raise ValueError('UNSUPPORTED_NATIVE_MEDIA_IMPORT_MODE')
        image=bpy.data.images.load(str(path),check_existing=True)
        if image.size[0]<1 or image.size[1]<1:raise ValueError('NATIVE_IMAGE_DECODER_UNSUPPORTED')
        image.pack()
        ob=bpy.data.objects.new(name,None)
        ob.empty_display_type='IMAGE';ob.data=image;ob.empty_display_size=5
        ob.hide_render=True;scene.collection.objects.link(ob)
        return {'object':ob.name,'source_asset':path.name,'original_resolution':list(image.size),
                'original_preserved':True,'excluded_from_final_render':True}
    if operation == 'project.export':
        form=p.get('format','BLEND')
        if form not in ('BLEND','GLB'):raise ValueError('NATIVE_EXPORT_FORMAT_UNAVAILABLE')
        folder=Path(root)/'Exports'
        if folder.is_symlink():raise ValueError('EXPORT_FOLDER_SYMLINK')
        folder.mkdir(mode=0o700,exist_ok=True)
        path=folder/('Export_'+uuid.uuid4().hex+('.blend' if form=='BLEND' else '.glb'))
        if form=='BLEND':
            import render_session_tools
            receipt=render_session_tools.save_copy_atomic(path,compress=False)
        else:
            result=_operator('export_scene.gltf')(filepath=str(path),export_format='GLB',check_existing=False)
            if 'FINISHED' not in result or not path.is_file():raise RuntimeError('NATIVE_EXPORT_NOT_FINISHED')
            from omega.phase02_render import sync_file, sync_directory
            sync_file(path);sync_directory(folder)
            from render_production_contract import file_receipt
            receipt=file_receipt(path)
        return dict(receipt,category='Exports',editable_blend_preserved=True,format=form)
    raise ValueError('ARTIST_OPERATION_UNAVAILABLE')
