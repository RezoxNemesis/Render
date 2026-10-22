# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure, device-independent contracts for source-guided Android Blender work.

Numbers returned by these helpers are measurements/plans, NOT a likeness score.
No arbitrary Blender/Python command or external filesystem path is accepted.
"""
import math
import re
from pathlib import Path

def owned_path(root, filename):
    root=Path(root).resolve()
    if not isinstance(filename,str) or not re.fullmatch(r'[a-f0-9]{64}\\.(?:png|jpg|jpeg|webp|mp4)',filename):
        raise ValueError('INVALID_OWNED_REFERENCE_NAME')
    candidate=root/filename
    if candidate.is_symlink() or candidate.resolve().parent!=root:
        raise ValueError('REFERENCE_PATH_OUTSIDE_SCOPE')
    return candidate

SCHEMAS = {
    'ui.state': {'fields': []},
    'reference.list': {'fields': ['offset', 'limit']},
    'reference.bind': {'fields': ['asset', 'name', 'location', 'size', 'crop', 'opacity', 'mode']},
    'reference.landmarks': {'fields': ['object', 'reference', 'model']},
    'reference.metadata': {'fields': ['asset']},
    'viewport.inspect': {'fields': []},
    'viewport.configure': {'fields': ['radius', 'distance', 'clip_start', 'clip_end', 'anti_alias']},
    'viewport.focus': {'fields': ['object', 'margin']},
    'object.geometry': {'fields': ['object', 'offset', 'limit']},
    'operator.describe': {'fields': ['operator']},
    'operator.execute': {'fields': ['operator', 'parameters', 'expected_object']},
}
SAFE_EXTENSION = frozenset(('png', 'jpg', 'jpeg', 'webp', 'mp4'))
HASH = re.compile(r'^[a-f0-9]{64}$')
NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,63}$')

def finite(value, low=None, high=None):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('INVALID_FINITE_NUMBER')
    if low is not None and value < low: raise ValueError('NUMBER_OUT_OF_RANGE')
    if high is not None and value > high: raise ValueError('NUMBER_OUT_OF_RANGE')
    return float(value)

def asset_name(hash_sha256, ext):
    if not isinstance(hash_sha256, str) or not HASH.fullmatch(hash_sha256):
        raise ValueError('INVALID_ASSET_HASH')
    if not isinstance(ext, str) or ext not in SAFE_EXTENSION:
        raise ValueError('INVALID_ASSET_FORMAT')
    return hash_sha256 + '.' + ext

def crop_rect(crop):
    if not isinstance(crop, list) or len(crop) != 4:
        raise ValueError('INVALID_CROP_RECT')
    x0,y0,x1,y1=[finite(x,0,1) for x in crop]
    if x1<=x0 or y1<=y0 or (x1-x0)<.005 or (y1-y0)<.005:
        raise ValueError('DEGENERATE_CROP_RECT')
    return [x0,y0,x1,y1]

def landmarks(points):
    if not isinstance(points, dict) or len(points)==0 or len(points)>256:
        raise ValueError('INVALID_LANDMARK_SET')
    out={}
    for name, coord in points.items():
        if not isinstance(name,str) or not NAME.fullmatch(name):
            raise ValueError('INVALID_LANDMARK_NAME')
        if not isinstance(coord,list) or len(coord)!=2:
            raise ValueError('INVALID_LANDMARK_COORD')
        out[name]=[finite(value,0,1) for value in coord]
    return out

def landmark_error(reference, projected):
    a,b=landmarks(reference),landmarks(projected)
    if set(a)!=set(b):raise ValueError('LANDMARKS_MISMATCH')
    squared=[(a[k][0]-b[k][0])**2+(a[k][1]-b[k][1])**2 for k in sorted(a)]
    score=math.sqrt(sum(squared)/len(squared))
    return {'landmarks':len(a),'rms_normalized_image_error':score,
            'max_normalized_image_error':math.sqrt(max(squared)),
            'visual_likeness_verified':False,
            'identity_verified':False,
            'metric':'2D landmark projection distance, not image similarity or facial identity',
            'likeness_percent_available':False}

def clip_plan(radius, distance):
    radius=finite(radius,.0000001,1e9)
    distance=finite(distance,.0000001,1e9)
    far=max(distance+2*radius, distance*1.25)
    near=max(1e-6, min(distance/64.0,radius/8.0),far/85000.0)
    return {'clip_start':near,'clip_end':far,'precision_ratio':far/near,
            'scene_radius':radius,'view_distance':distance,
            'render_settings_changed':False,'geometry_decimated':False,
            'viewport_only':True,'hardware_depth_artifacts_verified_fixed':False}

def render_complete(start,end,next_frame):
    for x in (start,end,next_frame):
        if type(x) is not int or x<1 or x>10_000_000:raise ValueError('INVALID_RENDER_FRAME')
    if end<start:raise ValueError('INVALID_RENDER_RANGE')
    return next_frame>end

def first_missing_frame(start,end,available):
    if type(start) is not int or type(end) is not int or start<1 or end<start:
        raise ValueError('INVALID_RENDER_RANGE')
    valid=set(available)
    for f in range(start,end+1):
        if f not in valid:return f
    return end+1

def long_render_plan(seconds,fps=24,width=1920,height=1080):
    seconds=finite(seconds,1,7200)
    if type(fps) is not int or not 1<=fps<=120:raise ValueError('INVALID_FPS')
    if type(width) is not int or type(height) is not int or width<16 or height<16:raise ValueError('INVALID_DIMENSIONS')
    frames=int(math.ceil(seconds*fps))
    return {'seconds':seconds,'fps':fps,'frames':frames,'width':width,'height':height,
            'minimum_uncompressed_rgba_bytes':frames*width*height*4,
            'estimated_wall_seconds':None,'phone_hardware_verified':False,
            'batch_resume_required':True,'quality_reduced':False}

def reference_provenance(asset_hash, view, unseen_known=False):
    asset_name(asset_hash,'png')
    if view not in ('front','back','left','right','three_quarter','other'):
        raise ValueError('INVALID_REFERENCE_VIEW')
    if type(unseen_known) is not bool:raise ValueError('INVALID_VISIBILITY')
    return {'source_hash':asset_hash,'reference_view':view,
            'unseen_geometry':'observed' if unseen_known else 'inferred',
            'automatic_reconstruction':False,
            'exact_likeness_verified':False}
