# SPDX-License-Identifier: GPL-2.0-or-later
"""ChatGPT fast lane in the real Blender bpy executor.

One authenticated call for capability + scene + queue discovery; bounded
read-only batches. It NEVER mutates scene objects, runs arbitrary scripts or
starts competing worker threads. Render's original production.execute is
still the sole native owner.
"""
from collections import deque
import hashlib
import json
import os
import time
import uuid

import bpy
import render_agent_fastlane_contract as Contract
import render_unified_contract as C

_TIMES=deque(maxlen=64)

def _spool():
    spool=os.environ.get("RENDER_AGENT_SPOOL")
    if not spool:
        raise RuntimeError("STUDIO_PRIVATE_SPOOL_UNAVAILABLE")
    return spool

def _manifest():
    import render_production_contract as P
    # Version-digest isn't a data or auth token; it is just an optimization
    # hint for clients to avoid repeatedly requesting unmodified schemas.
    manifest={"contract":Contract.VERSION,
              "blender_version":bpy.app.version_string,
              "native_ops":sorted(P.OPERATIONS),
              "workspaces":[x[0] for x in C.WORKSPACES]}
    raw=json.dumps(manifest,sort_keys=True,separators=(",",":")).encode("ascii")
    return hashlib.sha256(raw).hexdigest()

def _native_status(scene):
    return {"scene":scene.name,"objects":len(scene.objects),
            "frame":int(scene.frame_current),"engine":scene.render.engine,
            "selected_object":getattr(bpy.context.active_object,"name",None),
            "mode":bpy.context.mode,
            "native_blender_heartbeat_proven_by_this_execution":True}

def _measure(label,start,success=True):
    dt=round(max(0,(time.perf_counter_ns()-start)/1_000_000),3)
    _TIMES.append({"category":label,"elapsed_ms":dt,"succeeded":bool(success)})
    return dt

def bootstrap(p,root,scene):
    Contract.bootstrap(p)
    import render_unified_workspace as Studio
    digest=_manifest()
    unchanged=p.get("known_manifest_sha256")==digest
    started=time.perf_counter_ns()
    result={
        "contract":Contract.VERSION,
        "manifest_sha256":digest,
        "manifest_unchanged":unchanged,
        "full_tool_manifest_transferred":not unchanged,
        "current_workspace":Studio._section(scene),
        "scene":_native_status(scene) if p.get("include_scene",False) else None,
        "queue":Studio.Q.list_jobs(root) if p.get("include_queue",False) else None,
        "source":"current actual Blender process",
        "remote_eval_enabled":False,
        "same_call_can_create_objects":False,
        "recommended_next_operations":[
            "studio.command.catalog","studio.command.preview","studio.create.catalog",
            "studio.agent.batch.inspect","studio.agent.plan.preview",
            "studio.tool.search","studio.plan.submit"]
    }
    if not unchanged:
        result["workspaces"]=C.catalog(active=Studio._section(scene))["workspaces"]
        result["max_inspects_per_batch"]=Contract.MAX_READS
        result["max_queued_work_plans"]=4
        result["serialized_bpy_writes"]=True
        result["direct_physical_screen_touches"]=False
        result["force_stop_continuation_guaranteed"]=False
    if p.get("query"):
        query={"query":p["query"],"limit":p.get("limit",8)}
        if p.get("workspace"):query["workspace"]=p["workspace"]
        result["tool_search"]=Studio._tool_search(query)
    result["native_elapsed_ms"]=_measure("bootstrap",started)
    Contract._bounded_json(result,Contract.MAX_REPLY_BYTES)
    return result

def batch_inspect(p,root,scene):
    reads=Contract.batch(p)
    start=time.perf_counter_ns()
    results=[]
    import render_production
    for item in reads:
        op=item["operation"]
        t=time.perf_counter_ns()
        try:
            # Validate against the same native production allowlist. No CLI,
            # no shell, no parallel bpy readers and NO write-capable ops.
            result=render_production.execute(
                {"operation":op,"payload":item["payload"]},
                _spool(),uuid.uuid4().hex)
            entry={"operation":op,"state":"succeeded","result":result}
            success=True
        except Exception as exc:
            entry={"operation":op,"state":"failed",
                   "error_code":Contract.sanitize_error(exc)}
            success=False
        entry["native_elapsed_ms"]=_measure("read:"+op,t,success)
        results.append(entry)
        # Abort instead of truncating authoritative scan/landmark data.
        Contract._bounded_json({"results":results},Contract.MAX_REPLY_BYTES)
    return {"contract":Contract.VERSION,"results":results,
            "all_succeeded":all(row["state"]=="succeeded" for row in results),
            "reads_succeeded":sum(row["state"]=="succeeded" for row in results),
            "reads_requested":len(reads),
            "native_total_elapsed_ms":_measure("batch",start),
            "scene_modified_by_fastlane":False,
            "execution":"serial_in_existing_bpy_main_thread",
            "network_requests_inside_batch":False}

def plan_preview(p,root,scene):
    import render_unified_workspace as Studio
    started=time.perf_counter_ns()
    value=Contract.preview(p,C.PROGRAM_OPS,C.MUTATING)
    # Queued programs have up to 16 serial steps; actual runtime validates
    # every payload again against its domain-specific native contract.
    value.update({"contract":Contract.VERSION,
                  "preview_only_no_job_created":True,
                  "available_plan_slots":max(0,4-sum(
                      row["state"] in Studio.Q.ACTIVE
                      for row,path in Studio.Q._all(root))),
                  "scene_fingerprint_not_taken":True,
                  "native_elapsed_ms":_measure("preview",started)})
    return value

def metrics(p,root,scene):
    if not isinstance(p,dict) or set(p)-{"limit"}:
        raise ValueError("STUDIO_AGENT_METRICS_ARGUMENTS_INVALID")
    limit=p.get("limit",16)
    if type(limit) is not int or not 1<=limit<=64:
        raise ValueError("STUDIO_AGENT_METRICS_LIMIT_INVALID")
    measurements=list(_TIMES)[-limit:]
    return {"contract":Contract.VERSION,
            "measurements":measurements,
            "measurement_type":"actual_native_execution_not_network_roundtrip",
            "native_sample_count":len(measurements),
            "no_performance_speedup_claim_without_baseline":True,
            "private_scene_payloads_stored":False,
            "engine_or_render_quality_modified":False}

def execute(op,p,root,scene):
    if op=="studio.agent.bootstrap":return bootstrap(p,root,scene)
    if op=="studio.agent.batch.inspect":return batch_inspect(p,root,scene)
    if op=="studio.agent.plan.preview":return plan_preview(p,root,scene)
    if op=="studio.agent.metrics":return metrics(p,root,scene)
    raise ValueError("STUDIO_AGENT_FASTLANE_OPERATION_UNAVAILABLE")

def capabilities():
    return [
      {"operation":"studio.agent.bootstrap","workspace":"agent","read_only":True,
       "input_schema":{"type":"object","additionalProperties":False,
          "properties":{"query":{"type":"string","maxLength":80},
           "workspace":{"type":"string","maxLength":32},
           "limit":{"type":"integer","minimum":1,"maximum":12},
           "known_manifest_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"},
           "include_scene":{"type":"boolean"},"include_queue":{"type":"boolean"}}}},
      {"operation":"studio.agent.batch.inspect","workspace":"agent","read_only":True,
       "input_schema":{"type":"object","additionalProperties":False,
           "required":["reads"],"properties":{"reads":{
             "type":"array","minItems":1,"maxItems":Contract.MAX_READS,
             "items":{"type":"object","additionalProperties":False,
               "required":["operation","payload"],
               "properties":{"operation":{"enum":sorted(Contract.READS)},
                             "payload":{"type":"object"}}}}}}},
      {"operation":"studio.agent.plan.preview","workspace":"agent","read_only":True,
       "input_schema":{"type":"object","required":["steps"],
           "additionalProperties":False,"properties":{
             "name":{"type":"string"},"plan_id":{"type":"string"},
             "steps":{"type":"array","minItems":1,"maxItems":16},
             "available_memory_bytes":{"type":"integer","minimum":0}}}},
      {"operation":"studio.agent.metrics","workspace":"agent","read_only":True,
       "input_schema":{"type":"object","additionalProperties":False,
           "properties":{"limit":{"type":"integer","minimum":1,"maximum":64}}}}
    ]
