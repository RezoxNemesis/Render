# SPDX-License-Identifier: GPL-2.0-or-later
"""On-device Blender UI for actual brush interaction, not synthesized taps."""
import bpy
import render_artist_direct as Native

_INSTALLED=False
_LAST_AUDIT=None

def _selected_mesh(context):
    obj=context.view_layer.objects.active
    if obj is None or obj.type!="MESH":
        raise ValueError("DIRECT_SCULPT_SELECT_MESH_FIRST")
    return obj

class RENDERSTUDIO_OT_direct_sculpt_enter(bpy.types.Operator):
    bl_idname="renderstudio.direct_sculpt_enter"
    bl_label="Sculpt Selected Mesh"
    bl_description="Switch selected Blender mesh into genuine interactive Sculpt Mode"
    bl_options={"REGISTER"}
    def execute(self,context):
        try:
            obj=_selected_mesh(context)
            result=Native.enter(context.scene,{"object":obj.name})
            self.report({"INFO"},"Native Sculpt Mode: "+result["object"])
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as error:
            self.report({"ERROR"},str(error));return {"CANCELLED"}

class RENDERSTUDIO_OT_direct_sculpt_brush(bpy.types.Operator):
    bl_idname="renderstudio.direct_sculpt_brush"
    bl_label="Choose Real Sculpt Brush"
    bl_description="Activate an installed Blender Essentials sculpt brush asset"
    bl_options={"REGISTER"}
    brush:bpy.props.EnumProperty(
        name="Real Blender brush",
        items=[(key,name,name) for key,name in Native.Contract.BRUSH_PRESETS.items()])
    def execute(self,context):
        try:
            obj=_selected_mesh(context)
            result=Native.select_brush(context.scene,{"object":obj.name,"brush":self.brush})
            self.report({"INFO"},"Active Blender brush: "+result["native_blender_brush_asset"])
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as error:
            self.report({"ERROR"},str(error));return {"CANCELLED"}

class RENDERSTUDIO_OT_direct_connected_copy(bpy.types.Operator):
    bl_idname="renderstudio.direct_connected_copy"
    bl_label="Create Connected Sculpt Copy"
    bl_description="Checkpoint then voxel-remesh a separate evaluated sculpt surface"
    bl_options={"REGISTER"}
    voxel_size_m:bpy.props.FloatProperty(
        name="Voxel size (metres)",default=.014,min=.002,max=.05,precision=3)
    offset_x:bpy.props.FloatProperty(
        name="Place beside X (metres)",default=-1.8,min=-20,max=20)
    max_voxels:bpy.props.IntProperty(
        name="Maximum voxel cells",default=3000000,min=100000,max=16000000)
    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self,width=340)
    def execute(self,context):
        try:
            obj=_selected_mesh(context)
            if abs(self.offset_x)<.9:
                raise ValueError("DIRECT_SCULPT_SURFACE_OFFSET_MUST_AVOID_OVERLAP")
            import os
            import uuid
            spool=os.environ.get("RENDER_AGENT_SPOOL")
            if not spool:raise ValueError("DIRECT_SCULPT_NO_NATIVE_CHECKPOINT_SPOOL")
            name=(obj.name[:46]+"_JoinedSurface")
            if name in bpy.data.objects:
                raise ValueError("DIRECT_SCULPT_SURFACE_NAME_EXISTS")
            world=obj.matrix_world.translation
            location=[float(world.x+self.offset_x),float(world.y),float(world.z)]
            import render_production
            result=render_production.execute(
                {"operation":"studio.artist.surface.clone","payload":{
                    "object":obj.name,"name":name,
                    "voxel_size_m":float(self.voxel_size_m),
                    "max_voxels":int(self.max_voxels),
                    "location":location}},
                spool,uuid.uuid4().hex)
            if not result["connected_mesh_verified"]:
                raise ValueError("DIRECT_SCULPT_SURFACE_UNVERIFIED")
            self.report({"INFO"},"Native connected sculpt copy: "+result["object"])
            return {"FINISHED"}
        except (ValueError,RuntimeError,OSError,AttributeError) as error:
            self.report({"ERROR"},str(error));return {"CANCELLED"}

class RENDERSTUDIO_OT_direct_sculpt_leave(bpy.types.Operator):
    bl_idname="renderstudio.direct_sculpt_leave"
    bl_label="Leave Sculpt Mode"
    bl_description="Return the selected native Blender mesh to Object Mode"
    bl_options={"REGISTER"}
    def execute(self,context):
        try:
            obj=_selected_mesh(context)
            Native.leave(context.scene,{"object":obj.name})
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as error:
            self.report({"ERROR"},str(error));return {"CANCELLED"}

class RENDERSTUDIO_OT_direct_sculpt_inspect(bpy.types.Operator):
    bl_idname="renderstudio.direct_sculpt_inspect"
    bl_label="Inspect Real Mesh & Brush"
    bl_description="Inspect native mesh connectedness and current Blender brush"
    bl_options={"REGISTER"}
    def execute(self,context):
        global _LAST_AUDIT
        try:
            obj=_selected_mesh(context)
            _LAST_AUDIT=Native.inspect(context.scene,{"object":obj.name})
            count=_LAST_AUDIT["connected_components"]
            label="unverified" if count is None else str(count)
            self.report({"INFO"},"Real Blender connected shells: "+label)
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as error:
            self.report({"ERROR"},str(error));return {"CANCELLED"}

class RENDERSTUDIO_PT_direct_artist(bpy.types.Panel):
    bl_idname="RENDERSTUDIO_PT_direct_artist"
    bl_label="Artist / Direct Sculpt"
    bl_space_type="VIEW_3D"
    bl_region_type="UI"
    bl_category="Render Studio"
    def draw(self,context):
        layout=self.layout
        ob=context.view_layer.objects.active
        layout.label(text="REAL BLENDER BRUSH",icon="SCULPTMODE_HLT")
        layout.label(text="Select the character mesh first")
        col=layout.column(align=True)
        col.operator("renderstudio.direct_sculpt_enter",text="Enter Live Sculpt",icon="SCULPTMODE_HLT")
        col.label(text="Native Sculpt Brushes")
        for key,label in (("DRAW","Draw"),("SMOOTH","Smooth"),("GRAB","Grab"),
                          ("CLAY_STRIPS","Clay Strips")):
            button=col.operator("renderstudio.direct_sculpt_brush",text=label)
            button.brush=key
        col.operator("renderstudio.direct_sculpt_inspect",text="Inspect Mesh and Brush")
        col.operator("renderstudio.direct_connected_copy",
                     text="New Connected Sculpt Copy")
        col.operator("renderstudio.direct_sculpt_leave",text="Exit Sculpt")
        if ob and ob.type=="MESH":
            col.label(text="Target: "+ob.name[:28])
            col.label(text="Mode: "+ob.mode)
        if _LAST_AUDIT and ob and ob.name==_LAST_AUDIT["object"]:
            count=_LAST_AUDIT["connected_components"]
            col.label(text="Connected shells: "+("Not measured" if count is None else str(count)))
            if count and count>1:
                col.label(text="Detached mesh! Join anatomy",icon="ERROR")
            col.label(text="Brush: "+str(_LAST_AUDIT.get("active_brush") or "Not loaded")[:27])
        last=Native.last_stroke()
        if last:
            col.label(text="Last verified sculpt: "+last["object"][:20])
            col.label(text="Edited verts: "+str(last["changed_vertices"]))
        layout.separator()
        layout.label(text="Real viewport input; no fake clicks")
        layout.label(text="Touch mapping needs phone test")
        layout.label(text="Camera motion is not animation")

_CLASSES=(RENDERSTUDIO_OT_direct_sculpt_enter,
          RENDERSTUDIO_OT_direct_sculpt_brush,
          RENDERSTUDIO_OT_direct_sculpt_leave,
          RENDERSTUDIO_OT_direct_sculpt_inspect,
          RENDERSTUDIO_OT_direct_connected_copy,
          RENDERSTUDIO_PT_direct_artist)

def install():
    global _INSTALLED
    if _INSTALLED or bpy.app.background:return
    for cls in _CLASSES:bpy.utils.register_class(cls)
    _INSTALLED=True

def uninstall():
    global _INSTALLED
    if _INSTALLED:
        for cls in reversed(_CLASSES):
            try:bpy.utils.unregister_class(cls)
            except RuntimeError:pass
    _INSTALLED=False

def installed():return _INSTALLED
