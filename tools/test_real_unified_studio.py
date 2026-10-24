# SPDX-License-Identifier: GPL-2.0-or-later
"""Smoke-test genuine Blender bpy, not a mocked remote user interface.

Verifies native operation discovery, owner-named action plan, actual mesh and
keyframes, completed on-disk job receipts, recovery requirements and no
fabricated area/navigation or Android background claims.
"""
import json
import os
from pathlib import Path
import tempfile
import sys
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_unified_contract as C
import render_unified_queue as Q
import render_unified_workspace as Studio

with tempfile.TemporaryDirectory() as d:
    spool=Path(d)/"render_bpy_jobs"
    spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"]=str(spool)
    root=Path(d)/"Production"
    scene=bpy.context.scene
    before=(scene.render.engine,scene.render.fps,
            scene.render.resolution_x,scene.render.resolution_y)
    Studio.install_timer()
    api=Studio.execute("studio.capabilities",{},root,scene)
    assert len(api["workspaces"])==9 and not api["background_scene_edits_concurrent"]
    assert "studio.plan.submit" in api["api_supported_ops"]
    assert api["background_bpy"] and not api["app_ui_installed"]
    index=Studio.execute("studio.tool.search",{"query":"rig","limit":20},root,scene)
    assert any(x["operation"]=="rig.create" for x in index["matches"]),index
    selected=Studio.execute("studio.workspace.activate",{"workspace":"animation"},root,scene)
    assert selected["workspace"]=="animation",selected
    inspected=Studio.execute("studio.workspace.inspect",{},root,scene)
    assert inspected["active_workspace"]=="animation"
    try:
        Studio.execute("studio.view.orbit",{"yaw_degrees":5,"pitch_degrees":1},root,scene)
    except ValueError as e:
        assert "STUDIO_NATIVE_VIEWPORT_NOT_OPEN" in str(e)
    plan_id="9"*32
    args={"plan_id":plan_id,"name":"Real Blender scene and keys",
          "steps":[{"operation":"mesh.create",
                    "payload":{"name":"ProductionOrb","kind":"UV_SPHERE","segments":16,"rings":8}},
                   {"operation":"animation.keys","payload":{"object":"ProductionOrb",
                      "keys":[{"frame":1,"path":"location","value":[0,0,0]},
                              {"frame":20,"path":"location","value":[1,0,0]}]}}]}
    accepted=Studio.execute("studio.plan.submit",args,root,scene)
    assert accepted["state"]=="queued" and accepted["total_steps"]==2,accepted
    # No timed mocks: the SAME executor the app's timer would call.
    one=Q.tick(root,Studio._execute_step,on_start=Studio._step_start,
               on_finish=Studio._step_end)
    assert one["result"]=="succeeded",one
    two=Q.tick(root,Studio._execute_step,on_start=Studio._step_start,
               on_finish=Studio._step_end)
    assert two["result"]=="succeeded" and two["job"]["state"]=="completed",two
    actual=scene.objects["ProductionOrb"]
    assert actual.type=="MESH" and len(actual.data.vertices)>10
    assert actual.animation_data.action is not None
    scene.frame_set(1)
    x1=float(actual.location.x)
    scene.frame_set(20)
    x2=float(actual.location.x)
    assert abs(x2-x1)>.9,(x1,x2)
    assert before==(scene.render.engine,scene.render.fps,
                    scene.render.resolution_x,scene.render.resolution_y)
    assert (root/"StudioPlans"/(plan_id+".json")).is_file()
    ledger=Studio.execute("studio.activity",{"limit":10},root,scene)
    assert any(e["operation"]=="mesh.create" for e in ledger["events"]),ledger
    recorded=Studio.execute("studio.plan.status",{"plan_id":plan_id},root,scene)
    assert recorded["completed_steps"]==2
    assert not recorded["requires_manual_review"]
    assert Q.recover(root)["interrupted_steps_marked_needs_review"]==0
    # Manual checkpoint copies exist because these commands edit real geometry.
    checkpoints=list((root/"Projects").glob("*.blend"))
    assert len(checkpoints)>=2,checkpoints
    print("PASS: Blender runtime version:",bpy.app.version_string)
    print("PASS: native object keyed 1..20, persisted two steps, honest recent actions")
    print("PASS: checkpoints",len(checkpoints),"geometry vertices",len(actual.data.vertices))
    print("NOT CLAIMED: Android UI/thermal/force-stop acceptance or human sculpt realism")
