# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure validation for bounded reference comparison and native Blender motion.

All paths are owned SHA-named files, not user-supplied Android or Gallery paths.
Every operation rejects unknown keys and arbitrary Python/operator execution.
"""
import math
import re

NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
ASSET=re.compile(r"^[a-f0-9]{64}\.(?:png|jpg|jpeg|webp|mp4)$")
INTERPOLATIONS=frozenset(("BEZIER","LINEAR","CONSTANT"))

def fields(value, allowed, required=()):
    if not isinstance(value,dict) or set(value)-set(allowed) or not set(required)<=set(value):
        raise ValueError("REFERENCE_MOTION_FIELDS_INVALID")
    return value

def name(value):
    if not isinstance(value,str) or not NAME.fullmatch(value):
        raise ValueError("REFERENCE_MOTION_NAME_INVALID")
    return value

def integer(value,lo=1,hi=100000):
    if type(value) is not int or not lo<=value<=hi:
        raise ValueError("REFERENCE_MOTION_INTEGER_INVALID")
    return value

def number(value,lo,hi):
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError("REFERENCE_MOTION_NUMBER_INVALID")
    return float(value)

def vec(value,size,lo=-100000,hi=100000):
    if not isinstance(value,list) or len(value)!=size:
        raise ValueError("REFERENCE_MOTION_VECTOR_INVALID")
    return [number(x,lo,hi) for x in value]

def workspace(p):
    fields(p,("asset","preview_asset","mode","split_factor","frame","model","reference_name"),("asset",))
    if not isinstance(p["asset"],str) or not ASSET.fullmatch(p["asset"]):
        raise ValueError("REFERENCE_ASSET_ID_INVALID")
    if "preview_asset" in p:
        preview=p["preview_asset"]
        if (not isinstance(preview,str) or not ASSET.fullmatch(preview) or
                preview.endswith(".mp4") or not p["asset"].endswith(".mp4")):
            raise ValueError("VIDEO_REFERENCE_PREVIEW_INVALID")
    mode=p.get("mode","SPLIT")
    if mode not in ("SPLIT","REUSE","CAMERA"):raise ValueError("REFERENCE_MODE_INVALID")
    if "model" in p:name(p["model"])
    if "reference_name" in p:name(p["reference_name"])
    if "frame" in p:integer(p["frame"])
    factor=number(p.get("split_factor",.52),.3,.7)
    return dict(p,mode=mode,split_factor=factor)

def multiview(p):
    fields(p,("object","views"),("object","views"))
    name(p["object"])
    views=p["views"]
    if not isinstance(views,list) or not 1<=len(views)<=6:
        raise ValueError("REFERENCE_VIEWS_INVALID")
    known=set()
    for view in views:
        fields(view,("camera","label","reference","model"),("camera","reference","model"))
        name(view["camera"])
        if "label" in view:name(view["label"])
        if view["camera"] in known:raise ValueError("REFERENCE_CAMERA_DUPLICATED")
        known.add(view["camera"])
        points=view["reference"];indices=view["model"]
        if not isinstance(points,dict) or not 2<=len(points)<=128 or not isinstance(indices,dict) or set(points)!=set(indices):
            raise ValueError("REFERENCE_LANDMARKS_INVALID")
        for key,xy in points.items():
            name(key);vec(xy,2,0,1)
            integer(indices[key],0,99999999)
    return p

def clip(p):
    fields(p,("rig","name","poses","interpolation","nla","track"),("rig","name","poses"))
    name(p["rig"]);name(p["name"])
    interp=p.get("interpolation","BEZIER")
    if interp not in INTERPOLATIONS:raise ValueError("MOTION_INTERPOLATION_INVALID")
    if type(p.get("nla",False)) is not bool:raise ValueError("MOTION_NLA_INVALID")
    if "track" in p:name(p["track"])
    poses=p["poses"]
    if not isinstance(poses,list) or not 2<=len(poses)<=96:
        raise ValueError("MOTION_POSES_INVALID")
    last=0;total=0;bone_channels=0
    for pose in poses:
        fields(pose,("frame","bones","shapes"),("frame",))
        frame=integer(pose["frame"])
        if frame<=last:raise ValueError("MOTION_FRAMES_NOT_ASCENDING")
        last=frame
        bones=pose.get("bones",[]);shapes=pose.get("shapes",[])
        if not isinstance(bones,list) or not isinstance(shapes,list) or len(bones)>64 or len(shapes)>32 or not (bones or shapes):
            raise ValueError("MOTION_CHANNELS_INVALID")
        seen=set()
        for b in bones:
            fields(b,("bone","location","rotation_euler","rotation_quaternion","scale"),("bone",))
            bone=name(b["bone"])
            if bone in seen:raise ValueError("MOTION_DUPLICATE_BONE")
            seen.add(bone)
            channels=set(b)-{"bone"}
            if not channels or {"rotation_euler","rotation_quaternion"}<=channels:raise ValueError("MOTION_BONE_CHANNELS_INVALID")
            if "location" in b:vec(b["location"],3)
            if "rotation_euler" in b:vec(b["rotation_euler"],3,-100,100)
            if "rotation_quaternion" in b:
                q=vec(b["rotation_quaternion"],4,-1,1)
                if not .999<=math.sqrt(sum(x*x for x in q))<=1.001:
                    raise ValueError("MOTION_QUATERNION_NOT_NORMALIZED")
            if "scale" in b:vec(b["scale"],3,.000001,1000)
            total+=len(channels);bone_channels+=len(channels)
        shape_seen=set()
        for shape in shapes:
            fields(shape,("object","key","value"),("object","key","value"))
            ident=(name(shape["object"]),name(shape["key"]))
            if ident in shape_seen:raise ValueError("MOTION_DUPLICATE_SHAPE")
            shape_seen.add(ident)
            number(shape["value"],0,1)
            total+=1
    if bone_channels<1:raise ValueError("MOTION_RIG_REQUIRES_BONE_KEYS")
    if total>8192:raise ValueError("MOTION_KEY_BUDGET_EXCEEDED")
    return p

def audit(p):
    fields(p,("rig","bones","frames"),("rig","bones","frames"))
    name(p["rig"])
    bones=p["bones"];frames=p["frames"]
    if not isinstance(bones,list) or not 1<=len(bones)<=32 or len(set(bones))!=len(bones):
        raise ValueError("MOTION_BONE_SELECTION_INVALID")
    for b in bones:name(b)
    if not isinstance(frames,list) or not 2<=len(frames)<=128:
        raise ValueError("MOTION_AUDIT_FRAMES_INVALID")
    previous=0
    for f in frames:
        integer(f)
        if f<=previous:raise ValueError("MOTION_FRAMES_NOT_ASCENDING")
        previous=f
    return p
