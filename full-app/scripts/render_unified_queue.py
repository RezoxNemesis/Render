# SPDX-License-Identifier: GPL-2.0-or-later
"""Crash-conscious multi-plan queue, one REAL Blender bpy step per timer tick.

Importable/testable on hosts without Blender. No thread ever mutates bpy.
A started step with no receipt is NEVER replayed on process recovery.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import uuid
import render_unified_contract as C

ACTIVE=frozenset(("queued","running","paused","needs_review"))
TERMINAL=frozenset(("completed","cancelled"))
MAX_FILE=100000
MAX_PLANS=4

def _directory(root):
    root=Path(root)
    if root.is_symlink():raise ValueError("STUDIO_STORAGE_SYMLINK")
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    folder=root/"StudioPlans"
    if folder.is_symlink():raise ValueError("STUDIO_QUEUE_SYMLINK")
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not folder.is_dir():raise ValueError("STUDIO_QUEUE_NOT_DIRECTORY")
    return folder

def _path(root,id):
    if type(id) is not str or not C.ID.fullmatch(id):
        raise ValueError("STUDIO_PLAN_ID_INVALID")
    p=_directory(root)/(id+".json")
    if p.is_symlink():raise ValueError("STUDIO_PLAN_SYMLINK")
    return p

def _load_file(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_FILE:
        raise ValueError("STUDIO_PLAN_RECEIPT_CORRUPT")
    try:data=json.loads(path.read_bytes().decode("utf8"))
    except (OSError,ValueError,UnicodeError) as err:
        raise ValueError("STUDIO_PLAN_RECEIPT_CORRUPT") from err
    if not isinstance(data,dict) or data.get("plan_id")!=path.stem:
        raise ValueError("STUDIO_PLAN_ID_CONFLICT")
    if data.get("state") not in (*ACTIVE,*TERMINAL):
        raise ValueError("STUDIO_PLAN_STATE_CORRUPT")
    if C.plan({"name":data.get("name"),"steps":data.get("steps")}).get("fingerprint")!=data.get("fingerprint"):
        raise ValueError("STUDIO_PLAN_REVISION_CONFLICT")
    C.public(data)
    return data

def _save(path,value):
    data=json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf8")
    if len(data)>MAX_FILE:raise ValueError("STUDIO_PLAN_RECEIPT_OVERSIZE")
    temporary=path.with_name(path.stem+".writing")
    if temporary.is_symlink():raise ValueError("STUDIO_PLAN_TEMP_SYMLINK")
    try:
        fd=os.open(str(temporary),os.O_WRONLY|os.O_CREAT|os.O_TRUNC|getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
        dfd=os.open(str(path.parent),os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:
        if temporary.exists():temporary.unlink()

def _all(root):
    folder=_directory(root)
    entries=[]
    for path in sorted(folder.glob("*.json")):
        if not C.ID.fullmatch(path.stem) or path.is_symlink():continue
        entries.append((_load_file(path),path))
    return entries

def submit(root,request):
    clean=C.plan(request)
    plan_id=clean.get("plan_id") or uuid.uuid4().hex
    path=_path(root,plan_id)
    if path.exists():
        existing=_load_file(path)
        if existing["fingerprint"]!=clean["fingerprint"]:
            raise ValueError("STUDIO_PLAN_REPLAY_PAYLOAD_CONFLICT")
        return dict(C.public(existing),idempotent=True)
    active=[row for row,p in _all(root) if row["state"] in ACTIVE]
    if len(active)>=MAX_PLANS:raise ValueError("STUDIO_PLAN_QUEUE_FULL")
    rec=dict(clean,plan_id=plan_id,state="queued",next=0,receipts=[],
             started_step=None,last_action=None,last_workspace=None,
             updated_epoch_ms=int(time.time()*1000))
    _save(path,rec)
    return dict(C.public(rec),idempotent=False)

def get(root,plan_id):
    return C.public(_load_file(_path(root,plan_id)))

def list_jobs(root):
    rows=sorted((row for row,path in _all(root)),
                key=lambda x:x.get("updated_epoch_ms",0),reverse=True)
    return {"jobs":[C.public(row) for row in rows[:32]],
            "pending":sum(1 for r in rows if r["state"]=="queued"),
            "needs_review":sum(1 for r in rows if r["state"]=="needs_review"),
            "serialized_native_bpy_actions":True,
            "parallel_native_scene_edits_supported":False,
            "running_after_android_force_stop_guaranteed":False}

def _update(root,plan_id,accept,result):
    path=_path(root,plan_id);row=_load_file(path)
    if row["state"] not in accept:raise ValueError("STUDIO_PLAN_STATE_CONFLICT")
    row["state"]=result
    row["updated_epoch_ms"]=int(time.time()*1000)
    _save(path,row)
    return C.public(row)

def pause(root,plan_id):
    return _update(root,plan_id,{"queued"},"paused")

def resume(root,plan_id):
    path=_path(root,plan_id);row=_load_file(path)
    if row["state"]!="paused" or row.get("started_step") is not None:
        raise ValueError("STUDIO_PLAN_REQUIRES_INSPECTION")
    return _update(root,plan_id,{"paused"},"queued")

def cancel(root,plan_id):
    return _update(root,plan_id,{"queued","paused","needs_review"},"cancelled")

def recover(root):
    changed=0
    for row,path in _all(root):
        if row["state"]=="running":
            # A step may have mutated Blender, but no receipt was committed:
            # its outcome must be inspected by the owner before any new work.
            row["state"]="needs_review"
            row["updated_epoch_ms"]=int(time.time()*1000)
            _save(path,row);changed+=1
    return {"interrupted_steps_marked_needs_review":changed,
            "automatic_replay":False}

def tick(root,executor,on_start=None,on_finish=None,render_busy=False):
    if render_busy:
        return {"executed_steps":0,"blocked":"NATIVE_RENDER_IN_PROGRESS"}
    candidates=[(row,path) for row,path in _all(root) if row["state"]=="queued"]
    if not candidates:return {"executed_steps":0,"blocked":"NO_QUEUED_NATIVE_WORK"}
    candidates.sort(key=lambda item:(item[0]["updated_epoch_ms"],item[0]["plan_id"]))
    row,path=candidates[0]
    idx=row["next"]
    step=row["steps"][idx]
    op=step["operation"]
    row["state"]="running"
    row["started_step"]=idx
    row["last_action"]=op
    row["last_workspace"]=C.PROGRAM_OPS[op]
    row["updated_epoch_ms"]=int(time.time()*1000)
    _save(path,row)    # Crash barrier: NEVER execute before this fsync
    if on_start is not None:
        try:on_start(row["plan_id"],idx,op)
        except Exception:pass
    try:
        result=executor(op,step["payload"],row["plan_id"])
        if isinstance(result,dict) and (result.get("paused") or result.get("recovery_required")):
            raise RuntimeError("NATIVE_STEP_REQUIRES_MANUAL_REVIEW")
        # A receipt only counts when native execution truly returned success.
        digest=hashlib.sha256(json.dumps(result,sort_keys=True,default=str,
                        allow_nan=False).encode("utf8")).hexdigest()
        receipt={"index":idx,"operation":op,"state":"succeeded",
                 "result_sha256":digest}
        # Preserve only this validated local mesh revision for the immediately
        # following brush in the SAME plan. Not a generic variable evaluator.
        if op=="studio.sculpt.brush" and isinstance(result,dict):
            obj=result.get("object");rev=result.get("mesh_revision_after")
            if type(obj) is str and 1<=len(obj)<=80 and type(rev) is str and (
                    len(rev)==64 and all(ch in "0123456789abcdef" for ch in rev)):
                receipt["object"]=obj
                receipt["mesh_revision_after"]=rev
        row["receipts"].append(receipt)
        row["next"]=idx+1
        row["state"]="completed" if row["next"]==len(row["steps"]) else "queued"
        row["started_step"]=None
        row["updated_epoch_ms"]=int(time.time()*1000)
        _save(path,row)
        if on_finish is not None:
            try:on_finish(row["plan_id"],idx,op,"succeeded",result)
            except Exception:pass
        return {"executed_steps":1,"result":"succeeded","job":C.public(row)}
    except Exception as exc:
        # No implicit retry/rollback of a side-effectful object edit.
        row["receipts"].append({"index":idx,"operation":op,"state":"needs_review",
                                "error_type":type(exc).__name__})
        row["state"]="needs_review"
        row["updated_epoch_ms"]=int(time.time()*1000)
        _save(path,row)
        if on_finish is not None:
            try:on_finish(row["plan_id"],idx,op,"failed",None)
            except Exception:pass
        return {"executed_steps":1,"result":"needs_review",
                "job":C.public(row),"error_code":"NATIVE_STEP_REQUIRES_INSPECTION"}
