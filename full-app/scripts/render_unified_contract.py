# SPDX-License-Identifier: GPL-2.0-or-later
"""Stable, discoverable discipline contracts for the native Blender UI/agent.

A "workspace" is a set of existing, capability-probed Blender tools, NOT a
copy of any proprietary desktop application. This module has no bpy dependency
and can be tested before starting the Android renderer.
"""
import hashlib
import json
import re

VERSION="render.studio.unified.v1"
ID=re.compile(r"^[a-f0-9]{32}$")
NAME=re.compile(r"^[A-Za-z][A-Za-z0-9 _.-]{0,63}$")

# These are user-facing *disciplines*, not claims of installed proprietary IP.
WORKSPACES=(
 ("sculpt","Sculpt & Anatomy","SCULPT","ZBrush-style detail","VIEW_3D"),
 ("characters","Characters & Rig","OBJECT","Maya / MetaHuman-style production","VIEW_3D"),
 ("animation","Animation & Motion","POSE","Cascadeur / Maya-style keying","DOPESHEET_EDITOR"),
 ("cinema","Cinema & Lighting","OBJECT","Unreal-style shot direction","VIEW_3D"),
 ("simulation","Procedural & Physics","OBJECT","Houdini-style workflows","NODE_EDITOR"),
 ("materials","Materials & Paint","TEXTURE_PAINT","Substance-style look development","NODE_EDITOR"),
 ("drawing","2D & Story","PAINT_GPENCIL","Toon Boom / Grease Pencil-style work","DOPESHEET_EDITOR"),
 ("assets","Assets & References","OBJECT","Poly Haven / ambientCG workflows","FILE_BROWSER"),
 ("agent","Agent & Jobs","OBJECT","Auditable ChatGPT control","VIEW_3D"),
)

# Only exact existing approved production actions are allowed in an agent
# multi-step plan. No arbitrary source code, bpy expression or file paths.
PROGRAM_OPS={
 "scene.inspect":"agent",
 "mesh.create":"sculpt",
 "material.assign":"materials",
 "body.blockout":"characters",
 "rig.create":"characters",
 "rig.keys":"animation",
 "animation.keys":"animation",
 "animation.clip.create":"animation",
 "animation.clip.inspect":"animation",
 "animation.motion.audit":"animation",
 "studio.curve.inspect":"animation",
 "studio.curve.adjust":"animation",
 "reference.workspace.open":"assets",
 "reference.workspace.inspect":"assets",
 "reference.compare.multiview":"characters",
 "reference.fit.landmarks":"characters",
 "reference.fit.multiview":"characters",
 "camera.aim":"cinema",
 "world.configure":"cinema",
 "render.profile.inspect":"cinema",
 "render.quality.inspect":"cinema",
 "project.checkpoint":"agent",
 "studio.workspace.activate":"agent",
 "studio.view.orbit":"sculpt",
 "studio.sculpt.inspect":"sculpt",
 "studio.sculpt.brush":"sculpt",
 "studio.pose.inspect":"characters",
 "studio.pose.key":"animation",
 "studio.timeline.scrub":"animation",
}
MUTATING=frozenset(PROGRAM_OPS)-{
 "scene.inspect","animation.clip.inspect","animation.motion.audit",
 "reference.workspace.inspect","reference.compare.multiview",
 "render.profile.inspect","render.quality.inspect"
}
READ_ONLY=frozenset(PROGRAM_OPS)-MUTATING

# Runtime native Python/Bpy discovery is separate from this catalog. The names
# below are surface hints, not "fully implemented ZBrush/Maya" declarations.
WORKSPACE_HINTS={
 "sculpt":("Sculpt Mode","Voxel Remesh","Mirror","Multiresolution"),
 "characters":("Armatures","Weight Paint","Shape Keys","Reference Fit"),
 "animation":("Action Editor","Graph Editor","NLA","Keyframes","Motion Audit"),
 "cinema":("Cameras","Lights","Compositor","Render Jobs"),
 "simulation":("Geometry Nodes","Rigid Body","Cloth","Particles"),
 "materials":("Shader Editor","UV Editing","Texture Paint","PBR"),
 "drawing":("Grease Pencil","2D Camera","Dope Sheet","Onion Skin"),
 "assets":("Asset Browser","Reference Media","CC0 Catalog","Downloads"),
 "agent":("Plan Queue","Live Native Action","Recovery Ledger","Scene Checkpoint"),
}

def plan(request):
    if not isinstance(request,dict) or set(request)-{"plan_id","name","steps"} or "steps" not in request:
        raise ValueError("STUDIO_PLAN_ENVELOPE_INVALID")
    plan_id=request.get("plan_id")
    if plan_id is not None and (not isinstance(plan_id,str) or not ID.fullmatch(plan_id)):
        raise ValueError("STUDIO_PLAN_ID_INVALID")
    name=request.get("name","Artist Work")
    if not isinstance(name,str) or not NAME.fullmatch(name):
        raise ValueError("STUDIO_PLAN_NAME_INVALID")
    steps=request["steps"]
    if not isinstance(steps,list) or not 1<=len(steps)<=16:
        raise ValueError("STUDIO_PLAN_STEP_COUNT_INVALID")
    clean=[]
    for step in steps:
        if not isinstance(step,dict) or set(step)!={"operation","payload"}:
            raise ValueError("STUDIO_PLAN_STEP_FIELDS_INVALID")
        op=step["operation"];p=step["payload"]
        if type(op) is not str or op not in PROGRAM_OPS or not isinstance(p,dict):
            raise ValueError("STUDIO_PLAN_OPERATION_UNAVAILABLE")
        clean.append({"operation":op,"payload":p})
    output={"name":name,"steps":clean}
    try:
        raw=json.dumps(output,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
    except (ValueError,TypeError,RecursionError) as exc:
        raise ValueError("STUDIO_PLAN_JSON_INVALID") from exc
    if len(raw)>65536:raise ValueError("STUDIO_PLAN_PAYLOAD_TOO_LARGE")
    output["fingerprint"]=hashlib.sha256(raw).hexdigest()
    if plan_id is not None:output["plan_id"]=plan_id
    return output

def catalog(active=None,available=None):
    allowed=set(available) if available is not None else set(PROGRAM_OPS)
    rows=[]
    for ident,label,mode,inspired,editor in WORKSPACES:
        enabled=[op for op,group in PROGRAM_OPS.items() if group==ident and op in allowed]
        rows.append({"id":ident,"label":label,"ui_category":"RS "+label.split(" & ")[0],
                     "inspiration":inspired,"default_editor":editor,
                     "native_mode_hint":mode,"actual_native_tools_must_be_probed":True,
                     "verified_agent_operations":enabled,
                     "possible_native_functions":list(WORKSPACE_HINTS[ident]),
                     "vendor_software_installed":False,
                     "feature_parity_claimed":False})
    return {"contract":VERSION,"workspaces":rows,"active_workspace":active,
            "serialization":"one bpy scene edit per main-thread timer tick",
            "queued_multitask_plans_max":4,"steps_per_plan_max":16,
            "concurrent_scene_edits":False,
            "background_render_requires_android_foreground_service":True,
            "continuous_execution_after_force_stop_guaranteed":False}

def public(record):
    if not isinstance(record,dict):raise ValueError("STUDIO_PLAN_STATE_CORRUPT")
    count=len(record.get("steps",[]))
    done=record.get("next",0)
    if type(done) is not int or not 0<=done<=count:
        raise ValueError("STUDIO_PLAN_PROGRESS_CORRUPT")
    return {"plan_id":record["plan_id"],"name":record["name"],
            "state":record.get("state","unknown"),"completed_steps":done,
            "total_steps":count,"fraction":done/count if count else 0,
            "last_action":record.get("last_action",None),
            "last_workspace":record.get("last_workspace",None),
            "updated_epoch_ms":record.get("updated_epoch_ms",0),
            "requires_manual_review":record.get("state")=="needs_review",
            "results":[{"index":x.get("index"),"operation":x.get("operation"),
                        "state":x.get("state")} for x in record.get("receipts",[])[-16:]]}
