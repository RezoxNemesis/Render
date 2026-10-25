# SPDX-License-Identifier: GPL-2.0-or-later
"""Strict pure input contracts for true Blender viewport diagnostics.

Profiles change ONLY native 3D View shading/overlays/clip planes.
They never alter renderer quality, geometry, materials or project assets.
"""
import hashlib
import json
import math
import re

REV=re.compile(r"^[a-f0-9]{64}$")
NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
PROFILES=(
    "CLEAN_SOLID",       # stable shaded silhouette, no x-ray or wire overlay
    "DETAIL_INSPECT",    # physical geometry, studio light + cavity
    "MATERIAL_REVIEW",   # opt-in expensive actual material shading
    "SURFACE_DEBUG",     # wireframe inspection to locate depth problems
    "LOW_NOISE",         # lightweight shadows/cavity off, solid display
)
OPS=frozenset((
 "studio.preview.capabilities","studio.preview.inspect",
 "studio.preview.diagnose","studio.preview.profile.apply",
 "studio.preview.profile.restore","studio.preview.aa.inspect",
 "studio.preview.aa.configure",
 "studio.preview.sampling.inspect","studio.preview.sampling.configure",
))
READ_ONLY=frozenset((
 "studio.preview.capabilities","studio.preview.inspect",
 "studio.preview.diagnose","studio.preview.aa.inspect",
 "studio.preview.sampling.inspect",
))
MUTATING=OPS-READ_ONLY

def fields(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_PREVIEW_FIELDS_INVALID")
    return p

def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:
        raise ValueError("STUDIO_PREVIEW_INTEGER_INVALID")
    return value

def name(value):
    if not isinstance(value,str) or not NAME.fullmatch(value):
        raise ValueError("STUDIO_PREVIEW_TARGET_INVALID")
    return value

def boolean(value):
    if type(value) is not bool:
        raise ValueError("STUDIO_PREVIEW_BOOLEAN_INVALID")
    return value

def number(value,lo,hi):
    if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError("STUDIO_PREVIEW_NUMBER_INVALID")
    return float(value)

def digest(data):
    try:raw=json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
    except (ValueError,TypeError) as e:raise ValueError("STUDIO_PREVIEW_REVISION_INVALID") from e
    return hashlib.sha256(raw).hexdigest()

def validate(op,p):
    if op=="studio.preview.capabilities":
        return fields(p,())
    if op=="studio.preview.inspect":
        fields(p,("viewport_index",))
    elif op=="studio.preview.diagnose":
        fields(p,("object","viewport_index","max_candidates"))
        if "object" in p:name(p["object"])
        if "max_candidates" in p:integer(p["max_candidates"],8,1024)
    elif op=="studio.preview.profile.apply":
        fields(p,("profile","viewport_index","object","expected_sha256",
                  "allow_expensive_shader_compile","precision_target_clipping"),
               ("profile",))
        if p["profile"] not in PROFILES:
            raise ValueError("STUDIO_PREVIEW_PROFILE_UNKNOWN")
        if "object" in p:name(p["object"])
        if "expected_sha256" in p:
            if type(p["expected_sha256"]) is not str or not REV.fullmatch(p["expected_sha256"]):
                raise ValueError("STUDIO_PREVIEW_REVISION_INVALID")
        for field in ("allow_expensive_shader_compile","precision_target_clipping"):
            if field in p:boolean(p[field])
        if p["profile"]=="MATERIAL_REVIEW" and p.get("allow_expensive_shader_compile") is not True:
            raise ValueError("STUDIO_PREVIEW_MATERIAL_REVIEW_REQUIRES_OPT_IN")
        if p.get("precision_target_clipping") and "object" not in p:
            raise ValueError("STUDIO_PREVIEW_DEPTH_TARGET_REQUIRED")
    elif op=="studio.preview.profile.restore":
        fields(p,("viewport_index","expected_sha256"))
        if "expected_sha256" in p:
            if type(p["expected_sha256"]) is not str or not REV.fullmatch(p["expected_sha256"]):
                raise ValueError("STUDIO_PREVIEW_REVISION_INVALID")
    elif op=="studio.preview.sampling.inspect":
        return fields(p,())
    elif op=="studio.preview.sampling.configure":
        fields(p,("samples","restore","allow_viewport_sample_change",
                  "allow_high_gpu_load"),("allow_viewport_sample_change",))
        boolean(p["allow_viewport_sample_change"])
        if not p["allow_viewport_sample_change"]:
            raise ValueError("STUDIO_PREVIEW_SAMPLING_EXPLICIT_OPT_IN_REQUIRED")
        restoring=boolean(p.get("restore",False))
        heavy=boolean(p.get("allow_high_gpu_load",False))
        if restoring:
            if "samples" in p:raise ValueError("STUDIO_PREVIEW_SAMPLING_RESTORE_CONFLICT")
        else:
            if "samples" not in p:raise ValueError("STUDIO_PREVIEW_SAMPLING_COUNT_REQUIRED")
            integer(p["samples"],1,128)
            if p["samples"]>32 and not heavy:
                raise ValueError("STUDIO_PREVIEW_HIGH_SAMPLES_REQUIRES_OPT_IN")
        return p
    elif op=="studio.preview.aa.inspect":
        return fields(p,())
    elif op=="studio.preview.aa.configure":
        fields(p,("level","allow_global_preferences","restore"),("allow_global_preferences",))
        boolean(p["allow_global_preferences"])
        if p["allow_global_preferences"] is not True:
            raise ValueError("STUDIO_PREVIEW_AA_EXPLICIT_PERMISSION_REQUIRED")
        restore=p.get("restore",False)
        boolean(restore)
        if restore:
            if "level" in p:raise ValueError("STUDIO_PREVIEW_AA_RESTORE_CONFLICT")
        elif p.get("level") not in ("BEST_SUPPORTED","OFF","FXAA","5","8","11","16","32"):
            raise ValueError("STUDIO_PREVIEW_AA_LEVEL_INVALID")
        return p
    else:raise ValueError("STUDIO_PREVIEW_OPERATION_UNAVAILABLE")
    if "viewport_index" in p:integer(p["viewport_index"],0,7)
    return p

def capabilities():
    title={"type":"string","pattern":NAME.pattern}
    index={"type":"integer","minimum":0,"maximum":7}
    revision={"type":"string","pattern":REV.pattern}
    boolean_type={"type":"boolean"}
    attrs={
        "viewport_index":index,"object":title,"expected_sha256":revision,
        "profile":{"enum":list(PROFILES)},
        "max_candidates":{"type":"integer","minimum":8,"maximum":1024},
        "allow_expensive_shader_compile":boolean_type,
        "precision_target_clipping":boolean_type,
        "allow_global_preferences":boolean_type,
        "restore":boolean_type,
        "level":{"enum":["BEST_SUPPORTED","OFF","FXAA","5","8","11","16","32"]},
        "samples":{"type":"integer","minimum":1,"maximum":128},
        "allow_viewport_sample_change":boolean_type,
        "allow_high_gpu_load":boolean_type,
    }
    entries=(
        ("studio.preview.capabilities",True,(),()),
        ("studio.preview.inspect",True,(),("viewport_index",)),
        ("studio.preview.diagnose",True,(),("object","viewport_index","max_candidates")),
        ("studio.preview.profile.apply",False,("profile",),
         ("profile","viewport_index","object","expected_sha256",
          "allow_expensive_shader_compile","precision_target_clipping")),
        ("studio.preview.profile.restore",False,(),("viewport_index","expected_sha256")),
        ("studio.preview.aa.inspect",True,(),()),
        ("studio.preview.aa.configure",False,("allow_global_preferences",),
         ("level","allow_global_preferences","restore")),
        ("studio.preview.sampling.inspect",True,(),()),
        ("studio.preview.sampling.configure",False,("allow_viewport_sample_change",),
         ("samples","restore","allow_viewport_sample_change","allow_high_gpu_load")),
    )
    return [{
       "operation":op,"workspace":"sculpt" if op!="studio.preview.aa.configure" else "agent",
       "read_only":readonly,"preview_only":True,
       "scene_quality_changed":False,"full_geometry_repair_claimed":False,
       "input_schema":{"type":"object","additionalProperties":False,
                       "required":list(required),
                       "properties":{k:attrs[k] for k in allowed}}}
        for op,readonly,required,allowed in entries]
