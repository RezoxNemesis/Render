# SPDX-License-Identifier: GPL-2.0-or-later
"""Versioned native DCC benchmark contracts and safe typed operations.

External tutorial clips are *acceptance targets*, not licensed assets, data
to scrape, or proof that Render Studio already meets their artistic quality.
No arbitrary bpy Python, shell, filesystem paths or network action.
"""
import math
import re

VERSION="render.studio.external-dcc-benchmarks.v1"
NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
OPS={
 "studio.benchmark.catalog":"agent",
 "studio.benchmark.audit":"agent",
 "studio.mesh.bridge_loops":"sculpt",
 "studio.procedural.scatter":"simulation",
 "studio.material.surface":"materials",
 "studio.motion.action.create":"animation",
 "studio.motion.nla.create":"animation",
 "studio.compositor.grade":"cinema",
 "studio.compositor.inspect":"cinema",
 "studio.sim.rigidbody":"simulation",
 "studio.drawing.strokes":"drawing",
}
READ_ONLY=frozenset({"studio.benchmark.catalog","studio.benchmark.audit",
                    "studio.compositor.inspect"})
BENCHMARKS=(
 ("1000071894.mp4","motion","Obstacle path, anticipation and foot contact","motion.action, motion curves, contact audit"),
 ("1000071896.mp4","animation","Quadruped pose rig, graph curves and NLA","IK/FK, evaluated poses, NLA action strip"),
 ("1000071898.mp4","cinema","Train landscape assembly, sky and animated camera","hierarchy, scatter, camera keyframes"),
 ("1000071903.mp4","simulation","Ruined temple, dense vegetation and reveal","linked scene instances, lighting, camera"),
 ("1000071904.mp4","cinema","Matching WIP, raw render and final color grade","native compositor nodes and before/after"),
 ("1000071905.mp4","assets","Modular architectural asset library workflow","license metadata, linked instancing, transforms"),
 ("1000071906.mp4","simulation","Specialized LiquiGen water solver interoperability","cache import and solver verification (not implemented)"),
 ("1000071923.mp4","sculpt","Character face sculpt, retopo, hair and rig","actual mesh, connected topology, curves, armature"),
 ("1000071924.mp4","sculpt","Bridge selected boundary edge loops","actual bridge quads, winding and normals"),
 ("1000071925.mp4","animation","Rigged boxing punches from two views","editable timed armature actions and camera views"),
)

def name(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError("STUDIO_DCC_NAME_INVALID")
    return value

def real(value,low,high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError("STUDIO_DCC_NUMBER_INVALID")
    return float(value)

def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:
        raise ValueError("STUDIO_DCC_INTEGER_INVALID")
    return value

def vector(v,length=3,low=-1e5,high=1e5):
    if not isinstance(v,list) or len(v)!=length:
        raise ValueError("STUDIO_DCC_VECTOR_INVALID")
    return [real(x,low,high) for x in v]

def fields(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_DCC_FIELDS_INVALID")
    return p

def validate(op,p):
    if op=="studio.benchmark.catalog":
        fields(p,("discipline",))
        if p.get("discipline") is not None and p["discipline"] not in (
                "agent","sculpt","characters","simulation","animation",
                "cinema","assets","materials","drawing"):
            raise ValueError("STUDIO_DCC_DISCIPLINE_INVALID")
        return p
    if op=="studio.benchmark.audit":
        fields(p,("object",))
        if "object" in p:name(p["object"])
        return p
    if op=="studio.mesh.bridge_loops":
        fields(p,("object","loops","expected_vertices","expected_polygons",
                  "dry_run"),("object","loops","expected_vertices","expected_polygons"))
        name(p["object"])
        integer(p["expected_vertices"],6,1000000)
        integer(p["expected_polygons"],1,1000000)
        loops=p["loops"]
        if (not isinstance(loops,list) or len(loops)!=2 or
                not all(isinstance(x,list) and 3<=len(x)<=64 for x in loops) or
                len(loops[0])!=len(loops[1])):
            raise ValueError("STUDIO_DCC_BRIDGE_LOOPS_INVALID")
        seen=[]
        for loop in loops:
            for idx in loop:seen.append(integer(idx,0,p["expected_vertices"]-1))
            if len(set(loop))!=len(loop):
                raise ValueError("STUDIO_DCC_BRIDGE_REPEATED_VERTEX")
        if len(set(seen))!=len(seen):
            raise ValueError("STUDIO_DCC_BRIDGE_LOOPS_OVERLAP")
    elif op=="studio.procedural.scatter":
        fields(p,("source","name","count","seed","min","max","scale_min",
                  "scale_max","yaw_random","dry_run"),
               ("source","name","count","min","max"))
        name(p["source"]);name(p["name"]);integer(p["count"],1,96)
        integer(p.get("seed",0),0,2**31-1)
        lower=vector(p["min"]);upper=vector(p["max"])
        if any(hi<lo for hi,lo in zip(upper,lower)):
            raise ValueError("STUDIO_DCC_SCATTER_BOUNDS_INVALID")
        a=real(p.get("scale_min",.7),.01,5)
        b=real(p.get("scale_max",1.3),.01,5)
        if a>b:raise ValueError("STUDIO_DCC_SCATTER_SCALE_INVALID")
        if type(p.get("yaw_random",True)) is not bool:
            raise ValueError("STUDIO_DCC_SCATTER_YAW_INVALID")
    elif op=="studio.material.surface":
        fields(p,("object","name","preset","color","roughness","detail_scale",
                  "bump","replace_existing","dry_run"),
               ("object","name","preset"))
        name(p["object"]);name(p["name"])
        if p["preset"] not in ("SKIN","LEAF","CLOTH","STONE","METAL"):
            raise ValueError("STUDIO_DCC_MATERIAL_PRESET_INVALID")
        if "color" in p:vector(p["color"],3,0,1)
        real(p.get("roughness",.55),.02,1)
        real(p.get("detail_scale",24),1,256)
        real(p.get("bump",.08),0,.4)
        if type(p.get("replace_existing",False)) is not bool:
            raise ValueError("STUDIO_DCC_REPLACE_INVALID")
    elif op=="studio.motion.action.create":
        fields(p,("rig","bone","name","keys","allow_existing_action","dry_run"),
               ("rig","bone","name","keys"))
        for key in ("rig","bone","name"):name(p[key])
        keys=p["keys"]
        if not isinstance(keys,list) or not 2<=len(keys)<=16:
            raise ValueError("STUDIO_DCC_ACTION_KEYS_INVALID")
        last=0
        for item in keys:
            fields(item,("frame","rotation_euler"),("frame","rotation_euler"))
            frame=integer(item["frame"],1,100000)
            if frame<=last:raise ValueError("STUDIO_DCC_ACTION_FRAMES_NOT_ASCENDING")
            vector(item["rotation_euler"],3,-math.pi*2,math.pi*2)
            last=frame
        if type(p.get("allow_existing_action",False)) is not bool:
            raise ValueError("STUDIO_DCC_ACTION_OVERWRITE_INVALID")
    elif op=="studio.motion.nla.create":
        fields(p,("rig","action","name","frame_start","dry_run"),
               ("rig","action","name","frame_start"))
        for key in ("rig","action","name"):name(p[key])
        integer(p["frame_start"],1,100000)
    elif op=="studio.compositor.grade":
        fields(p,("name","brightness","contrast","saturation","hue",
                  "activate","dry_run"),("name",))
        name(p["name"]);real(p.get("brightness",0),-1,1)
        real(p.get("contrast",0),-1,1)
        real(p.get("saturation",1),0,2)
        real(p.get("hue",.5),0,1)
        if type(p.get("activate",False)) is not bool:
            raise ValueError("STUDIO_DCC_ACTIVATE_INVALID")
    elif op=="studio.compositor.inspect":
        fields(p,())
        return p
    elif op=="studio.sim.rigidbody":
        fields(p,("object","type","mass","friction","bounce","dry_run"),
               ("object",))
        name(p["object"])
        if p.get("type","ACTIVE") not in ("ACTIVE","PASSIVE"):
            raise ValueError("STUDIO_DCC_RIGID_BODY_TYPE_INVALID")
        real(p.get("mass",1),.01,10000)
        real(p.get("friction",.5),0,1)
        real(p.get("bounce",0),0,1)
    elif op=="studio.drawing.strokes":
        fields(p,("name","strokes","z","thickness","color","dry_run"),
               ("name","strokes"))
        name(p["name"])
        strokes=p["strokes"]
        if not isinstance(strokes,list) or not 1<=len(strokes)<=16:
            raise ValueError("STUDIO_DCC_STROKE_COUNT_INVALID")
        total=0
        for stroke in strokes:
            if not isinstance(stroke,list) or not 2<=len(stroke)<=96:
                raise ValueError("STUDIO_DCC_STROKE_LENGTH_INVALID")
            total+=len(stroke)
            for point in stroke:vector(point,2,-10000,10000)
        if total>512:raise ValueError("STUDIO_DCC_STROKE_BUDGET_EXCEEDED")
        real(p.get("z",0),-10000,10000)
        real(p.get("thickness",.006),.0001,.1)
        if "color" in p:vector(p["color"],3,0,1)
    else:raise ValueError("STUDIO_DCC_OPERATION_UNAVAILABLE")
    if type(p.get("dry_run",False)) is not bool:
        raise ValueError("STUDIO_DCC_DRY_RUN_INVALID")
    return p

def capabilities():
    # Deliberately supply bounded native schema hints; runtime validation is
    # stricter and does not trust consumer-authored arbitrary JSON.
    entries=[]
    for op,group in OPS.items():
        entries.append({
          "operation":op,"workspace":group,"read_only":op in READ_ONLY,
          "benchmark_source":"external_desktop_workflows_not_render_app",
          "implemented_as":"editable_native_blender_operation" if op not in READ_ONLY else "actual_native_data_inspection",
          "guarantees_vendor_parity":False,"checkpoint_before_change":op not in READ_ONLY,
          "input_schema":{"type":"object","additionalProperties":False,
               "properties":{
                 "object":{"type":"string","pattern":NAME.pattern},
                 "rig":{"type":"string","pattern":NAME.pattern},
                 "source":{"type":"string","pattern":NAME.pattern},
                 "name":{"type":"string","pattern":NAME.pattern},
                 "preset":{"enum":["SKIN","LEAF","CLOTH","STONE","METAL"]},
                 "count":{"type":"integer","minimum":1,"maximum":96},
                 "dry_run":{"type":"boolean"},
               }},
        })
    return entries
