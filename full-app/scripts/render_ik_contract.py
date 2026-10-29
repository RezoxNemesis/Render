# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure, versioned validation of native Blender IK/FK rig and control actions.

No owner paths, remote bpy expressions, Python console access or fake physics.
"""
import math
import re

NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
SHA=re.compile(r"^[a-f0-9]{64}$")
OPS=frozenset(("studio.ik.create","studio.ik.inspect",
               "studio.ik.target","studio.ik.blend"))
MUTATE=OPS-{"studio.ik.inspect"}

def fields(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_IK_FIELDS_INVALID")
    return p

def name(x):
    if not isinstance(x,str) or not NAME.fullmatch(x):
        raise ValueError("STUDIO_IK_NAME_INVALID")
    return x

def number(x,lo,hi):
    if type(x) not in (int,float) or not math.isfinite(x) or not lo<=x<=hi:
        raise ValueError("STUDIO_IK_NUMBER_INVALID")
    return float(x)

def integer(x,lo=1,hi=100000):
    if type(x) is not int or not lo<=x<=hi:
        raise ValueError("STUDIO_IK_INTEGER_INVALID")
    return x

def vec(x,lo=-100000,hi=100000):
    if not isinstance(x,list) or len(x)!=3:raise ValueError("STUDIO_IK_VECTOR_INVALID")
    return [number(v,lo,hi) for v in x]

def check(op,p):
    if op=="studio.ik.create":
        fields(p,("rig","bone","controller","chain_length",
                  "influence","pole","pole_offset","pole_angle","dry_run"),
                  ("rig","bone","controller"))
        name(p["rig"]);name(p["bone"]);name(p["controller"])
        integer(p.get("chain_length",2),2,8)
        number(p.get("influence",1),0,1)
        pole=p.get("pole")
        if pole is not None:
            name(pole)
            if pole==p["controller"]:raise ValueError("STUDIO_IK_DUPLICATE_CONTROL")
        if "pole_offset" in p:
            if pole is None:raise ValueError("STUDIO_IK_POLE_REQUIRED")
            vec(p["pole_offset"],-1000,1000)
        if "pole_angle" in p:
            if pole is None:raise ValueError("STUDIO_IK_POLE_REQUIRED")
            number(p["pole_angle"],-math.pi,math.pi)
        if type(p.get("dry_run",False)) is not bool:
            raise ValueError("STUDIO_IK_DRY_RUN_INVALID")
        return p
    if op=="studio.ik.inspect":
        fields(p,("rig","bone","frame"),("rig",))
        name(p["rig"])
        if "bone" in p:name(p["bone"])
        if "frame" in p:integer(p["frame"])
        return p
    if op=="studio.ik.target":
        fields(p,("rig","bone","frame","location_world",
                  "control","expected_sha256","dry_run","allow_existing_action",
                  "preview_frame"),
                  ("rig","bone","frame","location_world","expected_sha256"))
        name(p["rig"]);name(p["bone"]);integer(p["frame"])
        vec(p["location_world"],-1e6,1e6)
        if p.get("control","TARGET") not in ("TARGET","POLE"):
            raise ValueError("STUDIO_IK_CONTROL_INVALID")
    elif op=="studio.ik.blend":
        fields(p,("rig","bone","frame","influence","expected_sha256",
                  "dry_run","allow_existing_action","preview_frame"),
                  ("rig","bone","frame","influence","expected_sha256"))
        name(p["rig"]);name(p["bone"]);integer(p["frame"])
        number(p["influence"],0,1)
    else:raise ValueError("STUDIO_IK_OPERATION_UNAVAILABLE")
    if not isinstance(p["expected_sha256"],str) or not SHA.fullmatch(p["expected_sha256"]):
        raise ValueError("STUDIO_IK_REVISION_INVALID")
    for x in ("dry_run","allow_existing_action","preview_frame"):
        if type(p.get(x,True if x=="preview_frame" else False)) is not bool:
            raise ValueError("STUDIO_IK_BOOLEAN_INVALID")
    return p

def capabilities():
    ident={"type":"string","pattern":NAME.pattern}
    number_schema={"type":"number"}
    vector={"type":"array","minItems":3,"maxItems":3,
            "items":{"type":"number"}}
    base={"rig":ident,"bone":ident,
          "controller":ident,"chain_length":{"type":"integer","minimum":2,"maximum":8},
          "influence":{"type":"number","minimum":0,"maximum":1},
          "pole":ident,"pole_offset":vector,
          "pole_angle":{"type":"number","minimum":-math.pi,"maximum":math.pi},
          "dry_run":{"type":"boolean"},"control":{"enum":["TARGET","POLE"]},
          "location_world":vector,
          "frame":{"type":"integer","minimum":1,"maximum":100000},
          "expected_sha256":{"type":"string","pattern":SHA.pattern},
          "allow_existing_action":{"type":"boolean"},"preview_frame":{"type":"boolean"}}
    configs=(
       ("studio.ik.create",False,("rig","bone","controller"),
        ("rig","bone","controller","chain_length","influence",
         "pole","pole_offset","pole_angle","dry_run")),
       ("studio.ik.inspect",True,("rig",),("rig","bone","frame")),
       ("studio.ik.target",False,("rig","bone","frame","location_world","expected_sha256"),
        ("rig","bone","frame","location_world","control","expected_sha256","dry_run",
         "allow_existing_action","preview_frame")),
       ("studio.ik.blend",False,("rig","bone","frame","influence","expected_sha256"),
        ("rig","bone","frame","influence","expected_sha256",
         "dry_run","allow_existing_action","preview_frame")),
    )
    return [
      {"operation":op,"workspace":"characters" if op!="studio.ik.blend" else "animation",
       "read_only":readonly,"checkpoint_before_change":not readonly,
       "native_blender_constraint_required":True,
       "input_schema":{"type":"object","additionalProperties":False,
                       "required":list(required),
                       "properties":{k:base[k] for k in allowed}}}
      for op,readonly,required,allowed in configs]
