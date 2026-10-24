# SPDX-License-Identifier: GPL-2.0-or-later
"""Explicit native render settings. Throughput controls never alter pixel quality."""
import math
import json
try:
    import bpy
except ImportError:
    bpy = None
_INSTALLED = False


def _samples(scene, engine=None):
    engine = engine or scene.render.engine
    if engine == "CYCLES" and hasattr(scene, "cycles"):
        return scene.cycles, "samples"
    if engine == "BLENDER_WORKBENCH":
        display = getattr(scene, "display", None)
        return (display, "render_aa") if display is not None and hasattr(display, "render_aa") else (None, None)
    if engine not in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        return None, None
    eevee = getattr(scene, "eevee", None)
    if eevee is not None and hasattr(eevee, "taa_render_samples"):
        return eevee, "taa_render_samples"
    if eevee is not None and hasattr(eevee, "taa_samples"):
        return eevee, "taa_samples"
    return None, None


def sample_value(scene, engine=None):
    owner, field = _samples(scene, engine)
    value = getattr(owner, field) if owner is not None else None
    if isinstance(value, str):
        return int(value) if value.isdigit() else None  # OFF/FXAA are not sample counts.
    return value


def sample_target(scene, value):
    owner, field = _samples(scene)
    if owner is None:
        raise ValueError("ACTIVE_ENGINE_SAMPLE_SETTING_UNAVAILABLE")
    native = str(value) if isinstance(getattr(owner, field), str) else value
    if field == "render_aa":
        prop = getattr(getattr(owner, "bl_rna", None), "properties", {}).get(field)
        if prop is not None and native not in {item.identifier for item in prop.enum_items}:
            raise ValueError("WORKBENCH_ANTIALIAS_SAMPLES_UNAVAILABLE")
    return owner, field, native


def inspect(scene):
    render = scene.render
    owner, field = _samples(scene)
    return {"engine": render.engine, "width": render.resolution_x,
            "height": render.resolution_y, "percentage": render.resolution_percentage,
            "fps": render.fps, "fps_base": render.fps_base,
            "samples": sample_value(scene),
            "sample_control": field,
            "workbench_antialiasing": getattr(owner, field) if render.engine == "BLENDER_WORKBENCH" and owner is not None else None,
            "film_transparent": render.film_transparent,
            "persistent_data": render.use_persistent_data,
            "threads_mode": render.threads_mode, "threads": render.threads,
            "denoising": bool(scene.cycles.use_denoising) if render.engine == "CYCLES" else None,
            "silent_quality_changes": False,
            "persistent_data_tradeoff": "Reuses render data between frames at the cost of retained memory",
            "frame_checkpointing": True}


def plan_payload(scene, requested):
    current = inspect(scene)
    engine = requested.get("engine", current["engine"])
    samples = requested.get("samples", sample_value(scene, engine))
    if samples is None:
        raise ValueError("RENDER_PLAN_REQUIRES_EXPLICIT_SUPPORTED_SAMPLES")
    result = {"width": current["width"] * current["percentage"] // 100,
              "height": current["height"] * current["percentage"] // 100,
              "engine": engine, "fps": current["fps"],
              "samples": samples,
              "start": scene.frame_start, "end": scene.frame_end}
    result.update(requested)
    return result


def validate(p, performance=False):
    allowed = {"persistent_data", "threads_mode", "threads"} if performance else {
        "engine", "width", "height", "percentage", "fps", "fps_base", "samples", "film_transparent", "denoising"}
    if not isinstance(p, dict) or set(p) - allowed:
        raise ValueError("UNKNOWN_RENDER_SETTING")
    ranges = {"width": (4, 65536), "height": (4, 65536), "percentage": (1, 100),
              "fps": (1, 32767), "samples": (1, 16_777_216), "threads": (1, 1024)}
    for key, value in p.items():
        if key in ("persistent_data", "film_transparent", "denoising") and type(value) is not bool:
            raise ValueError("RENDER_SETTING_REQUIRES_BOOLEAN")
        if key == "engine" and value not in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH"):
            raise ValueError("INVALID_RENDER_ENGINE")
        if key == "threads_mode" and value not in ("AUTO", "FIXED"):
            raise ValueError("INVALID_RENDER_THREADS_MODE")
        if key in ranges and (type(value) is not int or not ranges[key][0] <= value <= ranges[key][1]):
            raise ValueError("RENDER_SETTING_OUT_OF_RANGE")
        if key == "fps_base" and (type(value) not in (int, float) or not math.isfinite(value) or not 0.1 <= value <= 1000):
            raise ValueError("INVALID_RENDER_FPS_BASE")


def configure(scene, p, performance=False):
    validate(p, performance)
    if scene.get("production_frozen_job"):
        raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
    before, changes = inspect(scene), []

    def set_value(owner, field, value):
        if getattr(owner, field) == value:
            return  # Avoid invalidating compiled shaders/render caches.
        changes.append((owner, field, getattr(owner, field)))
        setattr(owner, field, value)
        if getattr(owner, field) != value and not (field == "fps_base" and abs(getattr(owner, field) - value) < 1e-5):
            raise ValueError("NATIVE_RENDER_SETTING_WAS_CLAMPED")
    try:
        if "engine" in p:
            set_value(scene.render, "engine", p["engine"])
        fields = {"width": "resolution_x", "height": "resolution_y", "percentage": "resolution_percentage",
                  "fps": "fps", "fps_base": "fps_base", "film_transparent": "film_transparent",
                  "persistent_data": "use_persistent_data", "threads_mode": "threads_mode", "threads": "threads"}
        for key, field in fields.items():
            if key in p:
                set_value(scene.render, field, p[key])
        if "samples" in p:
            owner, field, native = sample_target(scene, p["samples"])
            set_value(owner, field, native)
        if "denoising" in p:
            if scene.render.engine != "CYCLES":
                raise ValueError("DENOISING_SETTING_REQUIRES_CYCLES")
            set_value(scene.cycles, "use_denoising", p["denoising"])
    except Exception:
        for owner, field, previous in reversed(changes):
            setattr(owner, field, previous)
        raise
    return {"before": before, "after": inspect(scene), "requested_fields": sorted(p),
            "quality_settings_changed": not performance and bool(p),
            "existing_render_snapshots_changed": False, "native_execution_verified": True}


def profiles(scene, p, configure_profile=False):
    if not isinstance(p, dict) or set(p) - ({"profile", "settings"} if configure_profile else set()):
        raise ValueError("UNKNOWN_RENDER_PROFILE_ARGUMENT")
    saved = json.loads(scene.get("render_studio_profiles_v1", '{}'))
    if not isinstance(saved, dict):
        raise ValueError("RENDER_PROFILE_CORRUPT")
    if configure_profile:
        if scene.get("production_frozen_job"):
            raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
        name, settings = p.get("profile"), p.get("settings")
        if name not in ("preview", "final") or not isinstance(settings, dict):
            raise ValueError("INVALID_RENDER_PROFILE")
        validate(settings)
        merged = dict(saved.get(name, {}), **settings)
        saved[name] = merged
        scene["render_studio_profiles_v1"] = json.dumps(saved, sort_keys=True, allow_nan=False)
    return {"profiles": {name: saved.get(name, {}) for name in ("preview", "final")},
            "unset_fields": "inherit artist scene settings at plan creation",
            "active_scene_quality_changed": False, "final_quality_silently_reduced": False}


def profile_plan(scene, requested):
    requested = dict(requested)
    name = requested.pop("profile", "final")
    if name not in ("preview", "final"):
        raise ValueError("INVALID_RENDER_PROFILE")
    overrides = profiles(scene, {})["profiles"][name]
    current = inspect(scene)
    combined = dict(current, **overrides)
    selected = {key: requested.get(key, overrides.get(key)) for key in ("engine", "samples")
                if key in requested or key in overrides}
    plan = plan_payload(scene, selected)
    if "fps" in overrides:
        plan["fps"] = combined["fps"]
    for key in ("width", "height"):
        plan[key] = combined[key] * combined["percentage"] // 100
    plan.update(requested)
    return plan, name, overrides


def execute(operation, scene, p):
    if operation.startswith("render.profile."):
        return profiles(scene, p, operation.endswith("configure"))
    if operation.endswith("inspect"):
        if p:
            raise ValueError("UNKNOWN_RENDER_SETTING")
        return inspect(scene)
    return configure(scene, p, operation.startswith("render.performance"))


if bpy is not None and getattr(getattr(bpy, "types", None), "Panel", None):
    class RENDERSTUDIO_OT_store_preview_profile(bpy.types.Operator):
        bl_idname = "renderstudio.store_preview_profile"
        bl_label = "Save Preview Scale"
        def execute(self, context):
            profiles(context.scene, {"profile": "preview", "settings": {
                "percentage": context.scene.render_preview_scale}}, True)
            self.report({"INFO"}, "Preview profile saved; final and scene settings preserved")
            return {"FINISHED"}

    class RENDERSTUDIO_PT_execution(bpy.types.Panel):
        bl_label = "Render Studio • Rendering"
        bl_idname = "RENDERSTUDIO_PT_execution"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Render Studio"
        def draw(self, context):
            layout, scene = self.layout, context.scene
            render = scene.render
            layout.prop(render, "engine")
            row = layout.row(align=True)
            row.prop(render, "resolution_x", text="Width")
            row.prop(render, "resolution_y", text="Height")
            layout.prop(render, "resolution_percentage", text="Output scale")
            owner, field = _samples(scene)
            if owner:
                layout.prop(owner, field, text="Render samples")
            if render.engine == "CYCLES":
                layout.prop(scene.cycles, "use_denoising", text="Denoising")
            layout.separator()
            layout.label(text="Preview and final profiles inherit unset settings")
            layout.prop(scene, "render_studio_profile", text="Job profile")
            layout.prop(scene, "render_preview_scale", text="Preview output %")
            layout.operator("renderstudio.store_preview_profile", text="Save Preview Scale")
            layout.prop(render, "use_persistent_data", text="Reuse data between frames")
            layout.label(text="Cache uses more memory; output quality is unchanged")
            layout.prop(render, "threads_mode", text="CPU threads")
            if render.threads_mode == "FIXED":
                layout.prop(render, "threads", text="Thread count")
            layout.separator()
            layout.operator("renderstudio.safe_render", text="Render with Background Checkpoints", icon="RENDER_ANIMATION")
            layout.operator("renderstudio.resume_render", text="Resume Checkpointed Render", icon="PLAY")
            layout.label(text="Android background limits still apply")


def install():
    global _INSTALLED
    if not _INSTALLED and bpy is not None and not bpy.app.background:
        bpy.types.Scene.render_studio_profile = bpy.props.EnumProperty(
            items=[("final", "Final", "Preserve artist settings unless explicitly configured"),
                   ("preview", "Preview", "Use the separately saved preview settings")], default="final")
        bpy.types.Scene.render_preview_scale = bpy.props.IntProperty(default=50, min=1, max=100)
        bpy.utils.register_class(RENDERSTUDIO_OT_store_preview_profile)
        bpy.utils.register_class(RENDERSTUDIO_PT_execution)
        _INSTALLED = True


def register():
    pass


def unregister():
    pass
