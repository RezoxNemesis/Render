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
        col.operator("renderstudio.direct_sculpt_inspect",text="Inspect Mesh and Brush")
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
          RENDERSTUDIO_OT_direct_sculpt_leave,
          RENDERSTUDIO_OT_direct_sculpt_inspect,
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
