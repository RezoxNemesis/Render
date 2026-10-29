# SPDX-License-Identifier: GPL-2.0-or-later
"""Phone-conscious native animation tools using the checkpointed public dispatcher.

Installing or opening this sidebar never changes scene geometry or render settings.
The Finish buttons hand off to Render's existing recoverable Android render queue.
"""
import os
import re
import textwrap
import uuid

import bpy
from bpy.app.handlers import persistent

_INSTALLED = False
_PROPERTIES = ()
_NOTICES = {}
_RESULTS = {}
_INSPECTIONS = {}
_FOCUS_ATTEMPTS = 0
_READ_ONLY = {"studio.animation.catalog", "studio.motion.audit", "studio.finish.inspect",
              "studio.keyframes.inspect"}


def _key(scene):
    return scene.as_pointer()


def _redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _notice(scene, message, error=False):
    _NOTICES[_key(scene)] = (message, error)
    _redraw()


def _error_text(error):
    code = str(error)
    known = {
        "ANIMATION_UI_SELECT_MESH": "Select a mesh in Object Mode first.",
        "ANIMATION_UI_SELECT_RIG": "Select the Motion Lab rig or one of its mesh parts.",
        "ANIMATION_UI_SELECT_LAYERS": "Select 2 to 32 layers at different depths.",
        "ANIMATION_UI_NO_ACTION": "Select an animated object, or choose an Action below.",
        "ANIMATION_UI_INSPECT_FIRST": "Inspect this action before changing its timing.",
        "ANIMATION_UI_SPOOL_NOT_READY": "Open Blender through Render Studio to enable saved checkpoints.",
        "ANIMATION_UI_RENDER_BUSY": "Wait for the active render before making another edit.",
        "ANIMATION_UI_PREFLIGHT_BLOCKED": "Resolve the render checks below before starting.",
        "ANIMATION_UI_OBJECT_MODE": "Switch to Object Mode before using animation tools.",
        "ANIMATION_UI_PREVIEW_RANGE": "Choose an ordered preview range of at most 10,000 frames.",
        "FINISH_MOTION_LAB_GROUP_RETIME_REQUIRED": "Motion Lab rig, IK controls and contacts must keep the same timing. Create a new clip with the desired frame range.",
        "CREATOR_NAME_EXISTS": "That name already exists. Choose a new name.",
        "ANIMATION_EXISTING_SHAPE_KEYS_PRESERVED": "This mesh already has shape keys. Edit its current keys in Blender.",
        "ANIMATION_PARALLAX_DISTINCT_DEPTH_REQUIRED": "Move the layers to different depths before creating parallax.",
        "ANIMATION_MORPH_EXISTING_SHAPE_KEYS": "This mesh already has shape keys. Use Blender's Shape Keys controls to edit them.",
    }
    if code in known:
        return known[code]
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,110}", code):
        for prefix in ("STUDIO_", "ANIMATION_UI_", "ANIMATION_", "MOTION_", "FINISH_"):
            code = code.removeprefix(prefix)
        return code.replace("_", " ").capitalize()
    return "The operation did not finish. Inspect its result in Agent Control."


def _execute(operation, payload):
    spool = os.environ.get("RENDER_AGENT_SPOOL")
    if not spool:
        raise ValueError("ANIMATION_UI_SPOOL_NOT_READY")
    if operation not in _READ_ONLY and bpy.app.is_job_running("RENDER"):
        raise ValueError("ANIMATION_UI_RENDER_BUSY")
    import render_production
    result = render_production.execute({"operation": operation, "payload": payload},
                                       spool, uuid.uuid4().hex)
    if not isinstance(result, dict):
        raise ValueError("ANIMATION_UI_RESULT_INVALID")
    return result


def _active(context, kind=None):
    obj = context.active_object
    if obj is None or kind and obj.type != kind:
        raise ValueError("ANIMATION_UI_SELECT_MESH")
    if obj.mode != "OBJECT":
        raise ValueError("ANIMATION_UI_OBJECT_MODE")
    return obj


def _rig(context):
    obj = context.active_object
    if obj is None:
        raise ValueError("ANIMATION_UI_SELECT_RIG")
    if obj.mode not in ("OBJECT", "POSE"):
        raise ValueError("ANIMATION_UI_OBJECT_MODE")
    if obj.type == "ARMATURE":
        return obj
    rig = obj.find_armature() if obj.type == "MESH" else None
    if rig is None and obj.parent is not None and obj.parent.type == "ARMATURE":
        rig = obj.parent
    if rig is None:
        raise ValueError("ANIMATION_UI_SELECT_RIG")
    return rig


def _action(context):
    scene = context.scene
    action = bpy.data.actions.get(scene.render_anim_action) if scene.render_anim_action else None
    if scene.render_anim_action and action is None:
        raise ValueError("ANIMATION_UI_NO_ACTION")
    if action is None and context.active_object is not None:
        obj = context.active_object
        data = getattr(obj, "animation_data", None)
        action = data.action if data else None
        if action is None and obj.type == "MESH" and obj.data.shape_keys is not None:
            data = obj.data.shape_keys.animation_data
            action = data.action if data else None
    if action is None:
        raise ValueError("ANIMATION_UI_NO_ACTION")
    return action


def _range(scene):
    return {"start": scene.render_anim_start, "end": scene.render_anim_end}


def _request(context, tool):
    s = context.scene
    if tool == "LAYER":
        return "studio.animation.layer.create", {
            "name": s.render_anim_layer_name, "shape": s.render_anim_layer_shape,
            "width": s.render_anim_width, "height": s.render_anim_height,
            "x": s.render_anim_x, "y": s.render_anim_y, "depth": s.render_anim_depth,
            "color": list(s.render_anim_color)}
    if tool == "PARALLAX":
        layers = sorted(obj.name for obj in context.selected_objects if obj.type == "MESH")
        if not 2 <= len(layers) <= 32:
            raise ValueError("ANIMATION_UI_SELECT_LAYERS")
        return "studio.animation.parallax.create", dict(_range(s),
            name=s.render_anim_camera_name, layers=layers, distance=s.render_anim_distance,
            travel_x=s.render_anim_travel_x, travel_y=s.render_anim_travel_y,
            lens_mm=s.render_anim_lens)
    if tool == "RIG":
        return "studio.motion.rig.create", {"name": s.render_anim_rig_name,
            "height": s.render_anim_rig_height, "origin": list(s.cursor.location)}
    if tool == "CLIP":
        return "studio.motion.clip.create", dict(_range(s), rig=_rig(context).name,
            preset=s.render_anim_clip, cycles=s.render_anim_cycles, stride=s.render_anim_stride)
    if tool == "AUDIT":
        return "studio.motion.audit", dict(_range(s), rig=_rig(context).name)
    if tool == "MORPH":
        return "studio.animation.morph.create", dict(_range(s), object=_active(context, "MESH").name,
            name=s.render_anim_morph_name, preset=s.render_anim_morph,
            amount=s.render_anim_amount, loop=s.render_anim_loop)
    if tool == "INSPECT_ACTION":
        return "studio.keyframes.inspect", {"action": _action(context).name}
    if tool == "RETIME":
        action = _action(context)
        inspected = _INSPECTIONS.get(_key(s), {})
        if inspected.get("action") != action.name or not inspected.get("revision_sha256"):
            raise ValueError("ANIMATION_UI_INSPECT_FIRST")
        return "studio.keyframes.retime", {"action": action.name,
            "expected_sha256": inspected["revision_sha256"], "scale": s.render_anim_time_scale,
            "offset": s.render_anim_time_offset, "pivot": s.render_anim_time_pivot}
    if tool == "PRESET":
        p = dict(_range(s), preset=s.render_anim_quality, fps=s.render_anim_fps,
                 engine=s.render_anim_engine)
        if s.render_anim_custom_size:
            p.update(width=s.render_anim_output_width, height=s.render_anim_output_height)
        return "studio.finish.preset", p
    if tool == "CHECK_RENDER":
        return "studio.finish.inspect", {}
    raise ValueError("ANIMATION_UI_TOOL_UNAVAILABLE")


def _select(context, name):
    obj = context.scene.objects.get(name) if isinstance(name, str) else None
    if obj is None or obj.name not in context.view_layer.objects:
        return
    if context.object is not None and context.object.mode != "OBJECT":
        return
    for selected in tuple(context.selected_objects):
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class RENDERSTUDIO_OT_animation_tool(bpy.types.Operator):
    bl_idname = "renderstudio.animation_tool"
    bl_label = "Animation Studio Tool"
    bl_description = "Run the native animation tool with a saved checkpoint before changes"
    tool: bpy.props.EnumProperty(items=[(v, v.replace("_", " ").title(), "") for v in (
        "LAYER", "PARALLAX", "RIG", "CLIP", "AUDIT", "MORPH", "INSPECT_ACTION",
        "RETIME", "PRESET", "CHECK_RENDER")])

    def execute(self, context):
        scene = context.scene
        try:
            operation, payload = _request(context, self.tool)
            result = _execute(operation, payload)
            _RESULTS.setdefault(_key(scene), {})[self.tool] = result
            if self.tool == "INSPECT_ACTION":
                _INSPECTIONS[_key(scene)] = result
                message = "Action inspected. Review its range, then adjust timing."
            elif self.tool == "RETIME":
                _INSPECTIONS.pop(_key(scene), None)
                message = "Keyframe timing updated. Inspect again before another timing edit."
            elif self.tool == "AUDIT":
                message = "Movement check: " + str(result.get("quality_gate", "INCOMPLETE"))
            elif self.tool == "CHECK_RENDER":
                message = "Render checks passed." if result.get("ready") else "Render needs attention below."
            elif self.tool == "PRESET":
                _RESULTS[_key(scene)]["CHECK_RENDER"] = result.get("preflight", {})
                message = "Output settings applied. Check the scene before rendering."
            elif self.tool == "CLIP":
                message = "Editable motion created. Run Check Movement to inspect it."
            else:
                message = {"LAYER": "Editable color layer created.",
                           "PARALLAX": "Camera motion created across the selected depths.",
                           "RIG": "Articulated mannequin created with leg IK controls.",
                           "MORPH": "Shape keys and their animation created."}[self.tool]
            if self.tool == "LAYER":
                _select(context, payload["name"])
            elif self.tool == "RIG":
                _select(context, result.get("rig"))
            _notice(scene, message)
            self.report({"INFO"}, message)
            return {"FINISHED"}
        except Exception as error:
            message = _error_text(error)
            _notice(scene, message, True)
            self.report({"ERROR"}, message)
            return {"CANCELLED"}


class RENDERSTUDIO_OT_animation_render(bpy.types.Operator):
    bl_idname = "renderstudio.animation_render"
    bl_label = "Start Recoverable Render"
    bl_description = "Check the current scene and queue it in Render's existing Android renderer"
    kind: bpy.props.EnumProperty(items=[("STILL", "Preview Current Frame", ""),
                                        ("ANIMATION", "Render Animation", ""),
                                        ("RESUME", "Resume Last Render", "")])

    def execute(self, context):
        try:
            if bpy.app.is_job_running("RENDER"):
                raise ValueError("ANIMATION_UI_RENDER_BUSY")
            if self.kind != "RESUME":
                result = _execute("studio.finish.inspect", {})
                _RESULTS.setdefault(_key(context.scene), {})["CHECK_RENDER"] = result
                if not result.get("ready"):
                    raise ValueError("ANIMATION_UI_PREFLIGHT_BLOCKED")
            import render_session_tools
            result = render_session_tools.queue_manual_render(
                resume=self.kind == "RESUME", still=self.kind == "STILL")
            if not isinstance(result, dict) or not result.get("job_id"):
                raise ValueError("ANIMATION_UI_RENDER_RECEIPT_INVALID")
            _RESULTS.setdefault(_key(context.scene), {})["RENDER"] = result
            message = "Render queued. Open Render Jobs for progress and MP4 export."
            _notice(context.scene, message)
            self.report({"INFO"}, message)
            return {"FINISHED"}
        except Exception as error:
            message = _error_text(error)
            _notice(context.scene, message, True)
            self.report({"ERROR"}, message)
            return {"CANCELLED"}


class RENDERSTUDIO_OT_animation_open(bpy.types.Operator):
    bl_idname = "renderstudio.animation_open"
    bl_label = "Open Animation Studio"
    bl_description = "Open the Animate sidebar without changing the project"

    def execute(self, context):
        result = open_animation_workspace()
        return {"FINISHED"} if result["animation_sidebar_opened"] else {"CANCELLED"}


class RENDERSTUDIO_OT_animation_preview(bpy.types.Operator):
    bl_idname = "renderstudio.animation_preview"
    bl_label = "Preview Animation Range"
    bl_description = "Play the chosen frame range using Blender's native timeline preview"

    def execute(self, context):
        try:
            if bpy.app.is_job_running("RENDER"):
                raise ValueError("ANIMATION_UI_RENDER_BUSY")
            if context.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
                return {"FINISHED"}
            start, end = context.scene.render_anim_start, context.scene.render_anim_end
            if not 0 <= end - start <= 10000:
                raise ValueError("ANIMATION_UI_PREVIEW_RANGE")
            context.scene.frame_preview_start = start
            context.scene.frame_preview_end = end
            context.scene.use_preview_range = True
            context.scene.frame_set(start)
            bpy.ops.screen.animation_play()
            return {"FINISHED"}
        except Exception as error:
            message = _error_text(error)
            _notice(context.scene, message, True)
            self.report({"ERROR"}, message)
            return {"CANCELLED"}


def _wrap(layout, text, icon="NONE"):
    for index, line in enumerate(textwrap.wrap(str(text), width=36) or [""]):
        layout.label(text=line, icon=icon if index == 0 else "NONE")


def _button(layout, tool, text, icon="NONE"):
    layout.operator("renderstudio.animation_tool", text=text, icon=icon).tool = tool


def _draw_layers(layout, scene):
    box = layout.box()
    box.label(text="2D · Color cutouts", icon="OUTLINER_OB_MESH")
    box.prop(scene, "render_anim_layer_name", text="Name")
    box.prop(scene, "render_anim_layer_shape", text="Shape")
    row = box.row(align=True)
    row.prop(scene, "render_anim_width", text="Width")
    row.prop(scene, "render_anim_height", text="Height")
    row = box.row(align=True)
    row.prop(scene, "render_anim_x", text="X")
    row.prop(scene, "render_anim_y", text="Y")
    box.prop(scene, "render_anim_depth", text="Depth")
    box.prop(scene, "render_anim_color", text="Color")
    _button(box, "LAYER", "Create Layer", "ADD")
    _wrap(box, "Edit each outline in Blender Edit Mode. Positive depth is closer to the camera.")
    box = layout.box()
    box.label(text="2.5D · Parallax camera", icon="OUTLINER_OB_CAMERA")
    _wrap(box, "Select 2–32 layers at different depths.")
    box.prop(scene, "render_anim_camera_name", text="Name")
    row = box.row(align=True)
    row.prop(scene, "render_anim_travel_x", text="Move X")
    row.prop(scene, "render_anim_travel_y", text="Move Y")
    box.prop(scene, "render_anim_distance", text="Distance")
    box.prop(scene, "render_anim_lens", text="Lens")
    _button(box, "PARALLAX", "Animate Selected Layers", "CAMERA_DATA")


def _draw_character(layout, context):
    scene = context.scene
    box = layout.box()
    box.label(text="Character starter", icon="ARMATURE_DATA")
    box.prop(scene, "render_anim_rig_name", text="Name")
    box.prop(scene, "render_anim_rig_height", text="Height")
    _button(box, "RIG", "Create Mannequin at Cursor", "ADD")
    _wrap(box, "An articulated mannequin for motion blocking. Refine anatomy and skin weights for a finished character.")
    box = layout.box()
    box.label(text="Editable motion", icon="ACTION")
    box.prop(scene, "render_anim_clip", text="Motion")
    box.prop(scene, "render_anim_cycles", text="Cycles")
    if scene.render_anim_clip == "walk":
        box.prop(scene, "render_anim_stride", text="Stride / Height")
    _button(box, "CLIP", "Create Clip on Selected Rig", "KEY_HLT")
    _button(box, "AUDIT", "Check Movement", "CHECKMARK")
    audit = _RESULTS.get(_key(scene), {}).get("AUDIT")
    if audit:
        box.separator()
        _wrap(box, "Rig: " + str(audit.get("rig", "")))
        box.label(text="Check: " + str(audit.get("quality_gate", "INCOMPLETE")))
        box.label(text="Issues: " + str(audit.get("issue_count", 0)))
        box.label(text="Sampled frames: " + str(audit.get("samples", 0)))
        for issue in audit.get("issues", [])[:5]:
            code = issue.get("message") or issue.get("code") or issue.get("kind", "Review motion")
            _wrap(box, str(code).replace("_", " ").capitalize(), "ERROR")
        if audit.get("quality_gate") == "INCOMPLETE":
            _wrap(box, "Contact and joint mappings are needed for a complete check of an imported rig.")
        _wrap(box, "Sampled checks do not replace visual review of the full performance.")


def _draw_time(layout, context):
    scene = context.scene
    box = layout.box()
    box.label(text="Morph · Shape over time", icon="SHAPEKEY_DATA")
    box.prop(scene, "render_anim_morph_name", text="Shape Key")
    box.prop(scene, "render_anim_morph", text="Motion")
    box.prop(scene, "render_anim_amount", text="Strength")
    box.prop(scene, "render_anim_loop", text="Loop")
    _button(box, "MORPH", "Animate Selected Mesh Shape", "KEY_HLT")
    _wrap(box, "Use a mesh with interior vertices along its height. Existing shape keys are preserved by refusing a replacement.")
    box = layout.box()
    box.label(text="Keyframe timing", icon="TIME")
    box.prop_search(scene, "render_anim_action", bpy.data, "actions", text="Action")
    _wrap(box, "Leave Action empty to use the selected object's active action or shape-key animation.")
    _button(box, "INSPECT_ACTION", "Inspect Action", "VIEWZOOM")
    inspected = _INSPECTIONS.get(_key(scene))
    if inspected:
        _wrap(box, inspected.get("action", "Action"))
        frame_range = inspected.get("frame_range", [])
        if len(frame_range) == 2:
            box.label(text="Frames: %.2f – %.2f" % tuple(frame_range))
        for blocker in inspected.get("retime_blockers", [])[:3]:
            _wrap(box, str(blocker).replace("_", " ").capitalize(), "ERROR")
    box.prop(scene, "render_anim_time_scale", text="Duration Scale")
    row = box.row(align=True)
    row.prop(scene, "render_anim_time_pivot", text="Pivot")
    row.prop(scene, "render_anim_time_offset", text="Offset")
    row = box.row()
    row.enabled = bool(inspected and not inspected.get("retime_blockers"))
    _button(row, "RETIME", "Apply Timing", "TIME")
    _wrap(box, "2× doubles the duration; 0.5× halves it. Shared or NLA-linked actions require separate editing.")


def _draw_finish(layout, context):
    scene = context.scene
    box = layout.box()
    box.label(text="1 · Output", icon="OUTPUT")
    box.prop(scene, "render_anim_quality", text="Quality")
    box.prop(scene, "render_anim_engine", text="Renderer")
    box.prop(scene, "render_anim_fps", text="FPS")
    box.prop(scene, "render_anim_custom_size", text="Custom Size")
    if scene.render_anim_custom_size:
        row = box.row(align=True)
        row.prop(scene, "render_anim_output_width", text="Width")
        row.prop(scene, "render_anim_output_height", text="Height")
    _button(box, "PRESET", "Apply Output Settings", "CHECKMARK")
    box = layout.box()
    box.label(text="2 · Check scene", icon="VIEWZOOM")
    _button(box, "CHECK_RENDER", "Check Before Rendering", "VIEWZOOM")
    report = _RESULTS.get(_key(scene), {}).get("CHECK_RENDER")
    if report:
        box.label(text="Ready" if report.get("ready") else "Needs attention",
                  icon="CHECKMARK" if report.get("ready") else "ERROR")
        settings = report.get("effective_settings", report.get("settings", {}))
        if settings.get("width") and settings.get("height"):
            percentage = settings.get("percentage", 100)
            width = int(settings["width"] * percentage // 100)
            height = int(settings["height"] * percentage // 100)
            fps = settings.get("fps", 0) / max(settings.get("fps_base", 1), 1e-9)
            box.label(text="%s × %s · %.2f FPS" % (width, height, fps))
        frames = report.get("range", {})
        if "frames" in frames:
            box.label(text="%s frames · %.1f seconds" % (frames["frames"], frames.get("duration_seconds", 0)))
        for issue in (report.get("blockers", []) + report.get("warnings", []))[:6]:
            _wrap(box, issue.get("message", issue.get("code", "Review render settings")), "INFO")
        _wrap(box, "Checks refresh when you start rendering.")
    box = layout.box()
    box.label(text="3 · Render & recover", icon="RENDER_ANIMATION")
    box.operator("renderstudio.animation_render", text="Preview Current Frame", icon="RENDER_STILL").kind = "STILL"
    box.operator("renderstudio.animation_render", text="Render Animation", icon="RENDER_ANIMATION").kind = "ANIMATION"
    box.operator("renderstudio.animation_render", text="Resume Last Render", icon="FILE_REFRESH").kind = "RESUME"
    _wrap(box, "Follow progress, resume frames and save the MP4 in Render Jobs on the Android home screen.")


class RENDERSTUDIO_PT_animation(bpy.types.Panel):
    bl_label = "Animation Studio"
    bl_idname = "RENDERSTUDIO_PT_animation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Animate"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.use_property_split = False
        layout.prop(scene, "render_anim_mode", text="Workspace")
        row = layout.row(align=True)
        row.prop(scene, "render_anim_start", text="From")
        row.prop(scene, "render_anim_end", text="To")
        notice = _NOTICES.get(_key(scene))
        if notice:
            box = layout.box()
            box.alert = notice[1]
            _wrap(box, notice[0], "ERROR" if notice[1] else "INFO")
        if scene.render_anim_mode == "LAYERS":
            _draw_layers(layout, scene)
        elif scene.render_anim_mode == "CHARACTER":
            _draw_character(layout, context)
        elif scene.render_anim_mode == "TIME":
            _draw_time(layout, context)
        else:
            _draw_finish(layout, context)
        layout.separator()
        row = layout.row(align=True)
        row.prop(scene, "frame_current", text="Frame")
        row.operator("renderstudio.animation_preview", text="Pause" if context.screen.is_animation_playing else "Preview Range",
                     icon="PAUSE" if context.screen.is_animation_playing else "PLAY")
        layout.label(text="Native preview; export range is set in Finish.")


class RENDERSTUDIO_MT_animation(bpy.types.Menu):
    bl_label = "Animation Studio"
    bl_idname = "RENDERSTUDIO_MT_animation"

    def draw(self, context):
        self.layout.operator("renderstudio.animation_open", icon="ACTION")
        self.layout.operator("renderstudio.animation_tool", text="Check Movement", icon="CHECKMARK").tool = "AUDIT"
        self.layout.operator("renderstudio.animation_tool", text="Check Render", icon="VIEWZOOM").tool = "CHECK_RENDER"


def _menu(self, context):
    self.layout.menu("RENDERSTUDIO_MT_animation", text="Animate")


def open_animation_workspace():
    global _FOCUS_ATTEMPTS
    if not _INSTALLED:
        install()
    changed = selected = 0
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.spaces.active.show_region_ui = True
            for region in area.regions:
                if region.type == "UI" and hasattr(region, "active_panel_category"):
                    try:
                        region.active_panel_category = "Animate"
                        selected += region.active_panel_category == "Animate"
                    except (AttributeError, TypeError, RuntimeError):
                        pass
            area.tag_redraw()
            changed += 1
    if changed and selected == changed:
        _FOCUS_ATTEMPTS = -1
    elif changed and not bpy.app.timers.is_registered(_startup_focus):
        _FOCUS_ATTEMPTS = 0
        bpy.app.timers.register(_startup_focus, first_interval=.3)
    return {"animation_sidebar_opened": changed > 0, "native_viewports": changed,
            "animation_category_selected": changed > 0 and selected == changed,
            "scene_reset": False, "scene_geometry_changed": False}


def _startup_focus():
    global _FOCUS_ATTEMPTS
    if not _INSTALLED or _FOCUS_ATTEMPTS < 0:
        return None
    _FOCUS_ATTEMPTS += 1
    result = open_animation_workspace()
    if not result["animation_category_selected"] and _FOCUS_ATTEMPTS < 6:
        return .5
    return None


@persistent
def _loaded(unused):
    _NOTICES.clear()
    _RESULTS.clear()
    _INSPECTIONS.clear()


_CLASSES = (RENDERSTUDIO_OT_animation_tool, RENDERSTUDIO_OT_animation_render,
            RENDERSTUDIO_OT_animation_open, RENDERSTUDIO_OT_animation_preview, RENDERSTUDIO_PT_animation,
            RENDERSTUDIO_MT_animation)


def install():
    global _INSTALLED, _PROPERTIES, _FOCUS_ATTEMPTS
    if bpy.app.background or _INSTALLED:
        return
    P = bpy.props
    enum = lambda values, default: P.EnumProperty(items=[(v, label, "") for v, label in values], default=default)
    name = lambda value: P.StringProperty(default=value, maxlen=64)
    props = {
        "mode": enum([("LAYERS", "2D / 2.5D Layers"), ("CHARACTER", "Character & Motion"),
                      ("TIME", "Morph & Keyframes"), ("FINISH", "Render & Finish")], "LAYERS"),
        "start": P.IntProperty(default=1, min=1, max=100000),
        "end": P.IntProperty(default=49, min=3, max=100000),
        "layer_name": name("AnimationLayer"),
        "layer_shape": enum([("rectangle", "Rectangle"), ("ellipse", "Ellipse")], "rectangle"),
        "width": P.FloatProperty(default=4, min=.01, max=100, soft_max=20),
        "height": P.FloatProperty(default=3, min=.01, max=100, soft_max=20),
        "x": P.FloatProperty(default=0, min=-1000, max=1000, soft_min=-10, soft_max=10),
        "y": P.FloatProperty(default=0, min=-1000, max=1000, soft_min=-10, soft_max=10),
        "depth": P.FloatProperty(default=0, min=-100, max=100, soft_min=-10, soft_max=10),
        "color": P.FloatVectorProperty(default=(.3, .55, .8), size=3, min=0, max=1, subtype="COLOR"),
        "camera_name": name("ParallaxCamera"),
        "distance": P.FloatProperty(default=20, min=.1, max=1000, soft_max=100),
        "travel_x": P.FloatProperty(default=2, min=-100, max=100, soft_min=-10, soft_max=10),
        "travel_y": P.FloatProperty(default=0, min=-100, max=100, soft_min=-10, soft_max=10),
        "lens": P.FloatProperty(default=50, min=10, max=200),
        "rig_name": P.StringProperty(default="MotionActor", maxlen=48),
        "rig_height": P.FloatProperty(default=1.8, min=.5, max=4, unit="LENGTH"),
        "clip": enum([("walk", "Walk"), ("idle", "Idle"), ("squat", "Squat")], "walk"),
        "cycles": P.IntProperty(default=1, min=1, max=4),
        "stride": P.FloatProperty(default=.4, min=.05, max=.6),
        "morph_name": name("Breathe"),
        "morph": enum([("breathe", "Breathe"), ("twist", "Twist"), ("wave", "Wave")], "breathe"),
        "amount": P.FloatProperty(default=.1, min=.001, max=1),
        "loop": P.BoolProperty(default=True),
        "action": P.StringProperty(default="", maxlen=128),
        "time_scale": P.FloatProperty(default=1, min=.05, max=20, soft_max=4),
        "time_offset": P.FloatProperty(default=0, min=-100000, max=100000, soft_min=-100, soft_max=100),
        "time_pivot": P.FloatProperty(default=1, min=0, max=100000, soft_max=1000),
        "quality": enum([("draft", "Draft · 480p"), ("standard", "Standard · 720p"), ("final", "Final · 1080p")], "standard"),
        "engine": enum([("keep", "Keep current"), ("CYCLES", "Cycles")], "keep"),
        "fps": P.IntProperty(default=24, min=1, max=120),
        "custom_size": P.BoolProperty(default=False),
        "output_width": P.IntProperty(default=1280, min=16, max=8192, step=2),
        "output_height": P.IntProperty(default=720, min=16, max=8192, step=2),
    }
    _PROPERTIES = tuple("render_anim_" + key for key in props)
    registered = []
    menu_added = False
    try:
        for key, prop in props.items():
            setattr(bpy.types.Scene, "render_anim_" + key, prop)
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.VIEW3D_MT_editor_menus.append(_menu)
        menu_added = True
        if _loaded not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_loaded)
        _INSTALLED = True
        if os.environ.get("RENDER_ANIMATION_FOCUS") == "1":
            _FOCUS_ATTEMPTS = 0
            bpy.app.timers.register(_startup_focus, first_interval=5.0)
    except Exception:
        if bpy.app.timers.is_registered(_startup_focus):
            bpy.app.timers.unregister(_startup_focus)
        if _loaded in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_loaded)
        if menu_added:
            bpy.types.VIEW3D_MT_editor_menus.remove(_menu)
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
        for key in _PROPERTIES:
            if hasattr(bpy.types.Scene, key):
                delattr(bpy.types.Scene, key)
        _INSTALLED = False
        raise


def installed():
    return _INSTALLED


def uninstall():
    global _INSTALLED
    if not _INSTALLED:
        return
    _INSTALLED = False
    if bpy.app.timers.is_registered(_startup_focus):
        bpy.app.timers.unregister(_startup_focus)
    if _loaded in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_loaded)
    bpy.types.VIEW3D_MT_editor_menus.remove(_menu)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    for key in _PROPERTIES:
        if hasattr(bpy.types.Scene, key):
            delattr(bpy.types.Scene, key)
    _loaded(None)
