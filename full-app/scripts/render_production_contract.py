# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure validation shared by native bpy operations and host regression tests."""
import hashlib
import json
import math
from pathlib import Path
import re

OPERATIONS = frozenset((
    'file.importers','file.inspect','file.import',
    'artist.capabilities','artist.inspect','body.blockout','camera.frame','viewport.orient','sculpt.prepare','object.duplicate','object.remove','sculpt.mask','sculpt.stroke','facial.expression','material.inspect','light.configure','camera.configure','media.import','project.export',
    'asset.search','asset.details','asset.preview','asset.download','asset.download.status','asset.download.pause','asset.import',
    'render.quality.inspect','render.quality.configure','render.performance.inspect','render.performance.configure',
    'render.profile.inspect','render.profile.configure',
    'capabilities', 'device.profile', 'editor.open', 'screenshot.capture',
    'artifact.read', 'artifact.export', 'reference.write',
    'asset.create', 'project.create', 'project.checkpoint', 'scene.inspect', 'mesh.create',
    'project.list','project.restore','mesh.edit','curve.create','shape.create','shape.keys','rig.create','rig.bind','rig.keys',
    'material.assign', 'group.create', 'animation.keys', 'camera.aim',
    'world.configure', 'instances.plan', 'instances.create', 'reference.attach',
    'reference.bind','reference.landmarks','viewport.inspect','viewport.configure','viewport.focus',
    'reference.workspace.open','reference.workspace.inspect','reference.compare.multiview','reference.fit.landmarks','reference.fit.multiview',
    'animation.clip.create','animation.clip.inspect','animation.motion.audit',
    'studio.capabilities','studio.tool.search','studio.workspace.activate','studio.workspace.inspect',
    'studio.view.orbit','studio.editor.open','studio.sculpt.inspect','studio.sculpt.brush',
    'studio.pose.inspect','studio.pose.key','studio.timeline.scrub',
    'studio.ik.create','studio.ik.inspect','studio.ik.target','studio.ik.blend',
    'studio.reference.timeline.bind','studio.reference.timeline.inspect','studio.reference.timeline.scrub',
    'studio.curve.inspect','studio.curve.adjust',
    'studio.agent.bootstrap','studio.agent.batch.inspect',
    'studio.agent.plan.preview','studio.agent.metrics',
    'studio.preview.capabilities','studio.preview.inspect',
    'studio.preview.diagnose','studio.preview.profile.apply',
    'studio.preview.profile.restore','studio.preview.aa.inspect',
    'studio.preview.aa.configure',
    'studio.plan.submit','studio.plan.status',
    'studio.plan.list','studio.plan.pause','studio.plan.resume','studio.plan.cancel','studio.activity',
    'object.geometry','operator.describe','operator.execute',
    'render.plan', 'render.step', 'render.status', 'render.encode',
))
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')
FILE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')
MAX_INSTANCES = 10_000_000

def fields(data, allowed, required=()):
    if not isinstance(data, dict) or set(data)-set(allowed) or not set(required)<=set(data):
        raise ValueError('INVALID_ARGUMENTS')
    return data

def number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('INVALID_FINITE_NUMBER')
    return value

def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('INVALID_INTEGER')
    return value

def triple(value, low=-100000, high=100000):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError('INVALID_VECTOR')
    return [number(x, low, high) for x in value]

def safe_name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError('INVALID_NAME')
    return value

def owned_path(root, filename):
    root = Path(root).resolve()
    if not isinstance(filename, str) or not FILE.fullmatch(filename) or '..' in filename:
        raise ValueError('INVALID_ARTIFACT_NAME')
    path = root / filename
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError('ARTIFACT_OUTSIDE_SCOPE')
    return path

def fingerprint(value):
    try:
        raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')
    except (ValueError, TypeError) as error:
        raise ValueError('INVALID_CANONICAL_JSON') from error
    return hashlib.sha256(raw).hexdigest()

def validate_envelope(args):
    fields(args, ('operation', 'payload'), ('operation',))
    op = args['operation']
    if not isinstance(op, str) or op not in OPERATIONS:
        raise ValueError('PRODUCTION_OPERATION_UNAVAILABLE')
    payload = args.get('payload', {})
    if not isinstance(payload, dict):
        raise ValueError('INVALID_PAYLOAD')
    if len(json.dumps(args, allow_nan=False).encode('utf8')) > 131072:
        raise ValueError('PRODUCTION_REQUEST_TOO_LARGE')
    return op, payload

def instance_plan(data, available_bytes):
    fields(data, ('name', 'source', 'counts', 'spacing', 'confirm_large_scene'), ('counts', 'spacing'))
    counts = data['counts']
    if not isinstance(counts, list) or len(counts) != 3:
        raise ValueError('INVALID_INSTANCE_GRID')
    counts = [integer(n, 1, MAX_INSTANCES) for n in counts]
    count = math.prod(counts)
    integer(count, 1, MAX_INSTANCES)
    triple(data['spacing'], 0.0001, 100000)
    if 'name' in data: safe_name(data['name'])
    if 'source' in data: safe_name(data['source'])
    if 'confirm_large_scene' in data and type(data['confirm_large_scene']) is not bool:
        raise ValueError('INVALID_CONFIRMATION')
    available = integer(available_bytes, 0, 2**63-1)
    # Conservative admission estimate, not a renderer-specific upper bound.
    estimate = count * 256 + 256 * 1024**2
    return {'instance_count': count, 'counts': counts, 'node_levels': 3,
            'realize_instances': False, 'estimated_bytes': estimate,
            'available_bytes': available, 'admitted': estimate <= available * 0.60,
            'hardware_verified': False, 'quality_reduced': False,
            'estimate_is_guarantee': False}

def render_spec(data):
    fields(data, ('name','width','height','fps','start','end','samples','engine','bitrate','output_kind'))
    result = {'width': integer(data.get('width',1280),16,8192),
              'height': integer(data.get('height',720),16,8192),
              'fps': integer(data.get('fps',24),1,120),
              'start': integer(data.get('start',1),1,100000),
              'end': integer(data.get('end',240),1,100000),
              'samples': integer(data.get('samples',64),1,16_777_216),
              'bitrate': integer(data.get('bitrate',16000000),100000,200000000),
              'engine': data.get('engine','BLENDER_EEVEE'),
              'output_kind': data.get('output_kind','ANIMATION')}
    if result['width']%2 or result['height']%2 or result['end']<result['start']:
        raise ValueError('INVALID_RENDER_RANGE_OR_DIMENSIONS')
    if result['engine'] not in ('BLENDER_EEVEE','BLENDER_EEVEE_NEXT','CYCLES','BLENDER_WORKBENCH'):
        raise ValueError('INVALID_RENDER_ENGINE')
    if result['output_kind'] not in ('STILL','ANIMATION'):
        raise ValueError('INVALID_RENDER_OUTPUT_KIND')
    if result['output_kind']=='STILL' and result['start']!=result['end']:
        raise ValueError('STILL_RENDER_MUST_BE_SINGLE_FRAME')
    if 'name' in data: result['name']=safe_name(data['name'])
    result['frame_count']=result['end']-result['start']+1
    integer(result['frame_count'],1,100000)
    return result

def mesh_spec(data):
    fields(data, ('name','kind','vertices','faces','location','scale','rotation_euler','segments','rings','bevel','smooth'), ('name',))
    result=dict(data);safe_name(result['name'])
    for key in ('location','rotation_euler','scale'):
        if key in result:triple(result[key], 0.0001 if key=='scale' else -100000,100000)
    if 'smooth' in result and type(result['smooth']) is not bool:raise ValueError('INVALID_SMOOTH')
    number(result.get('bevel',0),0,100)
    integer(result.get('segments',48),8,256);integer(result.get('rings',24),4,128)
    kind=result.get('kind','MESH' if 'vertices' in result else 'UV_SPHERE')
    if kind not in ('MESH','CUBE','UV_SPHERE','ICO_SPHERE','CYLINDER','CONE','PLANE','TORUS'):
        raise ValueError('INVALID_MESH_KIND')
    result['kind']=kind
    if kind=='MESH':
        vertices=result.get('vertices');faces=result.get('faces')
        if not isinstance(vertices,list) or not 3<=len(vertices)<=4096 or not isinstance(faces,list) or not 1<=len(faces)<=4096:
            raise ValueError('INVALID_TOPOLOGY')
        for v in vertices:triple(v)
        for f in faces:
            if not isinstance(f,list) or not 3<=len(f)<=64 or len(set(f))!=len(f):raise ValueError('INVALID_FACE')
            for index in f:integer(index,0,len(vertices)-1)
    return result

def file_receipt(path):
    path=Path(path)
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1048576),b''):digest.update(chunk)
    return {'filename':path.name,'bytes':path.stat().st_size,'sha256':digest.hexdigest()}

def frame_matches(root, receipt):
    try:
        path=owned_path(root,receipt['filename'])
        return path.is_file() and file_receipt(path)==receipt
    except (ValueError, OSError, KeyError, TypeError):return False
