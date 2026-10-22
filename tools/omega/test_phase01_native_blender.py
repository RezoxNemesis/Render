# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender bpy fixture: run using blender -b -noaudio --python-exit-code 1
--python tools/omega/test_phase01_native_blender.py

Background Blender cannot prove a phone's visible Vulkan frame. This fixture
checks native scene inspection without modifying actual render settings.
"""
from pathlib import Path
import importlib.util

import bpy

source=Path(__file__).resolve().parents[2]/"full-app/scripts/omega/phase01_engine.py"
module_spec=importlib.util.spec_from_file_location("real_render_phase01",source)
p01=importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(p01)

scene=bpy.context.scene
assert scene is not None
original=(scene.render.engine,scene.render.resolution_x,
          scene.render.resolution_y,scene.render.resolution_percentage,
          scene.render.fps,scene.render.fps_base)
bpy.ops.mesh.primitive_cube_add()
cube=bpy.context.object
cube.name="Omega01_NonUniform_Test"
cube.scale=(1.0,1.0,0.35)
report=p01.execute("omega.engine.diagnose",{"max_objects":128},
    {"scene":scene,"bpy":bpy})
assert report["native_execution_verified"] is True
assert report["native_bpy_present"] is True
assert report["blender_version"] == bpy.app.version_string
assert "Omega01_NonUniform_Test" in report["mesh_warnings"]["nonuniform_scale_candidates"]
assert report["android_vulkan_driver_verified"] is False
assert report["first_vulkan_pixel_observed"] is False
assert report["visual_quality_verified"] is False
inspection=p01.execute("omega.engine.viewport_profile",{"mode":"inspect"},
    {"scene":scene,"bpy":bpy})
assert inspection["quality_reduced"] is False
assert inspection["render_quality_unchanged"] is True
assert original==(scene.render.engine,scene.render.resolution_x,
                  scene.render.resolution_y,scene.render.resolution_percentage,
                  scene.render.fps,scene.render.fps_base)
print("PASS: real Blender P01 native bpy diagnostics, nonuniform mesh audit, no render settings changed")
print("NOT PROVEN: Android Vulkan driver compatibility, captured first frame or on-device jitter correction")
