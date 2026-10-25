# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Blender window: reversible clean/detail/wire previews and depth precision.

Xvfb is a REAL Blender window with VIEW_3D, not a mock screenshot. The
on-device Android GPU driver remains a separate acceptance requirement.
"""
import math
import os
from pathlib import Path
import sys
import tempfile

import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_viewport_fidelity as Quality
import render_viewport_fidelity_ui as UI

assert not bpy.app.background,"Must execute with real Blender graphical window"
folder=Path(tempfile.mkdtemp(prefix="render-preview-native-"))
spool=folder/"render_bpy_jobs";spool.mkdir()
os.environ["RENDER_AGENT_SPOOL"]=str(spool)
scene=bpy.context.scene
native_before=(scene.render.engine,scene.render.fps,
               scene.render.resolution_x,scene.render.resolution_y,
               scene.render.resolution_percentage,
               scene.render.film_transparent)
area=next(a for a in bpy.context.window.screen.areas if a.type=="VIEW_3D")
space=area.spaces.active
UI.install()
assert UI.installed()
assert hasattr(bpy.types.Scene,"render_studio_fidelity_profile")
assert getattr(bpy.types,"RENDERSTUDIO_PT_viewport_fidelity") is not None
assert scene.render_studio_fidelity_profile=="CLEAN_SOLID"

bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16)
head=bpy.context.object;head.name="HeadCloseupTest"
space.shading.type="SOLID"
space.shading.show_xray=True
space.overlay.show_wireframes=True
space.clip_start=.001
space.clip_end=100000.
state=Quality.inspect(scene,{})
assert state["native_viewport_available"] and state["area_pixels"]["width"]>0
old=state["revision_sha256"]
aa_before=Quality.aa_inspect({})["native_current"] if Quality.aa_inspect({})["available"] else None

result=Quality.apply(scene,{"profile":"CLEAN_SOLID","expected_sha256":old})
assert result["native_preview_changed"],result
assert not space.shading.show_xray and not space.overlay.show_wireframes
assert result["revision_after_sha256"]!=old
assert result["saved_original_in_memory"]
try:
    Quality.apply(scene,{"profile":"DETAIL_INSPECT","expected_sha256":old})
    raise AssertionError("Agent overwrote viewport despite stale revision")
except ValueError as e:
    assert str(e)=="STUDIO_PREVIEW_REVISION_CONFLICT",e

detail=Quality.apply(scene,{"profile":"DETAIL_INSPECT"})
assert space.shading.type=="SOLID"
assert space.shading.show_cavity and space.shading.show_shadows
wire=Quality.apply(scene,{"profile":"SURFACE_DEBUG"})
assert space.overlay.show_wireframes
assert not space.shading.show_shadows

# Near clip adjusts to the real object rather than silently making 2000m
# a global scene boundary, which used to hide geometry in large worlds.
precision=Quality.apply(scene,{"profile":"DETAIL_INSPECT",
                                "object":head.name,
                                "precision_target_clipping":True})
assert precision["target_precision"] is not None
assert space.clip_end/space.clip_start<=50001
assert precision["target_precision"]["other_scene_objects_may_be_clipped"]
assert native_before==(scene.render.engine,scene.render.fps,
                       scene.render.resolution_x,scene.render.resolution_y,
                       scene.render.resolution_percentage,
                       scene.render.film_transparent)
returned=Quality.restore(scene,{})
assert returned["restored_actual_blender_view"]
assert returned["revision_after_sha256"]==old,(returned,old)
assert space.shading.show_xray and space.overlay.show_wireframes
assert abs(space.clip_start-.001)<1e-8
assert abs(space.clip_end-100000)<.1

try:
    Quality.apply(scene,{"profile":"MATERIAL_REVIEW"})
    raise AssertionError("Expensive native shader compilation allowed without opt-in")
except ValueError as e:
    assert str(e)=="STUDIO_PREVIEW_MATERIAL_REVIEW_REQUIRES_OPT_IN",e
try:
    Quality.aa_configure({"level":"32","allow_global_preferences":False})
    raise AssertionError("Changed global AA with no express consent")
except ValueError:pass
aa_after=Quality.aa_inspect({})["native_current"] if Quality.aa_inspect({})["available"] else None
assert aa_before==aa_after,(aa_before,aa_after)
assert not list((folder/"Production"/"Projects").glob("*.blend")) if (
    folder/"Production"/"Projects").exists() else True

print("PASS: real native Blender viewport preview clean/detail/surface/wire changes",flush=True)
print("PASS: true depth precision for selected mesh, stale revision denied and exact restore",flush=True)
print("PASS: global anti-alias preference and final scene render settings untouched",flush=True)
print("NOT VERIFIED: physical Android GPU, ghosting resolved or human anatomy created",flush=True)

def _quit():
    bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(_quit,first_interval=.6)
