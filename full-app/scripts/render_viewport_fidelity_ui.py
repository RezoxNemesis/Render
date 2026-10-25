# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender sidebar for Phase 1 viewport fidelity.

Actions call the SAME native bpy controls as ChatGPT. No wallpaper/screenshot
replacement, fake taps or automatic global quality downgrade at startup.
"""
import bpy
import render_viewport_fidelity as Native
import render_viewport_fidelity_contract as Contract

_INSTALLED=False
_LAST_DIAG=None

class RENDERSTUDIO_OT_fidelity_apply(bpy.types.Operator):
    bl_idname="renderstudio.fidelity_apply"
    bl_label="Apply Viewport Fidelity"
    bl_description="Change only this real Blender 3D viewport (reversible)"
    def execute(self,context):
        params={"profile":context.scene.render_studio_fidelity_profile}
        if params["profile"]=="MATERIAL_REVIEW":
            if not context.scene.render_studio_allow_expensive_material_preview:
                self.report({"WARNING"},
                            "Enable expensive material shaders explicitly")
                return {"CANCELLED"}
            params["allow_expensive_shader_compile"]=True
        try:
            result=Native.apply(context.scene,params)
            self.report({"INFO"},
                result["profile"]+" / "+str(len(result["changed_native_fields"]))+
                " native viewport changes")
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as err:
            self.report({"ERROR"},str(err));return {"CANCELLED"}

class RENDERSTUDIO_OT_fidelity_restore(bpy.types.Operator):
    bl_idname="renderstudio.fidelity_restore"
    bl_label="Restore Original Viewport"
    bl_description="Restore the last native Blender viewport before Phase 1 profile"
    def execute(self,context):
        try:
            Native.restore(context.scene,{})
            self.report({"INFO"},"Original Blender viewport restored")
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as err:
            self.report({"ERROR"},str(err));return {"CANCELLED"}

class RENDERSTUDIO_OT_fidelity_analyze(bpy.types.Operator):
    bl_idname="renderstudio.fidelity_analyze"
    bl_label="Inspect Shattering / Detail"
    bl_description="Inspect real object/material/mesh evidence without changing art"
    def execute(self,context):
        global _LAST_DIAG
        params={}
        if context.active_object is not None:
            params["object"]=context.active_object.name
        try:
            _LAST_DIAG=Native.diagnose(context.scene,params)
            if _LAST_DIAG.get("object_found"):
                count=_LAST_DIAG["issue_count"]
                self.report({"WARNING"} if count else {"INFO"},
                            str(count)+" actual geometry/material/display concerns")
            else:self.report({"WARNING"},"Select a scene object first")
            return {"FINISHED"}
        except (ValueError,RuntimeError,AttributeError) as err:
            self.report({"ERROR"},str(err));return {"CANCELLED"}

class RENDERSTUDIO_PT_viewport_fidelity(bpy.types.Panel):
    bl_idname="RENDERSTUDIO_PT_viewport_fidelity"
    bl_label="Viewport Fidelity / Phase 1"
    bl_space_type="VIEW_3D"
    bl_region_type="UI"
    bl_category="Render Studio"
    def draw(self,context):
        layout=self.layout
        scene=context.scene
        layout.label(text="Preview-only native Blender quality")
        layout.prop(scene,"render_studio_fidelity_profile",text="Preset")
        if scene.render_studio_fidelity_profile=="MATERIAL_REVIEW":
            layout.prop(scene,"render_studio_allow_expensive_material_preview",
                        text="Allow shader compile / heat")
        layout.operator("renderstudio.fidelity_apply",text="Apply Clean Preview")
        layout.operator("renderstudio.fidelity_restore",text="Restore Original")
        layout.separator()
        layout.operator("renderstudio.fidelity_analyze",text="Diagnose Selected Model")
        if _LAST_DIAG is not None:
            if _LAST_DIAG.get("object_found"):
                layout.label(text="Inspected: "+_LAST_DIAG["object"][:28])
                for issue in _LAST_DIAG["issues"][:5]:
                    layout.label(text=issue.replace("_"," ").title()[:42],
                                 icon="ERROR")
            else:layout.label(text="Select a Blender object",icon="INFO")
        layout.separator()
        layout.label(text="No automatic geometry deletion")
        layout.label(text="Final render quality unchanged")

_CLASSES=(RENDERSTUDIO_OT_fidelity_apply,RENDERSTUDIO_OT_fidelity_restore,
          RENDERSTUDIO_OT_fidelity_analyze,RENDERSTUDIO_PT_viewport_fidelity)

def install():
    global _INSTALLED
    if _INSTALLED or bpy.app.background:return
    scene=bpy.types.Scene
    scene.render_studio_fidelity_profile=bpy.props.EnumProperty(
        name="Viewport fidelity",
        items=[(profile,profile.replace("_"," ").title(),"3D preview only")
               for profile in Contract.PROFILES],
        default="CLEAN_SOLID")
    scene.render_studio_allow_expensive_material_preview=bpy.props.BoolProperty(
        name="Compile material preview",default=False)
    for cls in _CLASSES:bpy.utils.register_class(cls)
    _INSTALLED=True

def installed():
    return _INSTALLED

def unregister():
    global _INSTALLED
    if _INSTALLED:
        for cls in reversed(_CLASSES):
            try:bpy.utils.unregister_class(cls)
            except RuntimeError:pass
    _INSTALLED=False
