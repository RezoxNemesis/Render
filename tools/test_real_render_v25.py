# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender process fixture for Android recovery instrumentation.

No fake device GPU success: validates only native bpy engine settings, startup
addon import, and fsynced render lifecycle breadcrumbs.
"""
import os
from pathlib import Path
import sys
import tempfile
import json
import bpy

source=Path(__file__).resolve().parents[1]/"full-app/scripts"
sys.path.insert(0,str(source))
with tempfile.TemporaryDirectory() as directory:
    os.environ["RENDER_AGENT_SPOOL"]=str(Path(directory)/"render_bpy_jobs")
    import render_session_tools as R
    import render_v25_recovery as addon

    scene=bpy.context.scene
    scene.render.resolution_x=1920
    scene.render.resolution_y=1080
    scene.render.resolution_percentage=100
    scene.frame_set(42)
    original_engine=scene.render.engine
    spec=R._render_spec(scene,"STILL")
    assert spec["output_kind"]=="STILL",spec
    assert spec["start"]==42 and spec["end"]==42,spec
    assert spec["width"]==1920 and spec["height"]==1080,spec
    assert spec["engine"]==original_engine,spec
    assert scene.render.resolution_percentage==100

    addon._record("started",scene)
    event=addon.read_render_state()
    assert event["state"]=="started",event
    assert event["render_engine"]==original_engine
    assert event["frame"]==42
    assert event["actual_png_validated"] is False
    addon._record("native_callback_completed",scene)
    completed=addon.read_render_state()
    assert completed["state"]=="native_callback_completed"
    assert completed["gpu_driver_root_cause_verified"] is False

print("PASS: real Blender native scene still spec, original settings and render event journal")
print("NOT VERIFIED: phone thermal path, GPU stability, rendered PNG bytes or app lifecycle")
