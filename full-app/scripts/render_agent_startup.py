# SPDX-License-Identifier: GPL-2.0-or-later
"""Native Blender bpy operations, executed on Blender's timer/main context.

This module is bundled into scripts/startup/ for Render's full Android build.
An app-private, one-way file spool accepts typed commands only. No eval/exec,
shell commands, arbitrary bpy operator IDs, or network listener are exposed.
"""
import json
import hashlib
import math
import os
from pathlib import Path
import re
import time

import bpy

ROOT = os.environ.get("RENDER_AGENT_SPOOL", "")
MOBILE_MODE = os.environ.get("RENDER_MOBILE_UI_MODE", "")
_UI_FOCUSED = False
_LAST_HEARTBEAT = 0.0
_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_OBJECT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_MAX_BYTES = 16384

def _number(value, lower, upper):
    return type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper


# PreferencesView.ui_scale is writable; PreferencesSystem.ui_scale is
# derived and readonly. Control size is separate from render quality.
def _ui_scale(value=None, delta=None):
    view = bpy.context.preferences.view
    current = float(view.ui_scale)
    target = current if value is None else value
    if delta is not None:
        target = current + delta
    target = min(2.20, max(0.85, float(target)))
    view.ui_scale = target
    return round(float(view.ui_scale), 3)


def _focus_viewport():
    global _UI_FOCUSED
    window = bpy.context.window
    screen = window.screen if window else None
    if not window or not screen:
        raise RuntimeError("BLENDER_WINDOW_UNAVAILABLE")
    area = next((x for x in screen.areas if x.type == "VIEW_3D"), None)
    if area is None:
        raise RuntimeError("NO_VIEW_3D_AREA")
    with bpy.context.temp_override(window=window, screen=screen, area=area):
        outcome = bpy.ops.screen.screen_full_area(use_hide_panels=False)
    if "FINISHED" not in outcome:
        raise RuntimeError("FOCUS_VIEWPORT_NOT_READY")
    _UI_FOCUSED = not _UI_FOCUSED
    return {"action": "toggle_fullscreen_area", "focused": _UI_FOCUSED,
            "preserves_other_editors": True}


def _mobile_mode(mode):
    if mode not in ("portrait", "landscape"):
        raise ValueError("INVALID_MOBILE_MODE")
    size = _ui_scale(value=1.34 if mode == "portrait" else 1.18)
    if mode == "landscape" and _UI_FOCUSED:
        # Restore Blender's original complete multi-editor workspace.
        _focus_viewport()
    elif mode == "portrait" and not _UI_FOCUSED:
        # Prefer the existing VIEW_3D; don't invent a reduced editor.
        _focus_viewport()
    return {"orientation": mode, "ui_scale": size,
            "focused": _UI_FOCUSED,
            "render_quality_unchanged": True, "engine": "native-blender"}


def _initial_mobile_setup():
    if MOBILE_MODE not in ("portrait", "landscape") or getattr(bpy.app,"background",False):
        return None
    try:
        _mobile_mode(MOBILE_MODE)
        return None
    except Exception as error:
        retries = getattr(_initial_mobile_setup, "attempts", 0) + 1
        _initial_mobile_setup.attempts = retries
        if retries >= 5:
            print("Render mobile layout skipped:", type(error).__name__)
            return None
        return 1.5

def _dispatch(command):
    action = command.get("action")
    args = command.get("args")
    if not isinstance(args, dict):
        raise ValueError("INVALID_ARGUMENTS")
    # Local touch-overlay UI operations; NOT remotely registered agent actions.
    if action == "blender.ui.adjust_scale":
        if set(args) != {"delta"} or not _number(args.get("delta"), -.25, .25):
            raise ValueError("INVALID_UI_SCALE_STEP")
        return {"ui_scale": _ui_scale(delta=args["delta"]),
                "render_quality_unchanged": True}
    if action == "blender.ui.focus_viewport":
        if args:
            raise ValueError("UNEXPECTED_ARGUMENT")
        return _focus_viewport()
    if action == "blender.ui.set_mode":
        if set(args) != {"mode"}:
            raise ValueError("INVALID_MOBILE_MODE")
        return _mobile_mode(args.get("mode"))

    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("NO_ACTIVE_BLENDER_SCENE")
    if action == "blender.scene.summary":
        if args:
            raise ValueError("UNEXPECTED_ARGUMENT")
        objects = list(scene.objects)
        return {
            "blender_version": bpy.app.version_string,
            "scene": scene.name,
            "frame": int(scene.frame_current),
            "render_engine": scene.render.engine,
            "total_objects": len(objects),
            "sample_objects": [
                {"name": ob.name, "type": ob.type}
                for ob in objects[:128]
            ],
            "executed_by": "bpy-main-thread-on-android",
        }
    if action == "blender.object.add_cube":
        if set(args) - {"name", "size", "location"}:
            raise ValueError("UNEXPECTED_ARGUMENT")
        name = args.get("name", "Cube")
        size = args.get("size", 2.0)
        location = args.get("location", [0.0, 0.0, 0.0])
        if not isinstance(name, str) or not _OBJECT_PATTERN.fullmatch(name):
            raise ValueError("INVALID_OBJECT_NAME")
        if not _number(size, 0.001, 10000):
            raise ValueError("INVALID_CUBE_SIZE")
        if not isinstance(location, list) or len(location) != 3 or not all(
            _number(v, -100000, 100000) for v in location
        ):
            raise ValueError("INVALID_CUBE_LOCATION")
        # This is Blender's genuine edit operation, not a manually built mesh.
        bpy.ops.mesh.primitive_cube_add(size=size, location=location)
        ob = bpy.context.object
        if ob is None:
            raise RuntimeError("BLENDER_OPERATOR_RETURNED_NO_OBJECT")
        ob.name = name
        return {
            "name": ob.name,
            "type": ob.type,
            "location": [float(v) for v in ob.location],
            "scene": bpy.context.scene.name,
            "executed_by": "bpy-main-thread-on-android",
        }
    if action == "blender.scene.set_frame":
        if set(args) != {"frame"} or type(args.get("frame")) is not int or not 1 <= args["frame"] <= 100000:
            raise ValueError("INVALID_FRAME")
        scene.frame_set(args["frame"])
        return {
            "scene": scene.name,
            "frame": int(scene.frame_current),
            "executed_by": "bpy-main-thread-on-android",
        }
    if action in ("blender.object.set_transform", "blender.object.keyframe"):
        name = args.get("name")
        if not isinstance(name, str) or not _OBJECT_PATTERN.fullmatch(name):
            raise ValueError("INVALID_OBJECT_NAME")
        ob = scene.objects.get(name)
        if ob is None:
            raise ValueError("OBJECT_NOT_FOUND")
        if action == "blender.object.set_transform":
            if set(args) - {"name", "location", "rotation_euler", "scale"}:
                raise ValueError("UNEXPECTED_ARGUMENT")
            if not any(path in args for path in ("location", "rotation_euler", "scale")):
                raise ValueError("TRANSFORM_FIELD_REQUIRED")
            for path, low, high, error in (
                ("location", -100000, 100000, "INVALID_OBJECT_LOCATION"),
                ("rotation_euler", -1000, 1000, "INVALID_OBJECT_ROTATION"),
                ("scale", 0.001, 10000, "INVALID_OBJECT_SCALE"),
            ):
                if path in args:
                    raw = args[path]
                    if not isinstance(raw, list) or len(raw) != 3 or not all(
                        _number(value, low, high) for value in raw
                    ):
                        raise ValueError(error)
            # Validate every field before mutating any property.
            for path in ("location", "rotation_euler", "scale"):
                if path in args:
                    setattr(ob, path, args[path])
            bpy.context.view_layer.update()
            return {
                "name": ob.name,
                "location": [float(v) for v in ob.location],
                "rotation_euler": [float(v) for v in ob.rotation_euler],
                "scale": [float(v) for v in ob.scale],
                "executed_by": "bpy-main-thread-on-android",
            }
        if set(args) != {"name", "data_path", "frame", "value"}:
            raise ValueError("INVALID_KEYFRAME_ARGUMENTS")
        frame = args.get("frame")
        if type(frame) is not int or not 1 <= frame <= 100000:
            raise ValueError("INVALID_FRAME")
        path = args.get("data_path")
        if path not in ("location", "rotation_euler", "scale"):
            raise ValueError("INVALID_KEYFRAME_PATH")
        lower, upper = (0.001, 10000) if path == "scale" else (
            (-1000, 1000) if path == "rotation_euler" else (-100000, 100000)
        )
        value = args.get("value")
        if not isinstance(value, list) or len(value) != 3 or not all(
            _number(v, lower, upper) for v in value
        ):
            raise ValueError("INVALID_KEYFRAME_VALUE")
        setattr(ob, path, value)
        inserted = bool(ob.keyframe_insert(data_path=path, frame=frame))
        if not inserted:
            raise RuntimeError("KEYFRAME_INSERT_FAILED")
        return {
            "name": ob.name,
            "data_path": path,
            "frame": frame,
            "value": [float(v) for v in getattr(ob, path)],
            "inserted": True,
            "executed_by": "bpy-main-thread-on-android",
        }
    if action == "blender.project.save_copy":
        if args:
            raise ValueError("UNEXPECTED_ARGUMENT")
        ident = command.get("id")
        if not ROOT or not isinstance(ident, str) or not _ID_PATTERN.fullmatch(ident):
            raise ValueError("INVALID_SNAPSHOT_ID")
        project_folder = Path(ROOT).resolve().parent / "Projects"
        project_folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        filename = "Render_" + ident + ".blend"
        destination = project_folder / filename
        if destination.exists():
            raise ValueError("SNAPSHOT_ALREADY_EXISTS")
        current_project = bpy.data.filepath
        finished = bpy.ops.wm.save_as_mainfile(
            filepath=str(destination),
            check_existing=False,
            compress=True,
            copy=True,
            relative_remap=True,
        )
        if "FINISHED" not in finished or not destination.is_file():
            raise RuntimeError("BLENDER_SAVE_FAILED")
        if bpy.data.filepath != current_project:
            raise RuntimeError("OPEN_PROJECT_PATH_CHANGED")
        byte_count = destination.stat().st_size
        if byte_count < 256:
            raise RuntimeError("SAVED_FILE_TOO_SMALL")
        digest = hashlib.sha256()
        with destination.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1048576), b""):
                digest.update(chunk)
        return {
            "filename": filename,
            "bytes": byte_count,
            "sha256": digest.hexdigest(),
            "scene": bpy.context.scene.name,
            "copied_without_changing_open_project": True,
            "executed_by": "bpy-main-thread-on-android",
            "warning": "Referenced external textures and libraries are not automatically packed",
        }
    raise ValueError("NATIVE_BLENDER_ACTION_UNAVAILABLE")

def _write_result(path, report):
    intermediate = path.with_name(path.name + ".partial")
    payload = json.dumps(report, separators=(",", ":"), ensure_ascii=True).encode("utf8")
    if len(payload) > 65536:
        raise ValueError("RESPONSE_TOO_LARGE")
    fd = os.open(str(intermediate), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(intermediate, path)
    finally:
        try:
            intermediate.unlink(missing_ok=True)
        except Exception:
            pass

def _poll():
    global _LAST_HEARTBEAT
    if not ROOT:
        return None
    root = Path(ROOT)
    pending, working, results = (root / part for part in ("pending", "working", "results"))
    for path in (pending, working, results):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    now = time.time()
    if now - _LAST_HEARTBEAT > 3.0:
        (root / "ready").touch(exist_ok=True)
        _LAST_HEARTBEAT = now
    for incoming in sorted(pending.glob("*.json"))[:4]:
        name = incoming.stem
        if not _ID_PATTERN.fullmatch(name) or incoming.is_symlink():
            continue
        claimed = working / incoming.name
        target = results / incoming.name
        try:
            if target.exists():
                incoming.unlink(missing_ok=True)
                continue
            os.replace(incoming, claimed)
            if claimed.stat().st_size > _MAX_BYTES:
                raise ValueError("COMMAND_TOO_LARGE")
            raw = claimed.read_bytes()
            command = json.loads(raw.decode("utf8"))
            if not isinstance(command, dict) or command.get("id") != name:
                raise ValueError("INVALID_COMMAND_ID")
            if type(command.get("deadline")) not in (int, float) or command["deadline"] < time.time():
                raise ValueError("COMMAND_EXPIRED")
            result = _dispatch(command)
            report = {"id": name, "state": "succeeded", "result": result}
        except Exception as error:
            code = str(error)
            if not re.fullmatch(r"[A-Z_]{3,96}", code):
                code = type(error).__name__
            report = {"id": name, "state": "failed", "error": code}
        try:
            _write_result(target, report)
        except Exception:
            # Leave claimed file for crash/recovery inspection. No blind replay.
            continue
        claimed.unlink(missing_ok=True)
    return 0.5

if ROOT:
    bpy.app.timers.register(_poll, first_interval=0.5, persistent=True)

if MOBILE_MODE in ("portrait", "landscape") and not getattr(bpy.app,"background",False):
    bpy.app.timers.register(_initial_mobile_setup, first_interval=2.0, persistent=False)
