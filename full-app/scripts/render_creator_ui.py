# SPDX-License-Identifier: GPL-2.0-or-later
"""Native Blender Creator tools and reviewed local recipes.

The controls call the same checkpointed production route as ChatGPT. Recipes
are explicitly deterministic local guidance; no prompt is sent to an AI model.
This module changes no scene at install time and never resets an existing scene.
"""
import json
import os
import re
import textwrap
import uuid

import bpy
from bpy.app.handlers import persistent

_INSTALLED = False
_PREVIEWS = {}
_JOBS = {}
_NOTICES = {}
_FOCUS_ATTEMPTS = 0
_RECIPE_ROWS = (
    ("asset", "Wooden crate", "wooden crate asset", "One editable prop with a material"),
    ("product_scene", "Product scene", "product scene with ceramic barrel", "A prop and presentation camera"),
    ("forest", "Forest world", "forest environment", "Terrain and linked trees"),
    ("island", "Island world", "island environment", "A procedural island landscape"),
    ("mountains", "Mountain world", "mountain environment", "A procedural mountain landscape"),
    ("dunes", "Dune world", "dunes environment", "A procedural dune landscape"),
    ("plains", "Open plains", "plains environment", "A procedural plains landscape"),
    ("animated_prop", "Animated prop", "animated metal barrel bounce", "An editable asset with motion keys"),
    ("studio_turntable", "Studio turntable", "studio turntable with wooden crate", "An asset and orbiting camera"),
    ("flexible_rig", "Flexible rig starter", "flexible rig starter", "A mesh with a segmented starter rig"),
)
_RECIPES = {row[0]: row for row in _RECIPE_ROWS}
_TOOL_LABELS = {
    "MODEL": "Model", "TERRAIN": "Terrain", "SCATTER": "Scatter",
    "MATERIAL": "Material", "MOTION": "Motion", "CAMERA": "Camera", "RIG": "Rig",
}
_ACTIVE_STATES = {"queued", "running", "paused", "needs_review"}


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
    # The local recipe parser exposes a static code separately from recovery
    # text. Never echo an owner-entered brief to construct an error message.
    code = getattr(error, "code", None)
    if not isinstance(code, str):
        code = str(error)
    known = {
        "CREATOR_PREVIEW_REQUIRED": "Preview this recipe again before creating it.",
        "CREATOR_PREVIEW_NOT_READY": "Resolve the preview issues before creating this recipe.",
        "STUDIO_COMMAND_PREVIEW_STALE": "The scene or plan changed. Preview again to review the current steps.",
        "STUDIO_COMMAND_UNSUPPORTED_BRIEF": "This wording is not a built-in recipe. Choose a recipe above, or connect ChatGPT for a custom request.",
        "STUDIO_COMMAND_AMBIGUOUS_BRIEF": "Choose one recipe at a time, then preview again.",
        "STUDIO_COMMAND_BRIEF_INVALID": "Use a short local recipe phrase, or choose a recipe from Start with.",
        "CREATOR_SELECT_MESH": "Select an editable mesh in the viewport first.",
        "CREATOR_SELECT_OBJECT": "Select an object in the viewport first.",
        "CREATOR_OBJECT_MODE_REQUIRED": "Switch to Object Mode before using Creator tools.",
        "CREATOR_SPOOL_NOT_READY": "Open Blender through Render to enable checkpoints and creation.",
        "CREATOR_NATIVE_RENDER_BUSY": "A native render is running. Wait or pause it before creating.",
        "CREATOR_PLAN_REQUIRED": "Create a recipe or load the most recent plan first.",
        "OBJECT_NAME_EXISTS": "That object name already exists. Choose a different name.",
        "CREATOR_NAME_EXISTS": "That object name already exists. Choose a different name.",
        "CREATOR_EXISTING_ANIMATION_PRESERVED": "This object already has animation. Refine it in Blender or choose another object.",
        "CREATOR_EXISTING_ARMATURE_PRESERVED": "This mesh already has a rig. Refine its existing armature in Blender.",
        "STUDIO_PLAN_QUEUE_FULL": "The plan queue is full. Finish or cancel a plan before adding another.",
        "STUDIO_PLAN_REQUIRES_INSPECTION": "This interrupted plan needs inspection before any retry.",
        "CREATOR_RESULT_INVALID": "The native result could not be verified. Inspect Agent Control before retrying.",
    }
    if code in known:
        return known[code]
    # Exceptions can contain filesystem paths or identifiers. Show only bounded
    # contract error codes, never arbitrary exception text in this UI.
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,110}", code):
        return code.replace("STUDIO_", "").replace("CREATOR_", "").replace("_", " ").capitalize()
    return "The native operation did not finish. Inspect its result in Agent Control."


def _failure(operator, scene, error):
    message = _error_text(error)
    _notice(scene, message, True)
    operator.report({"ERROR"}, message)
    return {"CANCELLED"}


def _execute(operation, payload):
    spool = os.environ.get("RENDER_AGENT_SPOOL")
    if not spool:
        raise ValueError("CREATOR_SPOOL_NOT_READY")
    if operation.startswith("studio.create.") or operation == "studio.command.submit":
        if bpy.app.is_job_running("RENDER"):
            raise ValueError("CREATOR_NATIVE_RENDER_BUSY")
    import render_production
    result = render_production.execute({"operation": operation, "payload": payload}, spool, uuid.uuid4().hex)
    if not isinstance(result, dict):
        raise ValueError("CREATOR_RESULT_INVALID")
    return result


def _request(scene):
    return {"brief": scene.render_creator_brief, "name": scene.render_creator_recipe_name,
            "seed": scene.render_creator_seed, "quality": scene.render_creator_quality}


def _changed(scene, context):
    _PREVIEWS.pop(_key(scene), None)


def _recipe_changed(scene, context):
    row = _RECIPES.get(scene.render_creator_recipe)
    if row:
        scene.render_creator_brief = row[2]
    _changed(scene, context)


def _active(context, mesh=False):
    obj = context.active_object
    if obj is None or (mesh and obj.type != "MESH"):
        raise ValueError("CREATOR_SELECT_MESH" if mesh else "CREATOR_SELECT_OBJECT")
    if obj.mode != "OBJECT":
        raise ValueError("CREATOR_OBJECT_MODE_REQUIRED")
    return obj


def _tool_request(context, tool):
    scene = context.scene
    if context.object is not None and context.object.mode != "OBJECT":
        raise ValueError("CREATOR_OBJECT_MODE_REQUIRED")
    if tool == "MODEL":
        p = {"name": scene.render_creator_model_name, "kind": scene.render_creator_model_kind,
             "size": scene.render_creator_model_size, "detail": int(scene.render_creator_detail),
             "seed": scene.render_creator_seed}
    elif tool == "TERRAIN":
        p = {"name": scene.render_creator_terrain_name, "style": scene.render_creator_terrain_style,
             "size": scene.render_creator_terrain_size, "resolution": scene.render_creator_resolution,
             "height": scene.render_creator_height, "seed": scene.render_creator_seed}
    elif tool == "SCATTER":
        p = {"name": scene.render_creator_scatter_name, "source": _active(context, True).name,
             "count": scene.render_creator_count, "extent": scene.render_creator_extent,
             "seed": scene.render_creator_seed, "min_scale": scene.render_creator_min_scale,
             "max_scale": scene.render_creator_max_scale}
        terrain = scene.render_creator_scatter_terrain
        if terrain is not None:
            p["terrain"] = terrain.name
    elif tool == "MATERIAL":
        p = {"object": _active(context, True).name, "preset": scene.render_creator_material,
             "scale": scene.render_creator_texture_scale}
        if scene.render_creator_custom_color:
            p["color"] = list(scene.render_creator_color)
    elif tool == "MOTION":
        p = {"object": _active(context).name, "preset": scene.render_creator_motion,
             "start": scene.render_creator_start, "end": scene.render_creator_end,
             "amount": scene.render_creator_motion_amount, "loop": scene.render_creator_loop}
    elif tool == "CAMERA":
        p = {"name": scene.render_creator_camera_name, "target": _active(context).name,
             "preset": scene.render_creator_camera, "radius": scene.render_creator_radius,
             "start": scene.render_creator_start, "end": scene.render_creator_end}
    elif tool == "RIG":
        p = {"object": _active(context, True).name, "name": scene.render_creator_rig_name,
             "segments": scene.render_creator_segments}
    else:
        raise ValueError("CREATOR_TOOL_UNAVAILABLE")
    return "studio.create." + tool.lower(), p


def _focus_object(context, name):
    obj = context.scene.objects.get(name) if isinstance(name, str) else None
    if obj is None or obj.name not in context.view_layer.objects:
        return
    # This is viewport navigation after a verified edit, not a generated scene.
    for selected in tuple(context.selected_objects):
        selected.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    for area in context.window.screen.areas if context.window else ():
        if area.type == "VIEW_3D":
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            if region:
                try:
                    with context.temp_override(area=area, region=region):
                        bpy.ops.view3d.view_selected(use_all_regions=False)
                except (RuntimeError, TypeError):
                    pass


def open_creator_workspace():
    """Open the real sidebar without replacing screens, data or scene settings."""
    global _FOCUS_ATTEMPTS
    if not _INSTALLED:
        install()
    changed = selected = 0
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.spaces.active.show_region_ui = True
            # Supported on newer Blender versions. The visible Creator menu is
            # also installed, so earlier builds retain an explicit entry point.
            for region in area.regions:
                if region.type == "UI" and hasattr(region, "active_panel_category"):
                    try:
                        region.active_panel_category = "Create"
                        if region.active_panel_category == "Create":
                            selected += 1
                    except (AttributeError, TypeError, RuntimeError):
                        pass
            area.tag_redraw()
            changed += 1
    if changed and selected == changed:
        # A pending retry must not pull the owner back after they switch tabs.
        _FOCUS_ATTEMPTS = -1
    elif changed:
        if _FOCUS_ATTEMPTS < 0:
            _FOCUS_ATTEMPTS = 0
        if not bpy.app.timers.is_registered(_startup_focus):
            _FOCUS_ATTEMPTS = 0
            bpy.app.timers.register(_startup_focus, first_interval=.3)
    return {"creator_sidebar_opened": changed > 0, "native_viewports": changed,
            "creator_category_selected": changed > 0 and selected == changed,
            "scene_reset": False, "scene_geometry_changed": False}


def _startup_focus():
    global _FOCUS_ATTEMPTS
    if not _INSTALLED or _FOCUS_ATTEMPTS < 0:
        return None
    _FOCUS_ATTEMPTS += 1
    result = open_creator_workspace()
    # A hidden sidebar materializes its panel categories on the next redraw.
    # Stop as soon as selected; do not override a later owner tab change.
    if not result["creator_category_selected"] and _FOCUS_ATTEMPTS < 6:
        return .5
    return None


def _poll_jobs():
    if not _INSTALLED:
        return None
    active = False
    for key, job in tuple(_JOBS.items()):
        if job.get("state") not in _ACTIVE_STATES or not job.get("plan_id"):
            continue
        active = True
        try:
            _JOBS[key] = _execute("studio.plan.status", {"plan_id": job["plan_id"]})
        except (ValueError, RuntimeError, OSError, AttributeError):
            _NOTICES[key] = ("Plan progress is unavailable. Refresh the queue to inspect its saved state.", True)
    if active:
        _redraw()
    return 2.0 if active else 8.0


@persistent
def _loaded(unused):
    _PREVIEWS.clear()
    _JOBS.clear()
    _NOTICES.clear()


class RENDERSTUDIO_OT_creator_open(bpy.types.Operator):
    bl_idname = "renderstudio.creator_open"
    bl_label = "Open Creator Workspace"
    bl_description = "Open native creation tools while keeping your current scene"

    def execute(self, context):
        result = open_creator_workspace()
        if not result["creator_sidebar_opened"]:
            return _failure(self, context.scene, ValueError("STUDIO_NATIVE_VIEWPORT_NOT_OPEN"))
        return {"FINISHED"}


class RENDERSTUDIO_OT_creator_preview(bpy.types.Operator):
    bl_idname = "renderstudio.creator_preview"
    bl_label = "Preview Recipe"
    bl_description = "Review the native operations and check names before a local recipe is queued"

    def execute(self, context):
        scene = context.scene
        _PREVIEWS.pop(_key(scene), None)
        try:
            request = _request(scene)
            result = _execute("studio.command.preview", request)
            if not isinstance(result.get("steps"), list) or not re.fullmatch(
                    r"[0-9a-f]{64}", result.get("preview_sha256", "")):
                raise ValueError("CREATOR_RESULT_INVALID")
            _PREVIEWS[_key(scene)] = {"request": request, "result": result}
            ready = result.get("ready_to_submit") is True
            _notice(scene, "Preview ready. Review the steps, then create." if ready else
                    "Preview needs changes. Review the issues below.", not ready)
            return {"FINISHED"}
        except (ValueError, RuntimeError, OSError, AttributeError, TypeError) as error:
            return _failure(self, scene, error)


class RENDERSTUDIO_OT_creator_apply(bpy.types.Operator):
    bl_idname = "renderstudio.creator_apply"
    bl_label = "Create Reviewed Recipe"
    bl_description = "Queue only the exact recipe preview you reviewed, with checkpoints before each edit"

    def execute(self, context):
        scene = context.scene
        try:
            preview = _PREVIEWS.get(_key(scene))
            if preview is None or preview["request"] != _request(scene):
                raise ValueError("CREATOR_PREVIEW_REQUIRED")
            if not preview["result"].get("ready_to_submit"):
                raise ValueError("CREATOR_PREVIEW_NOT_READY")
            request = dict(preview["request"], preview_sha256=preview["result"]["preview_sha256"])
            result = _execute("studio.command.submit", request)
            if not result.get("plan_id") or "state" not in result:
                raise ValueError("CREATOR_RESULT_INVALID")
            _JOBS[_key(scene)] = result
            _PREVIEWS.pop(_key(scene), None)
            _notice(scene, "Recipe " + str(result["state"]).replace("_", " ") +
                    ". Native steps and saved progress appear below.")
            return {"FINISHED"}
        except (ValueError, RuntimeError, OSError, AttributeError, TypeError) as error:
            _PREVIEWS.pop(_key(scene), None)
            return _failure(self, scene, error)


class RENDERSTUDIO_OT_creator_tool(bpy.types.Operator):
    bl_idname = "renderstudio.creator_tool"
    bl_label = "Run Creator Tool"
    bl_description = "Run one real Blender operation with a source checkpoint"
    tool: bpy.props.EnumProperty(items=[(key, value, "") for key, value in _TOOL_LABELS.items()])

    def execute(self, context):
        try:
            operation, payload = _tool_request(context, self.tool)
            result = _execute(operation, payload)
            name = result.get("object", payload.get("name", payload.get("object", "")))
            if self.tool in {"MODEL", "TERRAIN", "SCATTER", "CAMERA", "RIG"}:
                _focus_object(context, name)
            saved = " · source checkpoint saved" if result.get("checkpoint_before_change") else ""
            _notice(context.scene, _TOOL_LABELS[self.tool] + " applied: " + str(name)[:64] + saved)
            _PREVIEWS.pop(_key(context.scene), None)
            return {"FINISHED"}
        except (ValueError, RuntimeError, OSError, AttributeError, TypeError) as error:
            return _failure(self, context.scene, error)


class RENDERSTUDIO_OT_creator_plan_control(bpy.types.Operator):
    bl_idname = "renderstudio.creator_plan_control"
    bl_label = "Creation Progress"
    bl_description = "Read or control the actual native plan queue"
    action: bpy.props.EnumProperty(items=[("refresh", "Refresh", "Read the saved state"),
        ("recent", "Load Recent Plan", "Inspect the most recent native plan"),
        ("pause", "Pause", "Pause before the next native step"),
        ("resume", "Resume", "Continue a safely paused plan"),
        ("cancel", "Cancel Remaining", "Keep completed edits and stop remaining steps")])

    def execute(self, context):
        scene = context.scene
        try:
            if self.action == "recent":
                jobs = _execute("studio.plan.list", {}).get("jobs", [])
                if not jobs:
                    _notice(scene, "No native creation plans have been saved yet.")
                    return {"FINISHED"}
                _JOBS[_key(scene)] = jobs[0]
            else:
                job = _JOBS.get(_key(scene))
                if not job or not job.get("plan_id"):
                    raise ValueError("CREATOR_PLAN_REQUIRED")
                operation = "studio.plan." + ("status" if self.action == "refresh" else self.action)
                _JOBS[_key(scene)] = _execute(operation, {"plan_id": job["plan_id"]})
            _notice(scene, "Saved plan state updated.")
            return {"FINISHED"}
        except (ValueError, RuntimeError, OSError, AttributeError, TypeError) as error:
            return _failure(self, scene, error)


def _wrapped(layout, context, value, icon=None):
    scale = max(1.0, context.preferences.system.ui_scale)
    # Leave room for nested-box padding, disclosure arrows and status icons.
    width = max(20, min(68, int((getattr(context.region, "width", 300) - 48) / (7.3 * scale))))
    for index, line in enumerate(textwrap.wrap(str(value), width) or [""]):
        if index == 0 and icon:
            layout.label(text=line, icon=icon)
        else:
            layout.label(text=line)


def _form(layout):
    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.scale_y = 1.15
    return layout


def _button(layout, tool, label, icon):
    row = layout.row()
    row.scale_y = 1.35
    row.operator("renderstudio.creator_tool", text=label, icon=icon).tool = tool


def _selected(layout, context, mesh=False):
    obj = context.active_object
    valid = obj is not None and (not mesh or obj.type == "MESH") and obj.mode == "OBJECT"
    _wrapped(layout, context, "Selected: " + obj.name if valid else
             ("Select a mesh in Object Mode first." if mesh else "Select an object in Object Mode first."),
             "OBJECT_DATA" if valid else "INFO")
    return valid


def _draw_plan(layout, context):
    job = _JOBS.get(_key(context.scene))
    if not job:
        row = layout.row()
        row.operator("renderstudio.creator_plan_control", text="Inspect Recent Plan", icon="FILE_REFRESH").action = "recent"
        return
    box = layout.box()
    _wrapped(box, context, "Plan: " + str(job.get("name", "Native creation")))
    state = job.get("state", "unknown")
    box.label(text=str(job.get("completed_steps", 0)) + " / " + str(job.get("total_steps", 0)) +
              " steps · " + str(state).replace("_", " ").title())
    if state == "needs_review":
        _wrapped(box, context, "Interrupted step needs inspection. Completed edits are retained.", "ERROR")
    row = box.row(align=True)
    row.operator("renderstudio.creator_plan_control", text="Refresh", icon="FILE_REFRESH").action = "refresh"
    if state == "queued":
        row.operator("renderstudio.creator_plan_control", text="Pause", icon="PAUSE").action = "pause"
    elif state == "paused":
        row.operator("renderstudio.creator_plan_control", text="Resume", icon="PLAY").action = "resume"
    if state in {"queued", "paused", "needs_review"}:
        box.operator("renderstudio.creator_plan_control", text="Cancel Remaining Steps", icon="CANCEL").action = "cancel"


class RENDERSTUDIO_PT_creator(bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator"
    bl_label = "Creator Studio"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Create"
    bl_order = -100

    def draw(self, context):
        scene, layout = context.scene, self.layout
        _wrapped(layout, context, "Start with a recipe or open a tool below.", "OUTLINER_OB_MESH")
        _wrapped(layout, context, "Real editable Blender data. Current scene retained.")
        notice = _NOTICES.get(_key(scene))
        if notice:
            box = layout.box()
            box.alert = notice[1]
            _wrapped(box, context, notice[0], "ERROR" if notice[1] else "CHECKMARK")
        layout.separator()
        _wrapped(layout, context, "ChatGPT: connect through Render > Agent Control. Local recipes below do not use an AI model.", "INFO")


class _CreatorPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Create"
    bl_parent_id = "RENDERSTUDIO_PT_creator"


class RENDERSTUDIO_PT_creator_recipes(_CreatorPanel, bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator_recipes"
    bl_label = "Guided Recipes"
    bl_order = 0

    def draw(self, context):
        scene, layout = context.scene, self.layout
        form = _form(layout.column())
        form.prop(scene, "render_creator_recipe", text="Start with")
        form.prop(scene, "render_creator_recipe_name", text="Project prefix")
        form.prop(scene, "render_creator_quality", text="Geometry")
        form.prop(scene, "render_creator_seed", text="Variation seed")
        form.prop(scene, "render_creator_edit_brief", text="Edit recipe wording")
        if scene.render_creator_edit_brief:
            form.prop(scene, "render_creator_brief", text="Recipe wording")
            _wrapped(layout, context, "Uses fixed local recipe keywords. For open-ended requests, connect ChatGPT.")
        row = layout.row()
        row.scale_y = 1.35
        row.operator("renderstudio.creator_preview", text="1  Preview Recipe", icon="VIEWZOOM")
        preview = _PREVIEWS.get(_key(scene))
        if preview and preview["request"] == _request(scene):
            result = preview["result"]
            box = layout.box()
            recipe = result.get("recipe", {})
            _wrapped(box, context, str(recipe.get("label", "Recipe")) +
                     " · " + str(result.get("total_steps", len(result["steps"]))) + " steps")
            for index, step in enumerate(result["steps"], 1):
                p = step.get("payload", {})
                title = step.get("operation", "").rsplit(".", 1)[-1].replace("_", " ").title()
                subject = p.get("name", p.get("object", p.get("source", "")))
                _wrapped(box, context, str(index) + ". " + title +
                         (" · " + str(p.get("kind", p.get("preset", p.get("style", "")))) if
                          any(k in p for k in ("kind", "preset", "style")) else "") +
                         (" → " + str(subject) if subject else ""))
                if scene.render_creator_exact_steps:
                    for key, value in sorted(p.items()):
                        _wrapped(box, context, "   " + key + ": " + json.dumps(value, ensure_ascii=False))
            box.prop(scene, "render_creator_exact_steps", text="Show exact parameters")
            complexity = result.get("estimated_complexity", {})
            if complexity:
                _wrapped(box, context, "Estimate: " + str(complexity.get("created_objects", "?")) +
                         " objects · " + str(complexity.get("mesh_vertices_upper_bound", "?")) + " mesh vertices max")
            for issue in result.get("preflight", {}).get("issues", []):
                _wrapped(box, context, _error_text(ValueError(str(issue))), "ERROR")
            collisions = result.get("preflight", {}).get("collisions", [])
            if collisions:
                _wrapped(box, context, "Names already used: " + ", ".join(str(x) for x in collisions), "ERROR")
            for warning in result.get("warnings", []):
                _wrapped(box, context, warning, "INFO")
            row = layout.row()
            row.scale_y = 1.4
            row.enabled = result.get("ready_to_submit") is True
            row.operator("renderstudio.creator_apply", text="2  Create Reviewed Recipe", icon="CHECKMARK")
        _draw_plan(layout, context)


class RENDERSTUDIO_PT_creator_models(_CreatorPanel, bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator_models"
    bl_label = "Models"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 1

    def draw(self, context):
        scene, layout = context.scene, self.layout
        form = _form(layout.column())
        for prop, label in (("model_kind", "Asset"), ("model_name", "Name"),
                            ("model_size", "Size"), ("detail", "Geometry"), ("seed", "Variation seed")):
            form.prop(scene, "render_creator_" + prop, text=label)
        _button(layout, "MODEL", "Create Editable Model", "MESH_CUBE")


class RENDERSTUDIO_PT_creator_worlds(_CreatorPanel, bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator_worlds"
    bl_label = "Worlds & Maps"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 2

    def draw(self, context):
        scene, layout = context.scene, self.layout
        form = _form(layout.column())
        for prop, label in (("terrain_style", "Landscape"), ("terrain_name", "Name"),
                            ("terrain_size", "Width"), ("height", "Height"),
                            ("resolution", "Grid resolution"), ("seed", "Variation seed")):
            form.prop(scene, "render_creator_" + prop, text=label)
        _button(layout, "TERRAIN", "Create Terrain", "MESH_GRID")
        layout.separator()
        layout.label(text="Linked Scatter", icon="PARTICLES")
        valid = _selected(layout, context, True)
        form = _form(layout.column())
        form.prop(scene, "render_creator_scatter_name", text="Name")
        form.prop(scene, "render_creator_count", text="Copies")
        form.prop(scene, "render_creator_extent", text="Area width")
        form.prop(scene, "render_creator_scatter_terrain", text="Terrain (optional)")
        form.prop(scene, "render_creator_min_scale", text="Smallest scale")
        form.prop(scene, "render_creator_max_scale", text="Largest scale")
        col = layout.column()
        col.enabled = valid
        _button(col, "SCATTER", "Scatter Selected Mesh", "OUTLINER_OB_GROUP_INSTANCE")
        _wrapped(layout, context, "Linked copies share the source mesh. Choose terrain to place them on its surface.")


class RENDERSTUDIO_PT_creator_materials(_CreatorPanel, bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator_materials"
    bl_label = "Materials"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    def draw(self, context):
        scene, layout = context.scene, self.layout
        valid = _selected(layout, context, True)
        form = _form(layout.column())
        form.prop(scene, "render_creator_material", text="Surface")
        form.prop(scene, "render_creator_texture_scale", text="Texture scale")
        form.prop(scene, "render_creator_custom_color", text="Custom color")
        if scene.render_creator_custom_color:
            form.prop(scene, "render_creator_color", text="Color")
        col = layout.column()
        col.enabled = valid
        _button(col, "MATERIAL", "Apply to Selected Mesh", "MATERIAL")
        _wrapped(layout, context, "Creates an editable material node graph for the selected mesh.")


class RENDERSTUDIO_PT_creator_motion(_CreatorPanel, bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator_motion"
    bl_label = "Motion"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 4

    def draw(self, context):
        scene, layout = context.scene, self.layout
        valid = _selected(layout, context)
        form = _form(layout.column())
        for prop, label in (("motion", "Motion"), ("start", "First frame"), ("end", "Last frame"),
                            ("motion_amount", "Amount"), ("loop", "Loop")):
            form.prop(scene, "render_creator_" + prop, text=label)
        col = layout.column()
        col.enabled = valid
        _button(col, "MOTION", "Add Editable Motion", "ANIM")
        _wrapped(layout, context, "Inspect and refine the real keyframes in Blender's animation editors.")


class RENDERSTUDIO_PT_creator_camera_rig(_CreatorPanel, bpy.types.Panel):
    bl_idname = "RENDERSTUDIO_PT_creator_camera_rig"
    bl_label = "Camera & Rig"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 5

    def draw(self, context):
        scene, layout = context.scene, self.layout
        valid = _selected(layout, context)
        form = _form(layout.column())
        form.prop(scene, "render_creator_camera", text="Shot")
        form.prop(scene, "render_creator_camera_name", text="Camera name")
        form.prop(scene, "render_creator_radius", text="Distance")
        if scene.render_creator_camera == "orbit":
            form.prop(scene, "render_creator_start", text="First frame")
            form.prop(scene, "render_creator_end", text="Last frame")
        col = layout.column()
        col.enabled = valid
        _button(col, "CAMERA", "Create Camera for Selection", "CAMERA_DATA")
        layout.separator()
        layout.label(text="Flexible Rig Starter", icon="ARMATURE_DATA")
        _wrapped(layout, context, "Adds a segmented rig to the selected mesh. Refine weights and pose in Blender.")
        form = _form(layout.column())
        form.prop(scene, "render_creator_rig_name", text="Rig name")
        form.prop(scene, "render_creator_segments", text="Segments")
        col = layout.column()
        col.enabled = valid and context.active_object.type == "MESH"
        _button(col, "RIG", "Add Starter Rig to Mesh", "ARMATURE_DATA")


class RENDERSTUDIO_MT_creator(bpy.types.Menu):
    bl_idname = "RENDERSTUDIO_MT_creator"
    bl_label = "Creator"

    def draw(self, context):
        self.layout.operator("renderstudio.creator_open", icon="WORKSPACE")
        self.layout.separator()
        self.layout.operator("renderstudio.creator_preview", text="Preview Current Recipe", icon="VIEWZOOM")
        self.layout.operator("renderstudio.creator_plan_control", text="Inspect Recent Plan", icon="FILE_REFRESH").action = "recent"


def _menu(self, context):
    self.layout.menu("RENDERSTUDIO_MT_creator", text="Creator")


_CLASSES = (RENDERSTUDIO_OT_creator_open, RENDERSTUDIO_OT_creator_preview,
            RENDERSTUDIO_OT_creator_apply, RENDERSTUDIO_OT_creator_tool,
            RENDERSTUDIO_OT_creator_plan_control, RENDERSTUDIO_PT_creator,
            RENDERSTUDIO_PT_creator_recipes, RENDERSTUDIO_PT_creator_models,
            RENDERSTUDIO_PT_creator_worlds, RENDERSTUDIO_PT_creator_materials,
            RENDERSTUDIO_PT_creator_motion, RENDERSTUDIO_PT_creator_camera_rig,
            RENDERSTUDIO_MT_creator)
_PROPERTIES = ()


def install():
    global _INSTALLED, _PROPERTIES, _FOCUS_ATTEMPTS
    if bpy.app.background or _INSTALLED:
        return
    P = bpy.props
    enum = lambda rows, default: P.EnumProperty(items=[(v, label, "") for v, label in rows], default=default)
    name = lambda value: P.StringProperty(default=value, maxlen=64)
    props = {
        "recipe": P.EnumProperty(items=[(r[0], r[1], r[3]) for r in _RECIPE_ROWS],
                                 default="asset", update=_recipe_changed),
        "recipe_name": P.StringProperty(default="MyCreation", maxlen=40, update=_changed),
        "brief": P.StringProperty(default=_RECIPES["asset"][2], maxlen=240, update=_changed),
        "edit_brief": P.BoolProperty(default=False),
        "exact_steps": P.BoolProperty(default=False),
        "quality": P.EnumProperty(items=[("draft", "Light", "Fewer vertices and instances"),
            ("standard", "Balanced", "Balanced scene complexity"), ("detail", "Detailed", "More scene geometry")],
            default="standard", update=_changed),
        "seed": P.IntProperty(default=21, min=0, max=2147483647, update=_changed),
        "model_kind": enum([(x, x.title()) for x in ("crate", "barrel", "column", "arch", "stairs", "table", "rock", "tree")], "crate"),
        "model_name": name("CreatorModel"),
        "model_size": P.FloatProperty(default=2, min=.05, max=100, soft_max=10, unit="LENGTH"),
        "detail": enum([("1", "Light"), ("2", "Balanced"), ("3", "Detailed")], "2"),
        "terrain_name": name("CreatorTerrain"),
        "terrain_style": enum([(x, x.title()) for x in ("island", "mountains", "dunes", "plains")], "island"),
        "terrain_size": P.FloatProperty(default=64, min=.1, max=2048, soft_max=256, unit="LENGTH"),
        "height": P.FloatProperty(default=8, min=0, max=512, soft_max=40, unit="LENGTH"),
        "resolution": P.IntProperty(default=32, min=4, max=128),
        "scatter_name": name("CreatorScatter"),
        "count": P.IntProperty(default=24, min=1, max=10000, soft_max=200),
        "extent": P.FloatProperty(default=20, min=.1, max=2048, soft_max=100, unit="LENGTH"),
        "scatter_terrain": P.PointerProperty(type=bpy.types.Object, poll=lambda self, obj: obj.type == "MESH"),
        "min_scale": P.FloatProperty(default=.7, min=.01, max=10, soft_max=3),
        "max_scale": P.FloatProperty(default=1.3, min=.01, max=10, soft_max=3),
        "material": enum([(x, x.title()) for x in ("wood", "metal", "stone", "fabric", "ceramic", "emissive")], "wood"),
        "texture_scale": P.FloatProperty(default=5, min=.05, max=256, soft_max=20),
        "custom_color": P.BoolProperty(default=False),
        "color": P.FloatVectorProperty(default=(.32, .12, .04), size=3, min=0, max=1, subtype="COLOR"),
        "motion": enum([(x, x.title()) for x in ("turntable", "float", "bounce", "orbit")], "turntable"),
        "start": P.IntProperty(default=1, min=1, max=100000),
        "end": P.IntProperty(default=120, min=1, max=100000),
        "motion_amount": P.FloatProperty(default=1, min=.001, max=100, soft_max=10),
        "loop": P.BoolProperty(default=True),
        "camera": enum([(x, x.title()) for x in ("hero", "orbit", "top", "closeup")], "hero"),
        "camera_name": name("CreatorCamera"),
        "radius": P.FloatProperty(default=8, min=.1, max=10000, soft_max=100, unit="LENGTH"),
        "rig_name": name("CreatorRig"),
        "segments": P.IntProperty(default=4, min=2, max=32, soft_max=12),
    }
    _PROPERTIES = tuple("render_creator_" + key for key in props)
    registered = []
    menu_added = False
    try:
        for key, prop in props.items():
            setattr(bpy.types.Scene, "render_creator_" + key, prop)
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.VIEW3D_MT_editor_menus.append(_menu)
        menu_added = True
        if _loaded not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(_loaded)
        _INSTALLED = True
        bpy.app.timers.register(_poll_jobs, first_interval=2.0, persistent=True)
        if os.environ.get("RENDER_CREATOR_FOCUS") == "1":
            _FOCUS_ATTEMPTS = 0
            bpy.app.timers.register(_startup_focus, first_interval=5.0)
    except Exception:
        for callback in (_poll_jobs, _startup_focus):
            if bpy.app.timers.is_registered(callback):
                bpy.app.timers.unregister(callback)
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
    for callback in (_poll_jobs, _startup_focus):
        if bpy.app.timers.is_registered(callback):
            bpy.app.timers.unregister(callback)
    if _loaded in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_loaded)
    bpy.types.VIEW3D_MT_editor_menus.remove(_menu)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    for key in _PROPERTIES:
        if hasattr(bpy.types.Scene, key):
            delattr(bpy.types.Scene, key)
    _loaded(None)
