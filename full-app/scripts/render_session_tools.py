# SPDX-License-Identifier: GPL-2.0-or-later
"""Render Studio's native Blender session, manual render and viewport controls.

Everything runs inside the owner-installed Blender process. The file menu
requests jobs; Android's bounded ProductionBatch executes their frames with
thermal/memory checks and MediaCodec exports the verified PNG masters.
"""
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import time
import threading

import bpy

SPOOL = os.environ.get("RENDER_AGENT_SPOOL", "")
_ROOT = Path(SPOOL).resolve().parent / "Production" if SPOOL else None
_ID = re.compile(r"^[a-f0-9]{32}$")
_STARTED = False
_RESTORE_ATTEMPTED = False
_RESTORE_THREAD = None
_RESTORE_RESULT = None
_LAST_SAVE = 0

def _root():
    if _ROOT is None:
        raise RuntimeError("RENDER_LOCAL_STORAGE_UNAVAILABLE")
    _ROOT.mkdir(parents=True, mode=0o700, exist_ok=True)
    return _ROOT

def _atomic_json(path, data):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf8") as output:
        json.dump(data, output, sort_keys=True, allow_nan=False)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)

def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()

def _compressed_blend_header(path):
    # Blender can open Zstd or legacy gzip compressed .blend files. Actual
    # contents remain protected by independent SHA-256 receipt validation.
    with path.open("rb") as data:
        header = data.read(4)
    return header.startswith(b"\x1f\x8b") or header == b"\x28\xb5\x2f\xfd"


def _blend_file(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size < 256:
        return False
    with path.open("rb") as stream:
        return stream.read(7) == b"BLENDER" or _compressed_blend_header(path)

def _session_dir():
    folder = _root() / "Projects"
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    return folder

def _rendering_now():
    probe = getattr(bpy.app, "is_job_running", None)
    try:
        return bool(probe("RENDER")) if probe else False
    except (TypeError, RuntimeError):
        return False

def save_session():
    """Atomic latest-session save, with a fallback copy and untouched open path."""
    global _LAST_SAVE
    if _rendering_now():
        raise RuntimeError("RENDER_BUSY_CANNOT_CHECKPOINT")
    folder = _session_dir()
    latest, previous, stage = (folder / name for name in (
        "CurrentSession.blend", "CurrentSession.previous.blend",
        "CurrentSession.staged.blend"))
    if stage.exists():
        stage.unlink()
    prior_path = bpy.data.filepath
    try:
        result = bpy.ops.wm.save_as_mainfile(
            filepath=str(stage), copy=True, compress=True,
            check_existing=False, relative_remap=True)
        if "FINISHED" not in result or not _blend_file(stage):
            raise RuntimeError("SESSION_SNAPSHOT_INCOMPLETE")
        receipt = {"filename": latest.name, "bytes": stage.stat().st_size,
                   "sha256": _sha(stage), "saved_at": int(time.time()),
                   "source_path_retained": bpy.data.filepath == prior_path}
        if not receipt["source_path_retained"]:
            raise RuntimeError("OPEN_PROJECT_PATH_CHANGED")
        if latest.exists():
            manifest = folder / "CurrentSession.json"
            prior_manifest = folder / "CurrentSession.previous.json"
            if _receipt_matches(manifest, latest):
                old = json.loads(manifest.read_text(encoding="utf8"))
                _atomic_json(prior_manifest, dict(old, filename=previous.name))
            os.replace(latest, previous)
        try:
            os.replace(stage, latest)
        except OSError:
            if previous.exists() and not latest.exists():
                os.replace(previous, latest)
            raise
        _atomic_json(folder / "CurrentSession.json", receipt)
        _LAST_SAVE = time.monotonic()
        return {"saved": True, "reopen_on_next_launch": True,
                "bytes": receipt["bytes"], "sha256": receipt["sha256"],
                "source_project_unchanged": True}
    finally:
        if stage.exists():
            stage.unlink()

def _receipt_matches(receipt_path, target):
    if not receipt_path.is_file() or not _blend_file(target):
        return False
    try:
        data = json.loads(receipt_path.read_text(encoding="utf8"))
        return (data.get("filename") == target.name and
                data.get("bytes") == target.stat().st_size and
                data.get("sha256") == _sha(target))
    except (OSError, ValueError, TypeError):
        return False


def _recoverable_session():
    folder = _session_dir()
    latest = folder / "CurrentSession.blend"
    previous = folder / "CurrentSession.previous.blend"
    if _receipt_matches(folder / "CurrentSession.json", latest):
        return latest
    if _receipt_matches(folder / "CurrentSession.previous.json", previous):
        return previous
    return None

def restore_session(force=False):
    """Restore only a real saved session; never overwrite a loaded .blend silently."""
    if not force and (bpy.data.filepath or bpy.data.is_dirty):
        return {"restored": False, "reason": "CURRENT_PROJECT_ALREADY_OPEN"}
    candidate = _recoverable_session()
    if candidate is None:
        return {"restored": False, "reason": "NO_VALID_SAVED_SESSION"}
    if bpy.data.filepath and Path(bpy.data.filepath) == candidate:
        return {"restored": True, "already_open": True}
    result = bpy.ops.wm.open_mainfile(filepath=str(candidate), load_ui=False)
    if "FINISHED" not in result:
        raise RuntimeError("SESSION_RESTORE_FAILED")
    return {"restored": True, "filename": candidate.name}

def _scan_saved_project():
    global _RESTORE_RESULT
    try:
        # Read only app-owned files off the Blender UI thread. bpy scene
        # mutation and open_mainfile ALWAYS execute on the timer main thread.
        _RESTORE_RESULT = _recoverable_session()
    except Exception as error:
        print("Render session scan failed:", type(error).__name__)
        _RESTORE_RESULT = None


def _restore_at_start():
    global _RESTORE_ATTEMPTED, _RESTORE_THREAD
    if _RESTORE_ATTEMPTED:
        return None
    if bpy.data.filepath or bpy.data.is_dirty:
        # Never discard a project opened or edited while checking storage.
        _RESTORE_ATTEMPTED = True
        return None
    if _RESTORE_THREAD is None:
        _RESTORE_THREAD = threading.Thread(
            target=_scan_saved_project, name="render-session-integrity",
            daemon=True)
        _RESTORE_THREAD.start()
        return 0.5
    if _RESTORE_THREAD.is_alive():
        return 0.5
    _RESTORE_ATTEMPTED = True
    if _RESTORE_RESULT is None:
        return None
    try:
        result = bpy.ops.wm.open_mainfile(
            filepath=str(_RESTORE_RESULT), load_ui=False)
        if "FINISHED" not in result:
            print("Render session requires explicit manual recovery")
    except Exception as error:
        print("Render session preserved for manual recovery:", type(error).__name__)
    return None

def _autosave_tick():
    try:
        if not getattr(bpy.app, "background", False) and bpy.context.scene is not None:
            if bpy.data.is_dirty and not _rendering_now() and time.monotonic()-_LAST_SAVE >= 90:
                save_session()
    except Exception as error:
        print("Render autosave skipped:", type(error).__name__)
    return 90.0

def _latest_job():
    root = _root()
    entries = sorted((p for p in root.iterdir() if p.is_dir() and _ID.fullmatch(p.name)
                      and (p / "manifest.json").is_file()),
                     key=lambda p: (p / "manifest.json").stat().st_mtime, reverse=True)
    for entry in entries[:40]:
        try:
            manifest = json.loads((entry / "manifest.json").read_text(encoding="utf8"))
            if manifest.get("job_id") == entry.name and manifest.get("state") in (
                    "ready", "rendering", "paused_error", "frames_complete", "encoding"):
                return manifest
        except (OSError, ValueError, TypeError):
            continue
    return None

def render_progress():
    manifest = _latest_job()
    if not manifest:
        return None
    spec = manifest.get("spec", {})
    total = max(1, int(spec.get("frame_count", 1)))
    done = len(manifest.get("frames", {}))
    return {"job_id": manifest["job_id"], "completed": done,
            "total": total, "next_frame": manifest.get("next_frame"),
            "state": manifest.get("state"), "fraction": min(1.0, done / total)}

def _render_spec(scene, output_kind='ANIMATION'):
    render = scene.render
    percentage = int(render.resolution_percentage)
    width = int(render.resolution_x) * percentage // 100
    height = int(render.resolution_y) * percentage // 100
    if width % 2 or height % 2 or width < 16 or height < 16:
        raise ValueError("RENDER_REQUIRES_EVEN_PIXEL_DIMENSIONS")
    engine = render.engine
    if engine not in ("CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        raise ValueError("RENDER_ENGINE_NOT_SUPPORTED")
    if engine == "CYCLES":
        if getattr(scene, "cycles", None) is None:
            raise ValueError("REQUESTED_CYCLES_ENGINE_NOT_AVAILABLE")
        samples = int(scene.cycles.samples)
    else:
        settings = getattr(scene, "eevee", None)
        if settings is None:
            raise ValueError("REQUESTED_EEVEE_SAMPLE_CONTROL_UNAVAILABLE")
        if hasattr(settings, "taa_render_samples"):
            samples = int(settings.taa_render_samples)
        elif hasattr(settings, "taa_samples"):
            samples = int(settings.taa_samples)
        else:
            raise ValueError("REQUESTED_EEVEE_SAMPLE_CONTROL_UNAVAILABLE")
    if samples < 1:
        raise ValueError("INVALID_NATIVE_RENDER_SAMPLE_COUNT")
    if output_kind not in ("STILL", "ANIMATION"):
        raise ValueError("INVALID_RENDER_OUTPUT_KIND")
    first = int(scene.frame_current) if output_kind == "STILL" else int(scene.frame_start)
    last = first if output_kind == "STILL" else int(scene.frame_end)
    return {"width": width, "height": height, "start": first,
            "end": last, "fps": int(render.fps), "output_kind": output_kind,
            "samples": samples, "engine": engine,
            "bitrate": 16000000}

def queue_manual_render(resume=False, still=False):
    """Render menu only creates a frozen job; Android's thermal-aware worker runs it."""
    request_file = _root() / "manual_render_request.json"
    if request_file.exists():
        raise RuntimeError("RENDER_REQUEST_ALREADY_PENDING")
    if resume:
        manifest = _latest_job()
        if manifest is None:
            raise ValueError("NO_INCOMPLETE_RENDER_TO_RESUME")
        ident = manifest["job_id"]
    else:
        import render_production
        spec = _render_spec(bpy.context.scene, 'STILL' if still else 'ANIMATION')
        result = render_production.execute(
            {"operation": "render.plan", "payload": spec}, SPOOL, "local-editor-menu")
        ident = result["job_id"]
    _atomic_json(request_file, {"job_id": ident, "requested_at": int(time.time()),
                                "source": "owner-native-blender-menu"})
    return {"job_id": ident, "queued": True, "thermal_checked_by_android": True,
            "render_resolution_preserved": True}

def stabilize_viewport():
    """Fix display-state precision where possible; never touch mesh data or render settings."""
    changes = []
    duplicates = {}
    for obj in list(bpy.context.scene.objects)[:25000]:
        if obj.type != "MESH":
            continue
        signature = (obj.data.name, tuple(round(v, 6) for row in obj.matrix_world for v in row))
        duplicates.setdefault(signature, []).append(obj.name)
    collisions = [names[:4] for names in duplicates.values() if len(names) > 1][:16]
    window = bpy.context.window
    if window is not None:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            # Clip depth ratio, not render sample count, governs near-surface precision.
            # Most wire shimmer is depth-precision limited: keep the actual
            # near/far span <= 100,000 without touching camera render clipping.
            # Explicit UI action, reversible via native Blender viewport fields.
            far = min(float(space.clip_end), 2000.0)
            near = max(float(space.clip_start), 0.02, far / 100000.0)
            if abs(space.clip_start-near)>1e-6:
                space.clip_start = near
                changes.append("near_clip_precision")
            if abs(space.clip_end-far)>1e-6:
                space.clip_end = far
                changes.append("far_clip_precision")
            if space.shading.show_xray:
                space.shading.show_xray = False
                changes.append("xray_off")
            if space.overlay.show_wireframes:
                space.overlay.show_wireframes = False
                changes.append("wire_overlay_off")
            area.tag_redraw()
    # Prefer real GPU viewport multisampling only when the Blender build
    # explicitly reports the enum. Do not claim this repairs coplanar meshes.
    try:
        system = bpy.context.preferences.system
        if hasattr(system, "viewport_aa"):
            enums = system.bl_rna.properties["viewport_aa"].enum_items
            supported = {entry.identifier for entry in enums}
            requested = next((value for value in ("32", "16", "8", "FXAA")
                              if value in supported), None)
            if requested and system.viewport_aa != requested:
                system.viewport_aa = requested
                changes.append("viewport_anti_alias_" + requested)
    except (AttributeError, TypeError, ValueError, KeyError):
        pass
    return {"viewport_settings_changed": changes,
            "possible_identical_overlapping_objects": collisions,
            "mesh_geometry_modified": False,
            "final_render_samples_modified": False,
            "note": "Actual intersecting/coplanar meshes still require geometry inspection"}

def dispatch(action, args):
    if args:
        raise ValueError("UNEXPECTED_LOCAL_RENDER_ARGUMENTS")
    if action == "blender.project.save_session":
        return save_session()
    if action == "blender.project.restore_session":
        return restore_session(force=False)
    if action == "blender.render.plan_current":
        return queue_manual_render()
    if action == "blender.render.plan_still":
        return queue_manual_render(still=True)
    if action == "blender.render.resume_last":
        return queue_manual_render(resume=True)
    if action == "blender.ui.stabilize_viewport":
        return stabilize_viewport()
    raise ValueError("UNKNOWN_LOCAL_STUDIO_ACTION")

class RENDERSTUDIO_OT_save_session(bpy.types.Operator):
    bl_idname = "renderstudio.save_session"
    bl_label = "Save Current Session for Return"
    bl_description = "Atomic private Blender project snapshot; next launch resumes this work"
    def execute(self, context):
        try:
            save_session()
            self.report({"INFO"}, "Render Studio session saved")
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_OT_resume_session(bpy.types.Operator):
    bl_idname = "renderstudio.resume_session"
    bl_label = "Resume Previous Session"
    bl_description = "Load the latest verified Render Studio project snapshot"
    def execute(self, context):
        try:
            result = restore_session()
            if not result["restored"]:
                self.report({"WARNING"}, result["reason"])
                return {"CANCELLED"}
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_OT_safe_render(bpy.types.Operator):
    bl_idname = "renderstudio.safe_render"
    bl_label = "Render Animation (Checkpointed)"
    bl_description = "Freeze scene and render numbered PNG frames on the device with recovery"
    def execute(self, context):
        try:
            result = queue_manual_render()
            self.report({"INFO"}, "Queued Render " + result["job_id"][:8])
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_OT_resume_render(bpy.types.Operator):
    bl_idname = "renderstudio.resume_render"
    bl_label = "Resume Last Render / Encode"
    bl_description = "Continue missing frames or encode completed frames"
    def execute(self, context):
        try:
            result = queue_manual_render(resume=True)
            self.report({"INFO"}, "Resuming Render " + result["job_id"][:8])
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_OT_stabilize_view(bpy.types.Operator):
    bl_idname = "renderstudio.stabilize_view"
    bl_label = "Stabilize Viewport (No Geometry Changes)"
    bl_description = "Inspect overlapping instances and improve viewport clipping/xray precision"
    def execute(self, context):
        result = stabilize_viewport()
        self.report({"WARNING"} if result["possible_identical_overlapping_objects"] else {"INFO"},
                    "Possible overlaps: " + str(len(result["possible_identical_overlapping_objects"])))
        return {"FINISHED"}

_CLASSES = (RENDERSTUDIO_OT_save_session, RENDERSTUDIO_OT_resume_session,
            RENDERSTUDIO_OT_safe_render, RENDERSTUDIO_OT_resume_render,
            RENDERSTUDIO_OT_stabilize_view)

def _file_menu(self, context):
    col = self.layout.column()
    col.separator()
    col.label(text="Render Studio / Local and Recoverable")
    col.operator("renderstudio.save_session", text="Save & Keep Session")
    col.operator("renderstudio.resume_session", text="Open Last Saved Session")
    col.operator("renderstudio.safe_render", text="Render Animation (Safe Frames)")
    col.operator("renderstudio.resume_render", text="Resume Render / MP4")
    col.operator("renderstudio.stabilize_view", text="Fix Viewport Flicker")

def _statusbar(self, context):
    try:
        import render_native_hud
        if render_native_hud.draw_statusbar(self.layout):
            return
    except Exception:
        pass
    try:
        p = render_progress()
        if not p:
            return
        label = "Render Studio: " + str(p["completed"]) + "/" + str(p["total"])
        try:
            self.layout.progress(factor=p["fraction"], type="BAR", text=label)
        except (TypeError, AttributeError):
            self.layout.label(text=label)
    except Exception:
        pass

def _redraw_timer():
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == "STATUSBAR":
                    area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass
    return 1.0

def install():
    global _STARTED
    if _STARTED or not SPOOL or getattr(bpy.app, "background", False):
        return
    for klass in _CLASSES:
        try:
            bpy.utils.register_class(klass)
        except ValueError:
            pass
    import render_assets
    render_assets.install()
    import render_v25_recovery
    render_v25_recovery.install()
    try:
        import render_native_hud
        render_native_hud.install(render_progress)
    except Exception as error:
        print("Render Blender viewport HUD unavailable:", type(error).__name__)
    bpy.types.TOPBAR_MT_file.append(_file_menu)
    try:
        bpy.types.STATUSBAR_HT_header.append(_statusbar)
    except (AttributeError, TypeError):
        pass
    bpy.app.timers.register(_restore_at_start, first_interval=3.5, persistent=False)
    bpy.app.timers.register(_autosave_tick, first_interval=90, persistent=True)
    bpy.app.timers.register(_redraw_timer, first_interval=1, persistent=True)
    _STARTED = True
