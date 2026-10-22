# SPDX-License-Identifier: GPL-2.0-or-later
"""Native Blender recovery and render watchdog for Render Studio Android.

No alternate toy renderer, no reduced samples, no remote rendering.
A missing quit.blend after Android kills a native render is expected Blender
behavior: File > Recover > Last Session requires an orderly prior shutdown.
Our verified, app-owned snapshot is an independent recovery mechanism.
"""
import json
from pathlib import Path
import time
import uuid

import bpy
import render_session_tools as S

_INSTALLED = False
_HOOKS_INSTALLED = False


def _status_file():
    path = S._root() / "Diagnostics" / "native_render_event.json"
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    return path


def read_render_state():
    path = _status_file()
    if not path.is_file() or path.stat().st_size > 8192:
        return {"state": "no_native_render_record"}
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError, TypeError):
        return {"state": "invalid_native_render_record"}


def _record(state, scene):
    try:
        s = scene if scene is not None else bpy.context.scene
        render = s.render
        details = {
            "state": state,
            "timestamp_epoch_seconds": int(time.time()),
            "scene": str(s.name),
            "frame": int(s.frame_current),
            "render_engine": str(render.engine),
            "resolution_x": int(render.resolution_x),
            "resolution_y": int(render.resolution_y),
            "resolution_percentage": int(render.resolution_percentage),
            "gpu_driver_root_cause_verified": False,
            "actual_png_validated": False,
        }
        S._atomic_json(_status_file(), details)
    except Exception as error:
        # Never break an original Blender render merely because diagnostics fail.
        print("Render native event record failed:", type(error).__name__)


def _on_render_init(scene, *args):
    _record("started", scene)


def _on_render_complete(scene, *args):
    # A native completion callback is NOT proof that a pixel file exists.
    _record("native_callback_completed", scene)


def _on_render_cancel(scene, *args):
    _record("native_callback_cancelled", scene)


def _preserve_before_recover():
    """Recovering must not destroy edits in the scene that is currently open."""
    folder = S._session_dir()
    path = folder / ("BeforeExplicitRecover_" + uuid.uuid4().hex + ".blend")
    previous_path = bpy.data.filepath
    result = bpy.ops.wm.save_as_mainfile(
        filepath=str(path), copy=True, compress=True,
        check_existing=False, relative_remap=True)
    if ("FINISHED" not in result or not S._blend_file(path) or
        bpy.data.filepath != previous_path):
        raise RuntimeError("CURRENT_SCENE_ROLLBACK_BACKUP_FAILED")
    receipt = {"filename": path.name, "sha256": S._sha(path),
               "bytes": path.stat().st_size,
               "owner_action": "explicit_recovery"}
    S._atomic_json(folder / (path.stem + ".json"), receipt)
    return receipt


class RENDERSTUDIO_OT_protected_image(bpy.types.Operator):
    bl_idname = "renderstudio.protected_image"
    bl_label = "Render Image (Full Quality / Recoverable)"
    bl_description = "Render this frame with native Blender, unchanged output pixels and samples, backed by an immutable blend snapshot"

    def execute(self, context):
        try:
            result = S.queue_manual_render(still=True)
            self.report({"INFO"}, "Native still render queued: " + result["job_id"][:8])
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


class RENDERSTUDIO_OT_verified_recovery(bpy.types.Operator):
    bl_idname = "renderstudio.verified_recovery"
    bl_label = "Recover Render Studio Verified Session"
    bl_description = "Recover a verified app-owned snapshot; save a separate rollback of current edits first"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        try:
            target = S._recoverable_session()
            if target is None:
                self.report({"WARNING"}, "No verified Render Studio backup exists")
                return {"CANCELLED"}
            if bpy.data.is_dirty or bpy.data.filepath:
                _preserve_before_recover()
            result = S.restore_session(force=True)
            if not result.get("restored"):
                raise RuntimeError(result.get("reason", "RESTORE_DID_NOT_COMPLETE"))
            self.report({"INFO"}, "Render Studio recovered a verified local session")
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


class RENDERSTUDIO_OT_native_render_status(bpy.types.Operator):
    bl_idname = "renderstudio.native_render_status"
    bl_label = "Inspect Last Native Render"
    bl_description = "Inspect the last saved render lifecycle record, including renders without a completion receipt"

    def execute(self, context):
        try:
            state = read_render_state()
            message = str(state.get("state", "unknown"))
            if message == "started":
                message = "Previous native render had NO completion callback (possible interruption)"
            self.report({"WARNING"} if state.get("state") == "started" else {"INFO"}, message)
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def _recovery_menu(self, context):
    self.layout.separator()
    self.layout.operator("renderstudio.verified_recovery",
                         text="Render Studio: Recover Verified Project")


def _render_menu(self, context):
    self.layout.separator()
    self.layout.operator("renderstudio.protected_image",
                         text="Render Studio: Protected Image")
    self.layout.operator("renderstudio.safe_render",
                         text="Render Studio: Protected Animation")
    self.layout.operator("renderstudio.native_render_status",
                         text="Render Studio: Last Render Diagnostics")


def _file_menu(self, context):
    self.layout.separator()
    self.layout.operator("renderstudio.protected_image",
                         text="Render Image (Full Quality / Recoverable)")
    self.layout.operator("renderstudio.verified_recovery",
                         text="Recover Previous Render Studio Project")
    self.layout.operator("renderstudio.native_render_status",
                         text="Last Native Render Status")


_CLASSES = (RENDERSTUDIO_OT_protected_image,
            RENDERSTUDIO_OT_verified_recovery,
            RENDERSTUDIO_OT_native_render_status)


def install():
    global _INSTALLED, _HOOKS_INSTALLED
    if _INSTALLED or not S.SPOOL or getattr(bpy.app, "background", False):
        return
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file.append(_file_menu)
    recover = getattr(bpy.types, "TOPBAR_MT_file_recover", None)
    if recover is not None:
        recover.append(_recovery_menu)
    render = getattr(bpy.types, "TOPBAR_MT_render", None)
    if render is not None:
        render.append(_render_menu)
    hooks = getattr(bpy.app, "handlers", None)
    if hooks is not None and not _HOOKS_INSTALLED:
        persister = getattr(hooks, "persistent", lambda callback: callback)
        for name, handler in (
            ("render_init", _on_render_init),
            ("render_complete", _on_render_complete),
            ("render_cancel", _on_render_cancel),
        ):
            collection = getattr(hooks, name, None)
            if collection is not None:
                callback = persister(handler)
                if callback not in collection:
                    collection.append(callback)
        _HOOKS_INSTALLED = True
    _INSTALLED = True
