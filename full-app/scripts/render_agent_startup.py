# SPDX-License-Identifier: GPL-2.0-or-later
"""Native Blender bpy operations, executed on Blender's timer/main context.

This module is bundled into scripts/startup/ for Render's full Android build.
An app-private, one-way file spool accepts typed commands only. No eval/exec,
shell commands, arbitrary bpy operator IDs, or network listener are exposed.
"""
import json
import math
import os
from pathlib import Path
import re
import time

import bpy

ROOT = os.environ.get("RENDER_AGENT_SPOOL", "")
_LAST_HEARTBEAT = 0.0
_ID_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_OBJECT_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_MAX_BYTES = 16384

def _number(value, lower, upper):
    return type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper

def _dispatch(command):
    action = command.get("action")
    args = command.get("args")
    if not isinstance(args, dict):
        raise ValueError("INVALID_ARGUMENTS")
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
