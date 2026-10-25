# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Blender 4.x mesh sculpt, signed revision, bone pose and live frame test.

No mock scene, fake cursor input, Android screenshot or proprietary DCC claim.
"""
import os
from pathlib import Path
import tempfile
import sys

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_unified_workspace as Studio
import render_unified_queue as Queue
import render_production
import render_live_gestures as Gesture

with tempfile.TemporaryDirectory() as temp:
    spool=Path(temp)/"render_bpy_jobs";spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"]=str(spool)
    root=Path(temp)/"Production"
    scene=bpy.context.scene
    original=(scene.render.engine,scene.render.fps,
              scene.render.resolution_x,scene.render.resolution_y)
    # Native editable mesh, with ~200 real vertices. No bitmap substitute.
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,
                                         radius=1.0,location=(0,0,1.0))
    mesh=bpy.context.object
    mesh.name="SculptTarget"
    for polygon in mesh.data.polygons:polygon.use_smooth=True
    meta=Gesture.mesh_inspect(scene,{"object":mesh.name})
    sha=meta["mesh_revision_sha256"];count=meta["vertices"]
    initial=[v.co.copy() for v in mesh.data.vertices]
    command={"object":mesh.name,"expected_vertices":count,"expected_sha256":sha,
             "center":[.30,0,.35],"direction":[0,0,1],
             "radius":.84,"strength":.18,"mode":"PUSH",
             "falloff":"SMOOTHSTEP","mirror_x":True}
    preview=Gesture.sculpt(scene,dict(command,dry_run=True))
    assert preview["vertices_predicted"]>0
    assert not preview["native_blender_vertex_coordinates_updated"]
    assert all((a-b.co).length<1e-12 for a,b in zip(initial,mesh.data.vertices))
    applied=render_production.execute(
        {"operation":"studio.sculpt.brush","payload":command},str(spool),"a"*32)
    assert applied["native_blender_vertex_coordinates_updated"],applied
    assert applied["vertices_changed"]==preview["vertices_predicted"],(applied,preview)
    assert applied["mesh_revision_after"]!=sha
    assert len(mesh.data.vertices)==count
    assert any((a-b.co).length>.01 for a,b in zip(initial,mesh.data.vertices))
    assert not applied["topology_changed"]
    import render_native_hud as HUD
    HUD.command_started({"args":{"operation":"studio.sculpt.brush",
                                 "payload":command}})
    HUD.command_finished({"state":"succeeded","result":applied})
    marker=HUD.snapshot()["verified_sculpt_marker"]
    assert marker and marker["object"]==mesh.name,marker
    assert marker["local_center"]==command["center"],marker
    assert HUD.snapshot()["fabricated_ui_taps"] is False
    try:
        Gesture.sculpt(scene,command)
        raise AssertionError("Stale mesh revision accepted")
    except ValueError as error:
        assert str(error)=="STUDIO_SCULPT_MESH_REVISION_CONFLICT",error
    try:
        Gesture.sculpt(scene,dict(command,expected_sha256=applied["mesh_revision_after"],
                                      strength=5))
        raise AssertionError("Unsafe sculpt displacement accepted")
    except ValueError as error:
        assert str(error)=="STUDIO_GESTURE_NUMBER_INVALID",error

    rig_data=bpy.data.armatures.new("ActorBones")
    rig=bpy.data.objects.new("ActorRig",rig_data)
    scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bone=rig_data.edit_bones.new("Head")
    bone.head=(0,0,0);bone.tail=(0,0,1)
    bpy.ops.object.mode_set(mode="OBJECT")
    assert "Head" in rig.pose.bones
    poses=[
       {"rig":"ActorRig","bone":"Head","frame":1,"rotation_euler":[0,0,0]},
       {"rig":"ActorRig","bone":"Head","frame":20,
        "rotation_euler":[0,.5,.3],"allow_existing_action":True}
    ]
    first=render_production.execute({"operation":"studio.pose.key",
                "payload":poses[0]},str(spool),"b"*32)
    second=render_production.execute({"operation":"studio.pose.key",
                "payload":poses[1]},str(spool),"c"*32)
    assert first["native_pose_key_inserted"] and second["native_pose_key_inserted"]
    assert rig.animation_data.action is not None
    start=Studio.execute("studio.timeline.scrub",{"frame":1,"rig":rig.name,
                   "bone":"Head"},root,scene)
    end=Studio.execute("studio.timeline.scrub",{"frame":20,"rig":rig.name,
                 "bone":"Head"},root,scene)
    distance=(Vector(start["tail_world"])-Vector(end["tail_world"])).length
    assert distance>.25,distance # measured ~0.299 scene units in Blender 4.0
    assert end["native_blender_frame_evaluated"]
    report=Gesture.pose_inspect(scene,{"rig":rig.name,"bones":["Head"]})
    assert report["frame"]==20 and len(report["bones"])==1
    try:
        Gesture.pose_key(scene,dict(poses[1],frame=30,allow_existing_action=False))
        raise AssertionError("Existing action overwritten without approval")
    except ValueError as e:
        assert "STUDIO_POSE_EXISTING_ACTION_APPROVAL_REQUIRED" in str(e)

    # Two independent real mesh mutations can stream consecutively only
    # when the second uses the exact SHA from the preceding committed brush.
    # It is not a blanket "use whatever mesh state exists" shortcut.
    fresh=Gesture.mesh_inspect(scene,{"object":mesh.name})["mesh_revision_sha256"]
    follow=dict(command,expected_sha256=fresh,strength=.04)
    chain=dict(command,expected_sha256="$prev_mesh_sha256",strength=.03)
    request={"plan_id":"3"*32,"name":"Sculpt two steps and inspect motion",
             "steps":[{"operation":"studio.sculpt.brush","payload":follow},
                      {"operation":"studio.sculpt.brush","payload":chain},
                      {"operation":"studio.timeline.scrub",
                       "payload":{"frame":12,"rig":rig.name,"bone":"Head"}}]}
    accepted=Studio.execute("studio.plan.submit",request,root,scene)
    assert accepted["state"]=="queued"
    results=[]
    for unused in range(3):
        result=Queue.tick(root,Studio._execute_step,on_start=Studio._step_start,
                          on_finish=Studio._step_end)
        results.append(result)
        assert result["result"]=="succeeded",results
    assert scene.frame_current==12
    assert Queue.get(root,"3"*32)["completed_steps"]==3
    raw=Queue._load_file(Queue._path(root,"3"*32))
    assert raw["receipts"][0]["mesh_revision_after"]!=fresh
    assert raw["receipts"][1]["mesh_revision_after"]!=raw["receipts"][0]["mesh_revision_after"]
    assert raw["steps"][1]["payload"]["expected_sha256"]=="$prev_mesh_sha256"
    history=Studio.execute("studio.activity",{"limit":16},root,scene)
    assert any(x.get("operation")=="studio.timeline.scrub" for x in history["events"])
    checkpoints=list((root/"Projects").glob("*.blend"))
    assert len(checkpoints)>=3,len(checkpoints)
    assert original==(scene.render.engine,scene.render.fps,
                      scene.render.resolution_x,scene.render.resolution_y)
    print("PASS: real Blender mesh vertices",count, "modified",applied["vertices_changed"],
          "symmetry",applied["mirrored"],flush=True)
    print("PASS: real armature 20f pose trajectory distance",round(distance,4),flush=True)
    print("PASS: live serialized Blender plan, actual timeline and checkpoints",
          len(checkpoints),flush=True)
    print("NOT PROVEN: Android phone UI, sculpt mode interactive cursor, IK physics, benchmark realism",flush=True)
