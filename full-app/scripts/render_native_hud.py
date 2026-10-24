# SPDX-License-Identifier: GPL-2.0-or-later
"""Render's artist feedback INSIDE Blender's VIEW_3D and status bar.

Uses Blender GPU/BLF draw handlers, not Android overlays. Read-only UI state;
never changes scene geometry, rendering quality, input events or engine choice.
An object arrow is projected from a completed native command's actual object.
"""
import json
import math
import os
from pathlib import Path
import re
import time

import bpy

_handle = None
_provider = None
_progress = None
_worker = None
_event = {"state": "idle", "action": "", "object": None, "at": 0.0}
_pointer = None
_pointer_at = 0.0
_last_draw_at = 0.0
_draw_error = None
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


def command_started(command):
    global _event, _pointer
    action = command.get("args", {}).get("operation", command.get("action", "Native action"))
    _event = {"state": "running", "action": str(action)[:80], "object": None, "at": time.monotonic()}
    _pointer = None


def command_finished(report):
    """Called only AFTER the native result was atomically written to the spool."""
    global _event, _pointer
    result = report.get("result", {})
    if not isinstance(result, dict):
        result = {}
    state = report.get("state", "recovery_required")
    name = result.get("object", result.get("name"))
    if isinstance(name, dict):
        name = name.get("name")
    if state != "succeeded" or result.get("paused") or not isinstance(name, str) or not _NAME.fullmatch(name):
        name = None
    if state == "succeeded" and result.get("paused"):
        state = "paused"
    _event = dict(_event, state=state, object=name, at=time.monotonic())
    _pointer = None


def _read_worker():
    spool = os.environ.get("RENDER_AGENT_SPOOL", "")
    if not spool:
        return None
    production = Path(spool).resolve().parent / "Production"
    if production.is_symlink():
        return None
    path = production / "native_ui_status.json"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            return None
        value = json.loads(path.read_bytes().decode("utf8"))
        if not isinstance(value, dict) or value.get("state") not in (
                "running", "paused", "succeeded", "failed", "cancelled", "recovery_required"):
            return None
        age = time.time() * 1000 - float(value.get("updated_at_epoch_ms", 0))
        if age < 0 or not math.isfinite(age):
            return None
        if value["state"] == "running" and age > 35000:
            value = dict(value, state="recovery_required", stage="Inspect interrupted native command")
        if value["state"] in ("succeeded", "failed", "cancelled") and age > 5000:
            return None
        percent = value.get("progress", -1)
        if type(percent) is not int or not -1 <= percent <= 100:
            percent = -1
        return {"state": value["state"], "action": str(value.get("action", "Native work"))[:80],
                "stage": str(value.get("stage", ""))[:100], "progress": percent}
    except (OSError, ValueError, TypeError, OverflowError):
        return None


def _frame_progress(value):
    if not isinstance(value, dict):
        return None
    done, total = value.get("completed"), value.get("total")
    if type(done) is not int or type(total) is not int or not 0 <= done <= total or total <= 0:
        return None
    eta=value.get("estimated_remaining_ms",0)
    elapsed=value.get("render_active_ms",0)
    label=f"{done}/{total} checkpointed frames"
    if type(elapsed) is int and elapsed>0:label+=f" • rendered {elapsed//60000}m"
    if type(eta) is int and eta>0:label+=f" • ~{eta//60000}m frames left"
    return {"completed": done, "total": total, "fraction": done / total,
            "label": label, "job_id": value.get("job_id")}


def model():
    recent = time.monotonic() - _event["at"] < 5.0
    native = _event if _event["state"] == "running" or recent else None
    status = _worker if _worker is not None else native
    if status is None and _progress is None:
        return None
    status = status or {"state": "rendering", "action": "Rendering in Blender"}
    progress = _frame_progress(_progress)
    percent = status.get("progress", -1)
    fraction = progress["fraction"] if progress else percent / 100 if type(percent) is int and 0 <= percent <= 100 else None
    return {"state": status["state"], "action": status.get("action", "Native Blender action").replace(".", " ").replace("_", " "),
            "stage": status.get("stage", "Native command received" if status["state"] == "running" else status["state"]),
            "fraction": fraction, "progress_label": progress["label"] if progress else
                f"{percent}% native reported progress" if fraction is not None else "Waiting for native progress",
            "object": _event["object"] if recent and _event["state"] == "succeeded" else None}


def draw_card(value, width, height, rectangle, text, hand, inset_left=0, inset_right=0):
    """Blender drawing layout, with injectable primitives for host logic tests."""
    available = width - inset_left - inset_right
    if value is None or available < 180 or height < 110:
        return
    x, y, w, h = inset_left + 14, 18, min(360, available - 28), 90
    rectangle(x, y, w, h, (0.055, 0.07, 0.095, 0.92))
    hand(x + 17, y + 49)
    title = "Native Blender work" if value["state"] != "paused" else "Render paused"
    text(x + 39, y + 67, (title + " - " + value["action"])[:max(1, int((w-54)/7))], 12)
    text(x + 15, y + 45, value["stage"][:max(1, int((w-30)/6))], 11)
    text(x + 15, y + 12, value["progress_label"][:max(1, int((w-30)/6))], 10)
    if value["fraction"] is not None:
        rectangle(x + 15, y + 30, w - 30, 4, (0.17, 0.21, 0.27, 1))
        rectangle(x + 15, y + 30, (w - 30) * value["fraction"], 4, (0.25, 0.6, 1, 1))


def _project_object(name):
    if name is None:
        return None
    context = bpy.context
    if context.region is None or context.region_data is None:
        return None
    obj = context.scene.objects.get(name)
    if obj is None or not obj.visible_get():
        return None
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    point = location_3d_to_region_2d(context.region, context.region_data, obj.matrix_world.translation)
    if point is None or not all(math.isfinite(float(v)) for v in point):
        return None
    x, y = map(float, point)
    if not 0 <= x < context.region.width or not 0 <= y < context.region.height:
        return None
    return x, y


def _draw():
    global _pointer, _pointer_at, _last_draw_at, _draw_error
    try:
        value = model()
        region = bpy.context.region
        if value is None or region is None:
            return
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        def shape(points, color, kind="TRIS"):
            shader.bind();shader.uniform_float("color", color)
            batch_for_shader(shader, kind, {"pos": points}).draw(shader)
        def rectangle(x, y, w, h, color):
            if w > 0:
                shape([(x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)], color)
        def text(x, y, label, size):
            blf.position(0,x,y,0);blf.size(0,size);blf.color(0,0.94,0.97,1,1);blf.draw(0,label)
        def hand(x, y):
            points=[(-3,0),(-7,8),(-7,12),(-4,13),(0,8),(0,25),(4,25),(5,12),
                    (9,14),(12,12),(15,14),(18,11),(18,2),(12,-5),(3,-5),(-3,0)]
            shape([(x+a*.65,y+b*.65) for a,b in points], (0.92,0.96,1,1), "LINE_STRIP")
        previous = gpu.state.blend_get()
        try:
            gpu.state.blend_set("ALPHA")
            area, space = bpy.context.area, bpy.context.space_data
            # Blender's toolbar/sidebar overlay the WINDOW region on Android.
            # Keep the actual hand and status card inside its unobscured area.
            left = max((r.width for r in area.regions if r.type == "TOOLS"), default=0) if getattr(space,"show_region_toolbar",False) else 0
            right = max((r.width for r in area.regions if r.type == "UI"), default=0) if getattr(space,"show_region_ui",False) else 0
            draw_card(value,region.width,region.height,rectangle,text,hand,left,right)
            _last_draw_at=time.monotonic()
            _draw_error=None
            point = _project_object(value["object"])
            _pointer = None
            if point is not None:
                x,y=point
                shape([(x,y),(x+8,y-24),(x+13,y-13),(x,y),(x+13,y-13),(x+24,y-8)],(0.95,0.98,1,1))
                text(min(x+25,region.width-140),max(12,y-24),"Edited: "+value["object"][:18],11)
                _pointer={"object":value["object"],"x":x,"y":y,"region_width":region.width,"region_height":region.height}
                _pointer_at=time.monotonic()
        finally:
            gpu.state.blend_set(previous)
    except Exception as error:
        # UI/driver incompatibility cannot fail a native scene command or render.
        _pointer = None
        _draw_error = type(error).__name__


def _refresh():
    global _progress, _worker
    _worker = _read_worker()
    try:
        _progress = _provider() if _provider else None
    except Exception:
        _progress = None
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in ("VIEW_3D", "STATUSBAR"):
                    area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass
    return 0.5


def snapshot():
    return {"installed_in_blender_viewport": _handle is not None,
            "surface": "Blender SpaceView3D POST_PIXEL", "status": model(),
            "viewport_draw_observed": _last_draw_at > 0,
            "last_viewport_draw_age_ms": round((time.monotonic()-_last_draw_at)*1000) if _last_draw_at > 0 else None,
            "last_draw_error": _draw_error,
            "pointer": _pointer if time.monotonic()-_pointer_at < 1 else None,
            "pointer_source": "completed_native_object_projection",
            "pointer_is_ui_input": False, "fabricated_ui_taps": False,
            "in_frame_sample_progress_available": False}


def draw_statusbar(layout):
    value = model()
    if value is None:
        return False
    label = "ChatGPT: " + value["stage"][:50]
    if value["fraction"] is not None and hasattr(layout,"progress"):
        layout.progress(factor=value["fraction"],type="BAR",text=value["progress_label"])
    layout.label(text=label)
    return True


def install(progress_provider):
    global _handle, _provider
    if _handle is not None or getattr(bpy.app,"background",False):
        return
    _provider = progress_provider
    _handle = bpy.types.SpaceView3D.draw_handler_add(_draw,(),"WINDOW","POST_PIXEL")
    try:
        bpy.app.timers.register(_refresh,first_interval=0.1,persistent=True)
    except Exception:
        bpy.types.SpaceView3D.draw_handler_remove(_handle,"WINDOW")
        _handle = None
        raise


def uninstall():
    global _handle, _pointer
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle,"WINDOW")
        _handle = None
    if bpy.app.timers.is_registered(_refresh):
        bpy.app.timers.unregister(_refresh)
    _pointer = None
