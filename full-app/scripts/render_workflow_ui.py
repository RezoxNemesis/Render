# SPDX-License-Identifier: GPL-2.0-or-later
"""Visible Render Studio benchmark controls, using the SAME authenticated bpy.

The owner can see native scene data/operations and manually invoke real
linked geometry, PBR, and rigid-body tools. No synthetic mouse trajectory
or claim that the external desktop video frames were recreated.
"""
import os
import uuid
import bpy
import render_workflow_contract as Contract
import render_workflow_ops as Workflow

_INSTALLED=False
_LAST_AUDIT=None
_VIDEOS=tuple((v[0].replace(".","_"),v[0],v[2]) for v in Contract.BENCHMARKS)

def _execute(op,p):
    if bpy.app.is_job_running("RENDER"):
        raise ValueError("STUDIO_BENCHMARK_NATIVE_RENDER_IS_BUSY")
    spool=os.environ.get("RENDER_AGENT_SPOOL")
    if not spool:
        raise ValueError("STUDIO_BENCHMARK_NATIVE_SPOOL_NOT_READY")
    import render_production
    return render_production.execute({"operation":op,"payload":p},spool,uuid.uuid4().hex)

class RENDERSTUDIO_OT_benchmark_scene_audit(bpy.types.Operator):
    bl_idname="renderstudio.benchmark_scene_audit"
    bl_label="Inspect Real Benchmark Evidence"
    bl_description="Count actual current Blender mesh, NLA, PBR, simulation and compositor state"
    def execute(self,context):
        global _LAST_AUDIT
        try:
            _LAST_AUDIT=Workflow.audit(context.scene,{})
            scene=context.scene
            scene.render_studio_benchmark_last_summary=(
               str(_LAST_AUDIT["native_meshes"])+" meshes / "+
               str(_LAST_AUDIT["used_actions"])+" actions / "+
               str(_LAST_AUDIT["nla_strips"])+" NLA strips")
            self.report({"INFO"},scene.render_studio_benchmark_last_summary)
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as error:
            self.report({"ERROR"},str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_OT_benchmark_selected_action(bpy.types.Operator):
    bl_idname="renderstudio.benchmark_selected_action"
    bl_label="Apply Real Blender Artist Tool"
    bl_description="Perform a checked native scene edit on the selected mesh with an editable checkpoint"
    def execute(self,context):
        selected=context.active_object
        if selected is None or selected.type!="MESH":
            self.report({"WARNING"},"Select an editable Blender MESH first")
            return {"CANCELLED"}
        scene=context.scene
        mode=scene.render_studio_benchmark_action
        try:
            if mode=="SCATTER":
                radius=max(.1,min(10,max(selected.dimensions)*1.8))
                xyz=selected.matrix_world.translation
                base=[float(xyz.x),float(xyz.y),float(xyz.z)]
                args={"source":selected.name,
                      "name":"RS_LinkedInstances_"+uuid.uuid4().hex[:8],
                      "count":scene.render_studio_benchmark_instances,
                      "seed":21,"min":[base[0]-radius,base[1]-radius,base[2]],
                      "max":[base[0]+radius,base[1]+radius,base[2]]}
                op="studio.procedural.scatter"
            elif mode=="MATERIAL":
                args={"object":selected.name,
                      "name":"RS_RealPBR_"+uuid.uuid4().hex[:8],
                      "preset":scene.render_studio_benchmark_material,
                      "replace_existing":scene.render_studio_benchmark_replace_material}
                op="studio.material.surface"
            elif mode=="PHYSICS":
                args={"object":selected.name,"type":"ACTIVE","mass":1.0}
                op="studio.sim.rigidbody"
            else:raise ValueError("STUDIO_BENCHMARK_TOOL_UNAVAILABLE")
            answer=_execute(op,args)
            scene.render_studio_benchmark_last_summary=(
                op+" • verified "+("native linked "+str(answer["native_instances_created"])
                if mode=="SCATTER" else str(answer.get("material",answer.get("object")))))
            for area in context.window.screen.areas:
                if area.type=="VIEW_3D":area.tag_redraw()
            self.report({"INFO"},"Native Blender edit committed with source checkpoint")
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError,OSError) as error:
            self.report({"ERROR"},str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_PT_benchmark_workflows(bpy.types.Panel):
    bl_idname="RENDERSTUDIO_PT_benchmark_workflows"
    bl_label="Real Artist Workflow Benchmarks"
    bl_space_type="VIEW_3D"
    bl_region_type="UI"
    bl_category="Render Studio"
    def draw(self,context):
        box=self.layout
        scene=context.scene
        box.label(text="10 external video targets (not app captures)")
        box.prop(scene,"render_studio_benchmark_clip",text="Reference")
        index=next((i for i,v in enumerate(_VIDEOS)
                    if v[0]==scene.render_studio_benchmark_clip),0)
        clip=Contract.BENCHMARKS[index]
        box.label(text=clip[2][:58])
        box.label(text="Target: "+clip[3][:56])
        box.operator("renderstudio.benchmark_scene_audit",
                     text="Audit Actual Scene",icon="VIEWZOOM")
        if _LAST_AUDIT is not None:
            box.label(text=scene.render_studio_benchmark_last_summary[:64])
            box.label(text="Real rig bones: "+str(_LAST_AUDIT["rig_bones"]))
            box.label(text="Real body physics: "+str(_LAST_AUDIT["rigid_body_objects"]))
            box.label(text="Compositor nodes: "+str(len(_LAST_AUDIT["grade_nodes"])))
        box.separator()
        box.label(text="Run one native edit on selected mesh")
        box.prop(scene,"render_studio_benchmark_action",text="Tool")
        mode=scene.render_studio_benchmark_action
        if mode=="SCATTER":
            box.prop(scene,"render_studio_benchmark_instances",text="Linked Copies")
        if mode=="MATERIAL":
            box.prop(scene,"render_studio_benchmark_material",text="PBR Type")
            box.prop(scene,"render_studio_benchmark_replace_material",
                     text="Allow material replacement")
        box.operator("renderstudio.benchmark_selected_action",
                     text="Execute Real Blender Action",icon="MODIFIER")
        box.separator()
        box.label(text="Observed ChatGPT actions")
        try:
            import render_unified_workspace
            recent=render_unified_workspace._history()[-6:]
            if not recent:box.label(text="No native actions recorded")
            for entry in recent:
                state=str(entry.get("event","unknown"))[:9]
                op=str(entry.get("operation",""))[:37]
                box.label(text=state+"  "+op)
        except (ImportError,ValueError,OSError,RuntimeError):pass
        box.label(text="No fake click playback or vendor parity")

_CLASSES=(RENDERSTUDIO_OT_benchmark_scene_audit,
          RENDERSTUDIO_OT_benchmark_selected_action,
          RENDERSTUDIO_PT_benchmark_workflows)

def install():
    global _INSTALLED
    if bpy.app.background or _INSTALLED:return
    cls=bpy.types.Scene
    cls.render_studio_benchmark_clip=bpy.props.EnumProperty(
        name="External video target",items=_VIDEOS,default=_VIDEOS[0][0])
    cls.render_studio_benchmark_action=bpy.props.EnumProperty(
        name="Native tool",items=[
            ("SCATTER","Linked Scatter","Actual Blender linked mesh copies"),
            ("MATERIAL","PBR Surface","Editable procedural shader and bump"),
            ("PHYSICS","Rigid Body","Actual Blender physics body")],
        default="SCATTER")
    cls.render_studio_benchmark_instances=bpy.props.IntProperty(
        name="Copies",default=6,min=1,max=16)
    cls.render_studio_benchmark_material=bpy.props.EnumProperty(
        name="Surface preset",items=[(p,p.title(),"") for p in
          ("SKIN","LEAF","CLOTH","STONE","METAL")],default="STONE")
    cls.render_studio_benchmark_replace_material=bpy.props.BoolProperty(
        name="Approve replacement",default=False)
    cls.render_studio_benchmark_last_summary=bpy.props.StringProperty(default="")
    for op in _CLASSES:bpy.utils.register_class(op)
    _INSTALLED=True

def installed():
    return _INSTALLED

def uninstall():
    global _INSTALLED
    if _INSTALLED:
        for op in reversed(_CLASSES):
            try:bpy.utils.unregister_class(op)
            except RuntimeError:pass
        _INSTALLED=False
