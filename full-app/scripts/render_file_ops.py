# SPDX-License-Identifier: GPL-2.0-or-later
"""Structured import of owner-staged originals, executed only by Android Blender."""
import json
import contextlib
from pathlib import Path
import uuid
import bpy
import render_file_contract as F
import render_production_contract as C

SCHEMAS={
    'file.importers':{},
    'file.inspect':{'filename':{'type':'string'},'expected_sha256':{'type':'string'},
                    'entry':{'type':'string'},'offset':{'type':'integer','minimum':0},'limit':{'type':'integer','minimum':1,'maximum':100}},
    'file.import':{'filename':{'type':'string'},'expected_sha256':{'type':'string'},'entry':{'type':'string'},
                   'mode':{'enum':['MODEL','BLEND_APPEND','IMAGE_REFERENCE','TEXTURE','ENVIRONMENT','VIDEO_SEQUENCE','AUDIO_SEQUENCE']},
                   'name':{'type':'string'},'objects':{'type':'array','items':{'type':'string'},'maxItems':128},
                   'collections':{'type':'array','items':{'type':'string'},'maxItems':128},
                   'materials':{'type':'array','items':{'type':'string'},'maxItems':128},
                   'max_decoded_bytes':{'type':'integer','minimum':1048576,'maximum':2147483648},
                   'start_frame':{'type':'integer','minimum':1,'maximum':1000000},
                   'channel':{'type':'integer','minimum':1,'maximum':128}},
}


def _operator(name):
    group,member=name.split('.')
    op=getattr(getattr(bpy.ops,group),member);op.get_rna_type();return op


def _available(name):
    try:_operator(name);return True
    except (AttributeError,RuntimeError,KeyError):return False


def capabilities():
    return [{'operation':name,'available':True,'read_only':name!='file.import',
             'checkpoint_before_change':name=='file.import',
             'input_schema':{'type':'object','properties':fields,'additionalProperties':False,
                             'required':[] if name=='file.importers' else ['filename','expected_sha256']}}
            for name,fields in SCHEMAS.items()]


def importers():
    result=[{'extensions':[ext[1:]],'mode':'MODEL','operator':op,'available':_available(op),
             'reason':'' if _available(op) else 'NATIVE_IMPORTER_NOT_BUNDLED_OR_ENABLED'} for ext,op in F.OPERATORS.items()]
    result.extend([
        {'extensions':['blend'],'mode':'BLEND_APPEND','available':True,
         'requires':'explicit objects, collections or materials selected from file.inspect; scene settings remain as saved'},
        {'extensions':sorted(x[1:] for x in F.IMAGES),'mode':'IMAGE_REFERENCE','available':True,
         'decoder_verified':False,'requires':'original dimensions and memory admission; never automatic resizing'},
        {'extensions':sorted(x[1:] for x in F.IMAGES),'mode':'TEXTURE','available':True,'decoder_verified':False},
        {'extensions':['hdr','exr'],'mode':'ENVIRONMENT','available':True,'decoder_verified':False},
        {'extensions':sorted(x[1:] for x in F.VIDEOS),'mode':'VIDEO_SEQUENCE','available':hasattr(bpy.types.Scene,'sequence_editor_create'),
         'decoder_verified':False,'audio_imported_automatically':False},
        {'extensions':sorted(x[1:] for x in F.AUDIO|F.VIDEOS),'mode':'AUDIO_SEQUENCE','available':hasattr(bpy.types.Scene,'sequence_editor_create'),
         'decoder_verified':False},
        {'extensions':['zip'],'mode':'DEPENDENCY_BUNDLE','available':True,'requires':'storage.unpack, then file.inspect and explicit entry'},
    ])
    return {'importers':result,'blender_version':bpy.app.version_string,'native_editor_ready':True,
            'codec_support_requires_native_decoder_success':True,'originals_preserved':True,
            'arbitrary_python_allowed':False,'external_generators_used':False,
            'model_sources':'Poly Haven; supported AmbientCG formats; explicit files and connected Drive file references'}


def _names(p,key):
    names=p.get(key,[])
    if not isinstance(names,list) or len(names)>128 or any(not isinstance(n,str) or not 1<=len(n)<=255 for n in names) or len(set(names))!=len(names):
        raise ValueError('INVALID_BLEND_DATABLOCK_SELECTION')
    return names


def inspect(root,p):
    C.fields(p,SCHEMAS['file.inspect'],('filename','expected_sha256'))
    offset=C.integer(p.get('offset',0),0,1000000);limit=C.integer(p.get('limit',40),1,100)
    original=F.original(root,p['filename'],p['expected_sha256'])
    base={'filename':original.name,'sha256':p['expected_sha256'],'bytes':original.stat().st_size,
          'original_bytes_preserved':True,'native_import_completed':False}
    if original.suffix=='.zip' and not p.get('entry'):
        directory,entries=F.bundle(root,p['expected_sha256'])
        names=sorted(entries);page=[dict(entries[n],extension=Path(n).suffix.lower()[1:]) for n in names[offset:offset+limit]]
        return dict(base,entries=page,total_entries=len(names),next_offset=offset+limit if offset+limit<len(names) else None,
                    requires_explicit_entry=True)
    path,_=F.source(root,p,verified_original=original)
    base.update(extension=path.suffix.lower()[1:],entry=p.get('entry'))
    if path.suffix.lower()=='.blend':
        with bpy.data.libraries.load(str(path),link=False) as (source,target):
            for key in ('objects','collections','materials','scenes','actions','armatures'):
                names=list(getattr(source,key,[]));base[key]=names[offset:offset+limit];base[key+'_total']=len(names)
        base['append_keeps_active_render_settings']=True
    elif path.suffix.lower() in F.IMAGES:
        width,height=F.image_header(path);base.update(width=width,height=height,estimated_decode_bytes=width*height*32,native_decoder_verified=False)
    elif path.suffix.lower() in F.OPERATORS:
        op=F.OPERATORS[path.suffix.lower()];base.update(operator=op,importer_available=_available(op),native_decoder_verified=False)
    elif path.suffix.lower() in F.VIDEOS|F.AUDIO:base.update(native_decoder_verified=False)
    else:base.update(importer_available=False,reason='NATIVE_FILE_FORMAT_UNSUPPORTED')
    return base


def _gltf_dependencies(path,directory):
    if path.suffix.lower()!='.gltf':return
    if path.stat().st_size>64*1024*1024:raise ValueError('GLTF_JSON_TOO_LARGE_USE_GLB')
    data=json.loads(path.read_text())
    from urllib.parse import unquote, urlsplit
    for item in data.get('buffers',[])+data.get('images',[]):
        uri=item.get('uri','')
        if not uri or uri.startswith('data:'):continue
        parts=urlsplit(uri)
        if parts.scheme or parts.netloc or parts.query or parts.fragment:raise ValueError('GLTF_EXTERNAL_URL_REQUIRES_EXPLICIT_BUNDLE')
        import posixpath
        value=posixpath.normpath(str(path.relative_to(directory).parent/unquote(parts.path)))
        target=F.scoped(directory,value)
        if not target.is_file() or not target.resolve().is_relative_to(directory.resolve()):raise ValueError('GLTF_DEPENDENCY_MISSING_USE_STORAGE_UNPACK')


def _preflight(root,p):
    path,directory=F.source(root,p,verify_dependencies=True);suffix=path.suffix.lower()
    mode=p.get('mode','BLEND_APPEND' if suffix=='.blend' else 'IMAGE_REFERENCE' if suffix in F.IMAGES else
               'VIDEO_SEQUENCE' if suffix in F.VIDEOS else 'AUDIO_SEQUENCE' if suffix in F.AUDIO else 'MODEL')
    allowed={'MODEL':set(F.OPERATORS),'BLEND_APPEND':{'.blend'},'IMAGE_REFERENCE':F.IMAGES,'TEXTURE':F.IMAGES,
             'ENVIRONMENT':{'.hdr','.exr'},'VIDEO_SEQUENCE':F.VIDEOS,'AUDIO_SEQUENCE':F.AUDIO|F.VIDEOS}
    if mode not in allowed or suffix not in allowed[mode]:raise ValueError('NATIVE_FILE_IMPORT_MODE_UNSUPPORTED')
    if 'name' in p:C.safe_name(p['name'])
    for key in ('objects','collections','materials'):
        if key in p and mode!='BLEND_APPEND':raise ValueError('DATABLOCK_SELECTION_REQUIRES_BLEND')
    if mode=='BLEND_APPEND':
        requested={key:_names(p,key) for key in ('objects','collections','materials')}
        if not any(requested.values()):raise ValueError('BLEND_APPEND_REQUIRES_EXPLICIT_DATABLOCK_SELECTION')
        with bpy.data.libraries.load(str(path),link=False) as (source,target):
            for key,values in requested.items():
                if not set(values)<=set(getattr(source,key)):raise ValueError('BLEND_DATABLOCK_NOT_FOUND')
    if mode=='MODEL':
        if not _available(F.OPERATORS[suffix]):raise ValueError('NATIVE_IMPORTER_NOT_BUNDLED_OR_ENABLED')
        _gltf_dependencies(path,directory)
    if mode in ('IMAGE_REFERENCE','TEXTURE','ENVIRONMENT'):
        maximum=C.integer(p.get('max_decoded_bytes',128*1024*1024),1024*1024,2*1024**3)
        available=p.get('_available_memory_bytes',maximum)
        F.image_budget(path,min(maximum,max(1024*1024,available)))
    if mode in ('VIDEO_SEQUENCE','AUDIO_SEQUENCE'):
        C.integer(p.get('start_frame',1),1,1000000);C.integer(p.get('channel',1),1,128)
    return path,mode


@contextlib.contextmanager
def _preserve_settings(scene,mode):
    # Native importers can adjust timing, units, active camera or color settings.
    # Keep artist settings unless the operation explicitly replaces the world.
    values=[]
    groups=[(scene.render,('engine','resolution_x','resolution_y','resolution_percentage','fps','fps_base',
                          'film_transparent','use_persistent_data','threads_mode','threads','filepath','use_file_extension')),
            (scene,('frame_start','frame_end','camera')),
            (scene.unit_settings,('system','system_rotation','scale_length','length_unit','mass_unit','time_unit')),
            (scene.view_settings,('view_transform','look','exposure','gamma')),
            (scene.render.image_settings,('file_format','color_mode','color_depth','compression','quality','exr_codec'))]
    if mode!='ENVIRONMENT':groups.append((scene,('world',)))
    for owner,fields in groups:
        for field in fields:
            if hasattr(owner,field):values.append((owner,field,getattr(owner,field)))
    for engine,field in (('CYCLES','samples'),('BLENDER_WORKBENCH','render_aa'),('BLENDER_EEVEE_NEXT','taa_render_samples')):
        owner=getattr(scene,'cycles' if engine=='CYCLES' else 'display' if engine=='BLENDER_WORKBENCH' else 'eevee',None)
        if owner is not None and hasattr(owner,field):values.append((owner,field,getattr(owner,field)))
    current,subframe=scene.frame_current,scene.frame_subframe
    try:yield
    finally:
        for owner,field,value in values:
            if getattr(owner,field)!=value:setattr(owner,field,value)
        if scene.frame_current!=current or scene.frame_subframe!=subframe:scene.frame_set(current,subframe=subframe)
        if any(getattr(owner,field)!=value for owner,field,value in values):raise RuntimeError('IMPORT_SETTINGS_RESTORE_UNVERIFIED_CHECKPOINT_AVAILABLE')


def _import(scene,path,mode,p):
    name=p.get('name','Imported_'+uuid.uuid4().hex[:12]);before=set(bpy.data.objects);before_images=set(bpy.data.images)
    result={'mode':mode,'original_bytes_preserved':True}
    if mode=='MODEL':
        outcome=_operator(F.OPERATORS[path.suffix.lower()])(filepath=str(path))
        if 'FINISHED' not in outcome:raise RuntimeError('NATIVE_IMPORTER_DID_NOT_FINISH')
    elif mode=='BLEND_APPEND':
        with bpy.data.libraries.load(str(path),link=False) as (source,target):
            for key in ('objects','collections','materials'):setattr(target,key,_names(p,key))
        for collection in target.collections:
            if collection and collection.name not in scene.collection.children:scene.collection.children.link(collection)
        for ob in target.objects:
            if ob and ob.name not in scene.objects:scene.collection.objects.link(ob)
        for material in target.materials:
            if material:material.use_fake_user=True
        result['materials']=[m.name for m in target.materials if m]
        result['append_preserves_native_rigs_actions_and_editable_meshes']=True
    elif mode in ('IMAGE_REFERENCE','TEXTURE','ENVIRONMENT'):
        image=bpy.data.images.load(str(path),check_existing=True)
        if image.size[0]<1 or image.size[1]<1:raise ValueError('NATIVE_IMAGE_DECODER_UNSUPPORTED')
        image.pack();result.update(image=image.name,original_resolution=list(image.size))
        if mode=='IMAGE_REFERENCE':
            ob=bpy.data.objects.new(name,None);ob.empty_display_type='IMAGE';ob.data=image;ob.empty_display_size=2
            ob.hide_render=True;ob.location=scene.cursor.location;scene.collection.objects.link(ob)
            result.update(object=ob.name,excluded_from_final_render=True)
        elif mode=='TEXTURE':
            material=bpy.data.materials.new(name);material.use_nodes=True;material.use_fake_user=True
            shader=next(node for node in material.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
            node=material.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
            material.node_tree.links.new(node.outputs['Color'],shader.inputs['Base Color'])
            result.update(material=material.name,assigned_to_objects=False)
        else:
            world=scene.world.copy() if scene.world else bpy.data.worlds.new(name);world.use_nodes=True
            env=world.node_tree.nodes.new('ShaderNodeTexEnvironment');env.image=image
            background=next((node for node in world.node_tree.nodes if node.type=='BACKGROUND'),None)
            if background is None:
                background=world.node_tree.nodes.new('ShaderNodeBackground')
                output=world.node_tree.nodes.new('ShaderNodeOutputWorld');world.node_tree.links.new(background.outputs[0],output.inputs[0])
            world.node_tree.links.new(env.outputs['Color'],background.inputs['Color']);scene.world=world;result.update(world=world.name)
    else:
        editor=scene.sequence_editor_create();strips=getattr(editor,'strips',None)
        if strips is None:strips=getattr(editor,'sequences',None)
        if strips is None:raise ValueError('NATIVE_SEQUENCER_UNAVAILABLE')
        if strips.get(name):raise ValueError('SEQUENCE_NAME_ALREADY_EXISTS')
        channel=p.get('channel',1);start=p.get('start_frame',scene.frame_current)
        strip=(strips.new_movie if mode=='VIDEO_SEQUENCE' else strips.new_sound)(name,str(path),channel,start)
        # Preserve the artist's fps/range/resolution. Report the decoded clip instead.
        result.update(strip=strip.name,start_frame=strip.frame_start,end_frame=strip.frame_final_end,
                      duration_frames=strip.frame_final_duration,channel=strip.channel,native_decoder_verified=True,
                      audio_imported=mode=='AUDIO_SEQUENCE')
        if mode=='VIDEO_SEQUENCE':
            element=strip.elements[0] if len(strip.elements) else None
            result.update(source_width=getattr(element,'orig_width',None),source_height=getattr(element,'orig_height',None),
                          source_fps=getattr(strip,'fps',None),scene_fps_preserved=True)
    missing=[]
    for image in set(bpy.data.images)-before_images:
        if image.source=='FILE' and not image.packed_file:
            candidate=Path(bpy.path.abspath(image.filepath,library=image.library))
            if image.filepath.startswith('//'):
                source_relative=path.parent/image.filepath[2:]
                if source_relative.is_file():candidate=source_relative
            if candidate.is_file():image.filepath=str(candidate);image.reload();image.pack()
            else:missing.append(image.name)
    objects=[ob.name for ob in set(bpy.data.objects)-before]
    result.update(objects=objects[:128],imported_objects_total=len(objects),missing_images=missing[:128],
                  native_import_completed=not missing,quality_reduced=False)
    if missing:result.update(recovery='Original retained; supply a packed .blend/GLB or complete dependency ZIP. Inspect the checkpoint before retrying.',safe_to_replay=False)
    return result


def execute(operation,scene,root,p):
    if operation=='file.importers':C.fields(p,());return importers()
    if operation=='file.inspect':return inspect(root,p)
    C.fields(p,(*SCHEMAS['file.import'],'_available_memory_bytes'),('filename','expected_sha256'))
    path,mode=_preflight(root,p)
    import render_artist_ops
    checkpoint=render_artist_ops.checkpoint(scene,root,'file.import')
    try:
        with _preserve_settings(scene,mode):result=_import(scene,path,mode,p)
        result['artist_render_settings_preserved']=True
    except Exception as error:
        error.render_checkpoint=checkpoint
        from render_production import _write
        _write(Path(root)/'Projects'/('Failure_'+uuid.uuid4().hex+'.json'),{
            'operation':operation,'checkpoint':checkpoint,'error':str(error)[:160],
            'safe_to_replay':False,'recovery':'inspect exact command result and scene; restore checkpoint explicitly'})
        raise
    return dict(result,filename=p['filename'],entry=p.get('entry'),checkpoint=checkpoint,native_execution_verified=True)


def register():pass
def unregister():pass
