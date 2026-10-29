# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise actual native Animate panel operators, checkpoints and render handoff.

Run in windowed Blender under Xvfb. No Android installation or GPU claim is made.
The render test queues an immutable job but deliberately does not render a movie.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

import bpy

assert not bpy.app.background, "ANIMATION_UI_TEST_REQUIRES_NATIVE_WINDOW"
assert bpy.context.window is not None
bpy.context.preferences.view.show_splash = False
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
folder = Path(tempfile.mkdtemp(prefix="render-animation-ui-"))
spool = folder / "render_bpy_jobs"
spool.mkdir()
os.environ["RENDER_AGENT_SPOOL"] = str(spool)
os.environ.pop("RENDER_ANIMATION_FOCUS", None)

import render_animation_ui as UI

scene = bpy.context.scene
original = {obj.name: obj.as_pointer() for obj in scene.objects}
settings = (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
            scene.render.fps, scene.frame_start, scene.frame_end)
UI.install()
UI.install()
assert UI.installed() and hasattr(bpy.types, "RENDERSTUDIO_PT_animation")
assert hasattr(bpy.types, "RENDERSTUDIO_MT_animation")
assert len([f for f in bpy.app.handlers.load_post if f is UI._loaded]) == 1
assert "FINISHED" in bpy.ops.renderstudio.animation_open()
assert original == {obj.name: obj.as_pointer() for obj in scene.objects}
assert settings == (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
                    scene.render.fps, scene.frame_start, scene.frame_end)


def select(*objects):
    for obj in tuple(bpy.context.selected_objects):
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


def click(tool):
    result = bpy.ops.renderstudio.animation_tool(tool=tool)
    assert "FINISHED" in result, (tool, result, UI._NOTICES)
    assert not UI._NOTICES[UI._key(scene)][1]
    return UI._RESULTS[UI._key(scene)][tool]


def rejected(callback):
    try:
        result = callback()
        assert "CANCELLED" in result, result
    except RuntimeError:
        pass
    assert UI._NOTICES[UI._key(scene)][1], "A rejected UI action must explain itself"


# Two layers, real camera keys and collision handling. No hidden sample scene.
scene.render_anim_layer_name = "UiBackLayer"
scene.render_anim_depth = -3
click("LAYER")
back = scene.objects["UiBackLayer"]
assert back.type == "MESH" and len(back.data.polygons) > 0
assert bpy.context.active_object == back
scene.render_anim_layer_name = "UiFrontLayer"
scene.render_anim_layer_shape = "ellipse"
scene.render_anim_depth = 1
scene.render_anim_width = 2
click("LAYER")
front = scene.objects["UiFrontLayer"]
assert len(front.data.vertices) > 4
before_objects = set(scene.objects.keys())
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="LAYER"))
assert set(scene.objects.keys()) == before_objects
select(front, back)
scene.render_anim_camera_name = "UiLayerCamera"
click("PARALLAX")
camera = scene.objects["UiLayerCamera"]
assert camera.type == "CAMERA" and scene.camera == camera
assert camera.animation_data and camera.animation_data.action
assert camera.location.z > front.location.z > back.location.z

# Existing action inspection and revision rejection reaches the real dispatcher.
select(camera)
scene.render_anim_action = ""
inspection = click("INSPECT_ACTION")
assert inspection["revision_sha256"] and inspection["keys"] > 0
scene.render_anim_action = camera.animation_data.action.name
assert click("INSPECT_ACTION")["action"] == camera.animation_data.action.name
scene.render_anim_action = "A_missing_action"
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="INSPECT_ACTION"))
scene.render_anim_action = camera.animation_data.action.name
inspection = click("INSPECT_ACTION")
scene.render_anim_time_scale = 2
scene.render_anim_time_pivot = 1
scene.render_anim_time_offset = 0
before_range = inspection["frame_range"]
click("RETIME")
assert UI._key(scene) not in UI._INSPECTIONS
after = click("INSPECT_ACTION")
assert abs((after["frame_range"][1] - after["frame_range"][0]) -
           2 * (before_range[1] - before_range[0])) < 1e-4
action = camera.animation_data.action
curve = action.fcurves[0]
curve.keyframe_points[0].co.y += .25
curve.update()
before = [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right)) for k in curve.keyframe_points]
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="RETIME"))
assert before == [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right)) for k in curve.keyframe_points]

# Character button creates a genuine armature and motion data, then samples it.
scene.render_anim_rig_name = "UiMotionActor"
scene.render_anim_start = 1
scene.render_anim_end = 49
rig_result = click("RIG")
rig = scene.objects[rig_result["rig"]]
assert rig.type == "ARMATURE" and len(rig.data.bones) > 10
assert bpy.context.active_object == rig
scene.render_anim_clip = "walk"
clip = click("CLIP")
assert clip["actions"] and clip["audit_payload"]
assert "FINISHED" in bpy.ops.renderstudio.animation_preview()
assert scene.use_preview_range and (scene.frame_preview_start, scene.frame_preview_end) == (1, 49)
assert bpy.context.screen.is_animation_playing
assert "FINISHED" in bpy.ops.renderstudio.animation_preview()
assert not bpy.context.screen.is_animation_playing
audit = click("AUDIT")
assert audit["quality_gate"] == "PASS", audit
before_actions = set(bpy.data.actions.keys())
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="CLIP"))
assert set(bpy.data.actions.keys()) == before_actions

# Morphing operates on real mesh shape keys and protects unrelated geometry.
UI._execute("studio.create.model", {"name": "UiMorphColumn", "kind": "column"})
column = scene.objects["UiMorphColumn"]
original_mesh = column.data
original_vertices = [tuple(vertex.co) for vertex in original_mesh.vertices]
select(column)
scene.render_anim_morph = "breathe"
scene.render_anim_morph_name = "UiBreathe"
click("MORPH")
assert column.data != original_mesh
assert "UiBreathe" in column.data.shape_keys.key_blocks
assert column.data.shape_keys.animation_data.action
assert original_vertices == [tuple(vertex.co) for vertex in original_mesh.vertices]
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="MORPH"))

# Empty action/selection errors occur before any unintended edits.
select()
scene.render_anim_action = ""
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="INSPECT_ACTION"))
rejected(lambda: bpy.ops.renderstudio.animation_tool(tool="PARALLAX"))

# Finish presets reach the same scene/profile settings used by Android's queue.
scene.render_anim_start = 1
scene.render_anim_end = 3
scene.render_anim_engine = "CYCLES"
scene.render_anim_quality = "draft"
scene.render_anim_custom_size = True
scene.render_anim_output_width = 320
scene.render_anim_output_height = 240
scene.render_anim_fps = 24
click("PRESET")
assert (scene.render.resolution_x, scene.render.resolution_y, scene.render.fps) == (320, 240, 24)
assert (scene.frame_start, scene.frame_end) == (1, 3)
scene.camera = None
report = click("CHECK_RENDER")
assert not report["ready"] and report["blockers"]
rejected(lambda: bpy.ops.renderstudio.animation_render(kind="ANIMATION"))
scene.camera = camera
report = click("CHECK_RENDER")
assert report["ready"], report
assert "FINISHED" in bpy.ops.renderstudio.animation_render(kind="ANIMATION")
queued = UI._RESULTS[UI._key(scene)]["RENDER"]
assert queued["queued"] and queued["job_id"]
import render_session_tools
request = json.loads((render_session_tools._root() / "manual_render_request.json").read_text())
assert request["job_id"] == queued["job_id"]
assert not bpy.app.is_job_running("RENDER"), "UI must hand off to Android rather than launch a second render loop"
assert all(scene.objects[name].as_pointer() == pointer for name, pointer in original.items())
assert len(list((folder / "Production" / "Projects").glob("*.blend"))) >= 7

# Cleanup removes callbacks and fields; registration is safe after reopening.
UI.uninstall()
assert not UI.installed()
assert not hasattr(bpy.types.Scene, "render_anim_mode")
UI.install()
assert UI.installed()
scene.render_anim_mode = "FINISH"
assert "FINISHED" in bpy.ops.renderstudio.animation_open()
click("CHECK_RENDER")
print("PASS: native Animate sidebar, cutout/parallax, mannequin motion QA, morph and retime", flush=True)
print("PASS: stale action/duplicate creation rejected; checkpoints and original geometry preserved", flush=True)
print("PASS: Finish preflight blocks missing camera and queues recoverable Android handoff", flush=True)
print("NOT VERIFIED: phone touch ergonomics, Vulkan driver or completed device MP4", flush=True)

_capture_drawn = False


def close():
    global _capture_drawn
    assert any(region.type == "UI" and getattr(region, "active_panel_category", "") == "Animate"
               for area in bpy.context.window.screen.areas if area.type == "VIEW_3D"
               for region in area.regions), "ANIMATE_CATEGORY_NOT_ACTIVATED_AFTER_REDRAW"
    screenshot = os.environ.get("RENDER_ANIMATION_UI_SCREENSHOT")
    if screenshot:
        if not _capture_drawn:
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
            _capture_drawn = True
            return 2.0
        bpy.ops.screen.screenshot(filepath=screenshot)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(close, first_interval=1.5)
