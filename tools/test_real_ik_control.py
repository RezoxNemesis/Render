# SPDX-License-Identifier: GPL-2.0-or-later
"""Genuine Blender IK constraint, moving target, FK/IK switching, pose tests."""
import os
from pathlib import Path
import tempfile
import sys
import math
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_ik_control as IK
import render_production
import render_unified_workspace as Studio
import render_unified_queue as Q

with tempfile.TemporaryDirectory() as tmp:
    spool=Path(tmp)/"render_bpy_jobs";spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"]=str(spool)
    root=Path(tmp)/"Production"
    scene=bpy.context.scene
    baseline=(scene.render.engine,scene.render.fps,
              scene.render.resolution_x,scene.render.resolution_y)
    rig_data=bpy.data.armatures.new("JointRigData")
    rig=bpy.data.objects.new("JointRig",rig_data)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    top=rig_data.edit_bones.new("Thigh")
    top.head=(0,0,0);top.tail=(0,0,1)
    lower=rig_data.edit_bones.new("Shin")
    lower.head=(0,0,1);lower.tail=(.43,0,1.78)
    lower.parent=top;lower.use_connect=False
    bpy.ops.object.mode_set(mode="OBJECT")
    scene.frame_set(1)
    assert len(rig.pose.bones)==2

    args={"rig":"JointRig","bone":"Shin","controller":"FootTarget",
          "chain_length":2}
    probe=IK.execute("studio.ik.create",dict(args,dry_run=True),root,scene)
    assert probe["native_ik_created"] is False
    result=render_production.execute(
        {"operation":"studio.ik.create","payload":args},str(spool),"a"*32)
    assert result["native_ik_created"] and result["chain_length"]==2,result
    assert "FootTarget" in scene.objects
    assert rig.pose.bones["Shin"].constraints[0].type=="IK"
    assert scene.objects["FootTarget"].parent==rig
    assert "FootTarget" in bpy.data.objects
    initial=IK.execute("studio.ik.inspect",{"rig":rig.name,"bone":"Shin","frame":1},root,scene)
    first=initial["inspected_controls"][0]
    assert initial["frame_restored"] and first["revision_sha256"]
    start_tail=Vector(first["effector_tail_world"])

    # The target is a real native Blender Empty, not a made-up screen point.
    location=[.9,.18,1.28]
    planned=IK.execute("studio.ik.target",{
        "rig":rig.name,"bone":"Shin","frame":1,
        "location_world":location,
        "expected_sha256":first["revision_sha256"],
        "dry_run":True},root,scene)
    assert planned["key_inserted"] is False
    assert not scene.objects["FootTarget"].animation_data
    move=render_production.execute({"operation":"studio.ik.target","payload":{
        "rig":rig.name,"bone":"Shin","frame":1,
        "location_world":location,
        "expected_sha256":first["revision_sha256"]}},
        str(spool),"b"*32)
    assert move["target_key_inserted"] and move["native_bpy_controller_moved"],move
    assert scene.objects["FootTarget"].animation_data.action is not None
    target_world=Vector(move["target_world"])
    new_tail=Vector(move["effector_tail_world"])
    # Physically evaluate actual Blender solver response at target frame.
    assert (target_world-Vector(location)).length<1e-4,(move,target_world)
    assert (new_tail-start_tail).length>.08,(new_tail,start_tail)
    assert move["target_to_effector_world_distance"] < .4,move

    # A stale agent receipt must never move the artist's newly keyed IK.
    try:
        IK.execute("studio.ik.target",{
            "rig":rig.name,"bone":"Shin","frame":1,
            "location_world":[0,0,0],
            "expected_sha256":first["revision_sha256"]},root,scene)
        raise AssertionError("Stale native IK target revision was accepted")
    except ValueError as error:
        assert str(error)=="STUDIO_IK_REVISION_CONFLICT",error

    # FK/IK is an actual keyframed Blender constraint influence channel.
    before_fk=IK.execute("studio.ik.inspect",{
        "rig":rig.name,"bone":"Shin","frame":20},root,scene)["inspected_controls"][0]
    fk=render_production.execute({"operation":"studio.ik.blend","payload":{
        "rig":rig.name,"bone":"Shin","frame":20,
        "influence":0,"expected_sha256":before_fk["revision_sha256"]}},
        str(spool),"c"*32)
    assert fk["selected_mode"]=="FK" and fk["ik_influence_key_inserted"],fk
    assert abs(rig.pose.bones["Shin"].constraints[0].influence)<1e-5
    # A local FK rotation now really controls the end-effector.
    fkpose=render_production.execute({"operation":"studio.pose.key","payload":{
        "rig":"JointRig","bone":"Shin","frame":20,
        "rotation_euler":[0,.4,.15],
        "allow_existing_action":True}},str(spool),"d"*32)
    assert fkpose["native_pose_key_inserted"]
    scene.frame_set(20)
    fk_tail=Vector(rig.matrix_world@rig.pose.bones["Shin"].tail)
    assert (fk_tail-new_tail).length>.05

    # Re-enable IK on a later frame and evaluate the real armature action.
    before_ik=IK.execute("studio.ik.inspect",{
        "rig":rig.name,"bone":"Shin","frame":32},root,scene)["inspected_controls"][0]
    on=render_production.execute({"operation":"studio.ik.blend","payload":{
        "rig":rig.name,"bone":"Shin","frame":32,
        "influence":1.0,
        "expected_sha256":before_ik["revision_sha256"],
        "allow_existing_action":True}},str(spool),"e"*32)
    assert on["selected_mode"]=="IK" and on["ik_influence_key_inserted"],on
    assert rig.animation_data.action is not None
    channels=[c.data_path for c in rig.animation_data.action.fcurves]
    assert any("influence" in path for path in channels),channels
    scene.frame_set(32)
    ik_tail=Vector(rig.matrix_world@rig.pose.bones["Shin"].tail)
    assert (ik_tail-fk_tail).length>.03,(fk_tail,ik_tail)

    # Resilient native agent queue using a real on-scene, discoverable action.
    queued=Studio.execute("studio.plan.submit",{
        "plan_id":"f"*32,"name":"Inspect IK actor",
        "steps":[{"operation":"studio.ik.inspect",
                  "payload":{"rig":"JointRig","bone":"Shin","frame":32}},
                 {"operation":"studio.timeline.scrub",
                  "payload":{"frame":20,"rig":"JointRig","bone":"Shin"}}]
        },root,scene)
    assert queued["state"]=="queued"
    for i in range(2):
        receipt=Q.tick(root,Studio._execute_step,on_start=Studio._step_start,
                       on_finish=Studio._step_end)
        assert receipt["result"]=="succeeded",receipt
    assert Q.get(root,"f"*32)["state"]=="completed"
    assert scene.frame_current==20
    assert baseline==(scene.render.engine,scene.render.fps,
                     scene.render.resolution_x,scene.render.resolution_y)
    checkpoints=list((root/"Projects").glob("*.blend"))
    assert len(checkpoints)>=4,len(checkpoints)
    assert IK.execute("studio.ik.inspect",{"rig":"JointRig"},root,scene)["inspected_controls"]
    print("PASS: actual bpy IK with animated target world movement",
          round((new_tail-start_tail).length,4),flush=True)
    print("PASS: keyed FK/IK influence, genuine pose channels and separate IK/FK evaluation",
          round((ik_tail-fk_tail).length,4),flush=True)
    print("PASS: serialized agent, saved .blend checkpoints",len(checkpoints),flush=True)
    print("NOT VERIFIED: phone visual rendering, physics IK accuracy or reference likeness",flush=True)
