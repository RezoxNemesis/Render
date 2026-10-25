# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure, bounded agent fast-lane contracts. Never evaluates client code.

One authenticated native IPC replaces several inspect-only round trips.
Scene mutations ALWAYS use the existing checkpointed/serialized path.
"""
import json
import math
import re

VERSION="render.studio.agent.fastlane.v1"
MAX_READS=6
MAX_REPLY_BYTES=65536
MAX_REQUEST_BYTES=32768
MAX_PREVIEW_STEPS=16
HASH=re.compile(r"^[a-f0-9]{64}$")
# Explicit allowlist, not a prefix or a heuristic about command names.
# All implementations are owned by Render's current native bpy source.
READS=frozenset((
    "scene.inspect","artist.inspect","material.inspect",
    "studio.sculpt.inspect","studio.pose.inspect","studio.ik.inspect",
    "studio.curve.inspect","studio.reference.timeline.inspect",
    "studio.workspace.inspect","studio.activity","studio.plan.list",
    "studio.plan.status","render.profile.inspect","render.quality.inspect",
    "animation.clip.inspect","animation.motion.audit",
    "reference.workspace.inspect",
    "studio.preview.capabilities","studio.preview.inspect",
    "studio.preview.diagnose","studio.preview.aa.inspect",
    "studio.character.qa.inspect",
    "studio.preview.sampling.inspect",
))

def _fields(data,allowed,required=()):
    if not isinstance(data,dict) or set(data)-set(allowed) or not set(required)<=set(data):
        raise ValueError("STUDIO_AGENT_FIELDS_INVALID")

def _bounded_json(p,max_size=MAX_REQUEST_BYTES):
    try:
        raw=json.dumps(p,sort_keys=True,separators=(",",":"),
                       ensure_ascii=True,allow_nan=False).encode("utf8")
    except (TypeError,ValueError,RecursionError) as e:
        raise ValueError("STUDIO_AGENT_NONFINITE_OR_UNSERIALIZABLE") from e
    if len(raw)>max_size:raise ValueError("STUDIO_AGENT_PAYLOAD_TOO_LARGE")
    return raw

def batch(p):
    _fields(p,("reads",),("reads",))
    reads=p["reads"]
    if not isinstance(reads,list) or not 1<=len(reads)<=MAX_READS:
        raise ValueError("STUDIO_AGENT_BATCH_SIZE_INVALID")
    result=[]
    for item in reads:
        _fields(item,("operation","payload"),("operation","payload"))
        op=item["operation"]
        if type(op) is not str or op not in READS:
            raise ValueError("STUDIO_AGENT_READ_ONLY_REQUIRED")
        if not isinstance(item["payload"],dict):
            raise ValueError("STUDIO_AGENT_READ_PAYLOAD_INVALID")
        result.append({"operation":op,"payload":item["payload"]})
    _bounded_json(p)
    return result

def bootstrap(p):
    _fields(p,("query","workspace","limit","known_manifest_sha256",
               "include_queue","include_scene"))
    query=p.get("query","")
    if type(query) is not str or len(query)>80:
        raise ValueError("STUDIO_AGENT_QUERY_INVALID")
    work=p.get("workspace")
    if work is not None and (type(work) is not str or len(work)>32):
        raise ValueError("STUDIO_AGENT_WORKSPACE_INVALID")
    limit=p.get("limit",8)
    if type(limit) is not int or not 1<=limit<=12:
        raise ValueError("STUDIO_AGENT_LIMIT_INVALID")
    known=p.get("known_manifest_sha256")
    if known is not None and (type(known) is not str or not HASH.fullmatch(known)):
        raise ValueError("STUDIO_AGENT_MANIFEST_HASH_INVALID")
    for flag in ("include_queue","include_scene"):
        if type(p.get(flag,False)) is not bool:
            raise ValueError("STUDIO_AGENT_FLAG_INVALID")
    _bounded_json(p)
    return p

def preview(p,program_ops,mutating):
    _fields(p,("name","steps","plan_id","available_memory_bytes"),
            ("steps",))
    import render_unified_contract as C
    request={k:v for k,v in p.items() if k in ("name","steps","plan_id")}
    plan=C.plan(request)
    memory=p.get("available_memory_bytes")
    if memory is not None and (type(memory) is not int or not 0<=memory<=2**63-1):
        raise ValueError("STUDIO_AGENT_MEMORY_HINT_INVALID")
    _bounded_json(p)
    operations=[step["operation"] for step in plan["steps"]]
    if any(op not in program_ops for op in operations):
        raise ValueError("STUDIO_AGENT_UNKNOWN_STEP")
    modifications=[op for op in operations if op in mutating]
    return {"plan_fingerprint":plan["fingerprint"],
            "name":plan["name"],"total_steps":len(operations),
            "mutating_steps":len(modifications),"read_only_steps":len(operations)-len(modifications),
            "operations":operations,
            "serial_scene_mutations_required":bool(modifications),
            "automatic_rollback_guaranteed":False,
            "per_operation_payload_preflight_complete":False,
            "native_editor_presence_required":True,
            "queued_plan_will_checkpoint_before_mutation":True,
            "android_frame_render_budget_validated":False,
            "available_memory_bytes_hint":memory,
            "simulation_executed":False}

def rank(query,op,workspace,hints):
    """Deterministic semantic-lite matching with no remote search or embeddings."""
    if type(query) is not str:return 0
    q=query.lower().strip()
    if not q:return 0
    path=op.lower()
    leaf=path.rsplit(".",1)[-1]
    group=(workspace or "").lower()
    synonym={
        "sculpt":"sculpt mesh brush vertex deform anatomy model",
        "characters":"rig character skeleton armature bone actor ik fk human face",
        "animation":"motion keyframe pose interpolation nla graph animate timing",
        "cinema":"camera shot light compositing render movie cinematic",
        "assets":"reference footage source image video import catalog",
        "agent":"agent chatgpt assistant command queue session automation optimize status",
        "simulation":"simulation cloth physics water particle geometry",
        "materials":"texture shader pbr uv paint surface",
        "drawing":"draw pencil 2d toon storyboard",
    }.get(group,"")
    replacements={
      "faster":"speed","fast":"speed","quick":"speed","performance":"speed",
      "bending":"ik","limbs":"ik","foot":"ik","walking":"pose",
      "clip":"animation","acting":"pose","character":"rig",
      "video":"reference","film":"reference",
      "drag":"move","rotate":"transform","zoom":"orbit",
      "automatic":"agent","ai":"agent","tools":"agent",
      "bones":"bone","curve":"graph"}
    tokens=[replacements.get(t,t) for t in re.findall("[a-z0-9_]+",q)]
    stop={"the","a","an","i","me","my","you","can","we","do","and","or",
          "with","that","how","what","where","for","to","in","is","of",
          "use","make","edit","get","please","need","want"}
    meaningful=[x for x in tokens if x not in stop][:12]
    if not meaningful:return 0
    hints=" ".join(hints).lower() if isinstance(hints,(list,tuple)) else str(hints).lower()
    aliases=path+" "+group+" "+synonym+" "+hints
    score=0
    for token in meaningful:
        if token==path:score+=60
        elif token==leaf:score+=38
        elif token in path:score+=20
        elif token==group:score+=17
        elif token in synonym.split():score+=10
        elif token in aliases:score+=5
    return score

def sanitize_error(exc):
    name=type(exc).__name__
    message=str(exc)
    if re.fullmatch("[A-Z_]{3,72}",message):
        return message
    return "STUDIO_AGENT_"+("VALUE_ERROR" if isinstance(exc,ValueError) else
                            "NATIVE_INSPECTION_FAILED")
