# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender bpy acceptance for SEVEN missing artist capabilities.

Runs on desktop Blender CI using exactly the native Android bpy modules.
Checks DATA CHANGES (mesh faces, shader links, animation curves, NLA strips,
instanced datablocks, compositor links, rigid body and 2D curve splines).
Does not pretend remote video UI, physical Android GPU or finished likeness.
"""
import os
from pathlib import Path
import tempfile
import sys
import math
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_production as Production
import render_workflow_ops as Ops
import render_unified_workspace as Studio
import render_unified_queue as Queue

with tempfile.TemporaryDirectory() as d:
    spool=Path(d)/"render_bpy_jobs";spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"]=str(spool)
    project=Path(d)/"Production"
    scene=bpy.context.scene
    original=(scene.render.engine,scene.render.fps,scene.render.resolution_x,
              scene.render.resolution_y,scene.render.resolution_percentage)
    def native(op,p):
        result=Production.execute({"operation":op,"payload":p},str(spool),
                                   "real_android_protocol_smoke")
        assert isinstance(result,dict),result
        return result
    def ring(z):
        return [(math.cos(i*math.pi/2)*.5,math.sin(i*math.pi/2)*.5,z)
                for i in range(4)]
    verts=ring(0)+ring(1)+ring(2)+ring(3)
    faces=[]
    for start in (0,8):
        for i in range(4):
            j=(i+1)%4
            faces.append((start+i,start+j,start+j+4,start+i+4))
    mesh=bpy.data.meshes.new("NativeArch")
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    arch=bpy.data.objects.new("ArchEdgeMesh",mesh)
    scene.collection.objects.link(arch)
    bridge_args={"object":arch.name,"expected_vertices":16,
                 "expected_polygons":8,
                 "loops":[[4,5,6,7],[8,9,10,11]]}
    preview=native("studio.mesh.bridge_loops",dict(bridge_args,dry_run=True))
    assert preview["would_add_quads"]==4 and len(mesh.polygons)==8
    data=native("studio.mesh.bridge_loops",bridge_args)
    assert data["native_editable_bridge_faces_created"]
    assert len(mesh.polygons)==12 and len(mesh.vertices)==16
    assert arch.get("render_benchmark_bridge")==4

    material=native("studio.material.surface",{
        "object":arch.name,"name":"StoneForArch","preset":"STONE",
        "roughness":.65,"detail_scale":45,"bump":.16})
    assert material["actual_shader_node_tree_created"]
    mat=mesh.materials[0]
    assert mat.node_tree.nodes.get("RS_EditableSurfaceMicroBump") is not None
    shader=next(x for x in mat.node_tree.nodes if x.type=="BSDF_PRINCIPLED")
    assert shader.inputs["Normal"].is_linked
    count=native("studio.procedural.scatter",{
        "source":arch.name,"name":"RuinsScatter","count":9,"seed":17,
        "min":[-2,-2,0],"max":[2,2,0],
        "scale_min":.8,"scale_max":1.2})
    assert count["native_instances_created"]==9,count
    copies=[ob for ob in scene.objects if ob.get("render_benchmark_scatter")]
    assert len(copies)==9 and all(ob.data==mesh for ob in copies),count
    assert mesh.users==10

    rig_data=bpy.data.armatures.new("ActorBoneData")
    rig=bpy.data.objects.new("ActingRig",rig_data)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bone=rig_data.edit_bones.new("Arm")
    bone.head=(0,0,0);bone.tail=(0,0,1)
    bpy.ops.object.mode_set(mode="OBJECT")
    action=native("studio.motion.action.create",{
        "rig":rig.name,"bone":"Arm","name":"JabAction",
        "keys":[{"frame":1,"rotation_euler":[0,0,0]},
                {"frame":6,"rotation_euler":[0,.5,.3]},
                {"frame":12,"rotation_euler":[0,0,0]}]})
    assert action["native_action_created"],action
    assert rig.animation_data.action is not None
    assert rig.animation_data.action.name=="JabAction"
    assert action["native_fcurves"]>=3,action
    scene.frame_set(6)
    middle=Vector(rig.pose.bones["Arm"].tail)
    scene.frame_set(1)
    beginning=Vector(rig.pose.bones["Arm"].tail)
    assert (middle-beginning).length>.1,(middle,beginning)
    nla=native("studio.motion.nla.create",{
        "rig":rig.name,"action":"JabAction","name":"BoxingTrack","frame_start":20})
    assert nla["native_nla_track_created"],nla
    assert len(rig.animation_data.nla_tracks)==1

    grade=native("studio.compositor.grade",{
        "name":"WIPvsFinal","brightness":.03,"contrast":.15,
        "saturation":1.16,"activate":True})
    assert grade["native_compositor_graph_linked"],grade
    assert grade["activated_for_final_render"]
    state=native("studio.compositor.inspect",{})
    assert state["enabled"] and state["composite_has_input"],state
    assert len(state["native_grade_nodes"])==2

    cube_mesh=bpy.data.meshes.new("PhysicsCrateMesh")
    cube_mesh.from_pydata([(-.2,-.2,1),(.2,-.2,1),(.2,.2,1),(-.2,.2,1),
                           (-.2,-.2,1.4),(.2,-.2,1.4),(.2,.2,1.4),(-.2,.2,1.4)],
                         [],[(0,1,2,3),(4,5,6,7)])
    cube_mesh.update()
    crate=bpy.data.objects.new("Crate",cube_mesh)
    scene.collection.objects.link(crate)
    rigid=native("studio.sim.rigidbody",{"object":crate.name,
            "type":"ACTIVE","mass":1.3,"friction":.65,"bounce":.1})
    assert rigid["native_blender_rigidbody_created"],rigid
    assert crate.rigid_body is not None and crate.rigid_body.type=="ACTIVE"
    assert abs(crate.rigid_body.mass-1.3)<.001

    ink=native("studio.drawing.strokes",{"name":"2DStoryboardContours",
        "strokes":[[[0,0],[.3,.6],[.8,.4],[1,1]],
                   [[.1,.1],[.5,.2],[1,.1]]],
        "thickness":.009,"color":[.02,.02,.03]})
    assert ink["actual_2d_ink_geometry_created"],ink
    obj=scene.objects[ink["object"]]
    assert obj.type=="CURVE" and len(obj.data.splines)==2

    archive=native("studio.benchmark.catalog",{})
    assert archive["total_benchmarks"]==10
    assert any(x["filename"]=="1000071906.mp4" for x in archive["benchmarks"])
    audit=native("studio.benchmark.audit",{})
    assert audit["bridge_meshes"]>=1,audit
    assert audit["linked_scatter_instances"]==9
    assert audit["rigid_body_objects"]==1
    assert audit["nla_strips"]==1
    assert len(audit["grade_nodes"])==2
    assert not audit["liquigen_fluid_interop_implemented"]
    assert not audit["benchmark_visual_criteria_automatically_passed"]
    assert original==(scene.render.engine,scene.render.fps,scene.render.resolution_x,
                      scene.render.resolution_y,scene.render.resolution_percentage)
    # Verify several durable native artist steps are VISIBLE TO CHATGPT as
    # individual serialized actions, not a single false "completed" click.
    submitted=Studio.execute("studio.plan.submit",{
        "plan_id":"b"*32,"name":"Visual sculpt to cinema",
        "steps":[{"operation":"studio.benchmark.audit","payload":{}},
                 {"operation":"studio.drawing.strokes","payload":{
                     "name":"ProgressStroke","strokes":[[[0,0],[.5,.3]]]}},
                 {"operation":"studio.compositor.inspect","payload":{}}]},
        project,scene)
    assert submitted["state"]=="queued",submitted
    for i in range(3):
        result=Queue.tick(project,Studio._execute_step,
                          on_start=Studio._step_start,on_finish=Studio._step_end)
        assert result["result"]=="succeeded",result
    receipts=Queue.get(project,"b"*32)
    assert receipts["completed_steps"]==3 and receipts["state"]=="completed"
    history=Studio.execute("studio.activity",{"limit":16},project,scene)
    assert any(x.get("operation")=="studio.drawing.strokes"
               for x in history["events"]),history
    checkpoint_paths=list((project/"Projects").glob("*.blend"))
    assert len(checkpoint_paths)>=6,len(checkpoint_paths)
    print("PASS: real Blender bridge 4 quads, linked 9x geometry, PBR shader tree",flush=True)
    print("PASS: rig action 3 FCurves/NLA, compositor grade, rigid body, 2D curves",flush=True)
    print("PASS: 3-step serial native agent with real progress events and",
          len(checkpoint_paths),"saved .blend files",flush=True)
    print("NOT VERIFIED: external videos reproduced, mobile real-time sculpting,"
          " LiquiGen fluid interop, physical-device visual quality",flush=True)
