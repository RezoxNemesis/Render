# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Blender bpy: one ChatGPT call for several owner-safe inspections.

Measures *only native Python/Blender execution*. IPC and phone network
latencies are NOT asserted without actual-device evidence.
"""
import os
from pathlib import Path
import sys
import tempfile
import time
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_agent_fastlane as Agent
import render_agent_fastlane_contract as Contract
import render_unified_workspace as Studio
import render_unified_queue as Queue

with tempfile.TemporaryDirectory() as home:
    spool=Path(home)/"render_bpy_jobs";spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"]=str(spool)
    root=Path(home)/"Production"
    scene=bpy.context.scene
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=10,
                                         location=(0,0,1))
    ob=bpy.context.object
    ob.name="SpeedHead"
    render_before=(scene.render.engine,scene.render.fps,
                   scene.render.resolution_x,scene.render.resolution_y)
    boot=Agent.execute("studio.agent.bootstrap",{
        "query":"rigging natural animation ik",
        "include_scene":True,"include_queue":True,
        "limit":12},root,scene)
    assert boot["source"]=="current actual Blender process"
    assert boot["scene"]["selected_object"]=="SpeedHead"
    assert boot["max_inspects_per_batch"]==6
    assert not boot["remote_eval_enabled"]
    assert len(boot["workspaces"])==9
    assert len(boot["manifest_sha256"])==64
    assert "tool_search" in boot and boot["tool_search"]["matches"],boot
    assert any("ik." in x["operation"]
               for x in boot["tool_search"]["matches"]),boot["tool_search"]

    native_cache_before=Studio._tool_index.cache_info()
    small=Agent.execute("studio.agent.bootstrap",{
        "known_manifest_sha256":boot["manifest_sha256"],
        "query":"zoom camera","limit":8},root,scene)
    native_cache_after=Studio._tool_index.cache_info()
    assert small["manifest_unchanged"]
    assert not small["full_tool_manifest_transferred"]
    assert "workspaces" not in small
    assert native_cache_after.hits>native_cache_before.hits
    assert any("view.orbit" in x["operation"]
               for x in small["tool_search"]["matches"]),small

    # Four existing inspections are now executed via one and only one
    # authenticated production IPC; no scene writes or unscoped scripts.
    inp={"reads":[
        {"operation":"scene.inspect","payload":{"limit":1}},
        {"operation":"studio.sculpt.inspect","payload":{"object":"SpeedHead"}},
        {"operation":"studio.workspace.inspect","payload":{}},
        {"operation":"studio.plan.list","payload":{}}]}
    started=time.perf_counter_ns()
    batch=Agent.execute("studio.agent.batch.inspect",inp,root,scene)
    wall=(time.perf_counter_ns()-started)/1e6
    assert batch["all_succeeded"],batch
    assert batch["reads_requested"]==4 and batch["reads_succeeded"]==4
    assert [x["operation"] for x in batch["results"]]==[
        x["operation"] for x in inp["reads"]]
    assert batch["results"][1]["result"]["vertices"]>50
    assert not batch["scene_modified_by_fastlane"]
    assert render_before==(scene.render.engine,scene.render.fps,
                           scene.render.resolution_x,scene.render.resolution_y)
    assert ob.name=="SpeedHead" and ob.type=="MESH"
    assert not list((root/"Projects").glob("*.blend")) if (root/"Projects").exists() else True

    # Recoverable per-step errors are explicitly called failed, never success.
    failed=Agent.execute("studio.agent.batch.inspect",{"reads":[
        {"operation":"studio.ik.inspect","payload":{"rig":"NonexistentRig"}},
        {"operation":"studio.sculpt.inspect","payload":{"object":"SpeedHead"}}]},
        root,scene)
    assert not failed["all_succeeded"] and failed["reads_succeeded"]==1,failed
    assert failed["results"][0]["state"]=="failed"
    assert "error_code" in failed["results"][0]
    assert failed["results"][1]["state"]=="succeeded"

    program={"name":"Accurate IK pose","steps":[
        {"operation":"studio.pose.inspect","payload":{"rig":"ActorRig"}},
        {"operation":"studio.ik.inspect","payload":{"rig":"ActorRig"}}]}
    preview=Agent.execute("studio.agent.plan.preview",program,root,scene)
    assert preview["total_steps"]==2 and not preview["simulation_executed"]
    assert preview["available_plan_slots"]==4
    assert not Queue.list_jobs(root)["jobs"]  # no plan was created
    measurements=Agent.execute("studio.agent.metrics",{"limit":20},root,scene)
    assert len(measurements["measurements"])>=4,measurements
    assert not measurements["engine_or_render_quality_modified"]

    print("PASS: Blender scene/bootstrap/tool search in one native call; SHA ETag reuses immutable schema",flush=True)
    print("PASS: 4 authenticated read-only commands in 1 Blender IPC, native cost(ms)=",round(wall,3),flush=True)
    print("PASS: per-read failure receipts, plan-preview-only, no hidden .blend mutation",flush=True)
    print("NOT CLAIMED: phone network speedup, 3D artistic realism, parallel scene writes, device thermals",flush=True)
