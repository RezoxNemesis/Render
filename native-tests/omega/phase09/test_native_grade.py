# SPDX-License-Identifier: GPL-2.0-or-later
"""ACTUAL bpy/CPU render fixture; NOT a mocked native pass.

From repo root (Blender 3.4+ installed):
  blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase09/test_native_grade.py
Exercises native shaders, layer links, rendered PNG pixels, file reopen, replay,
and exact unmodified render engine/quality/color management settings.
"""
import hashlib
import importlib.util
from pathlib import Path
import tempfile

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("omega_phase09_native", ROOT / "full-app/scripts/omega/phase09_vfx.py")
vfx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vfx)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
if not hasattr(scene, "cycles"):
    raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE: Cycles CPU renderer not installed")
scene.cycles.device = "CPU"
scene.cycles.samples = 4
# The Ubuntu CI Blender build omits OpenImageDenoiser. Disable denoising only
# for this synthetic fixture; never change the production render defaults.
if hasattr(scene.cycles, "use_denoising"):
    scene.cycles.use_denoising = False
for layer in scene.view_layers:
    if hasattr(layer, "cycles") and hasattr(layer.cycles, "use_denoising"):
        layer.cycles.use_denoising = False
scene.render.resolution_x = 64
scene.render.resolution_y = 64
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.use_compositing = True
scene.view_settings.view_transform = "Standard"

bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=(0, 0, 0.7))
mesh = bpy.context.object
mesh.name = "Omega09TestSphere"
mesh.data.materials.clear()
camera_data = bpy.data.cameras.new("FixtureCam")
camera = bpy.data.objects.new("FixtureCam", camera_data)
scene.collection.objects.link(camera)
camera.location = (3.1, -4.8, 2.6)
direction = Vector((0, 0, 0.7)) - camera.location
camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.camera = camera
light_data = bpy.data.lights.new("FixtureArea", "AREA")
light = bpy.data.objects.new("FixtureArea", light_data)
scene.collection.objects.link(light)
light.location = (0.0, -2.0, 4.0)
light_data.energy = 450
scene.world = bpy.data.worlds.new("FixtureWorld")
scene.world.use_nodes = True
world_background = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
world_background.inputs["Color"].default_value = (0.2, 0.35, 0.6, 1.0)
world_background.inputs["Strength"].default_value = 0.5

payload = {"object": mesh.name, "material": "Omega09FixtureMaterial",
           "base_color": [0.65, 0.27, 0.12], "roughness": 0.28,
           "metallic": 0.2, "bump_strength": 0.17,
           "contrast": 30, "gamma": 0.55, "mode": "RAW"}
ctx = {"scene": scene, "job_id": "a" * 32}
before = vfx._quality(scene)
receipt = vfx.execute("omega.vfx.create_grade", payload, ctx)
assert receipt["state"] == "succeeded" and receipt["native_execution_verified"], receipt
assert before == vfx._quality(scene), "P09 altered final render settings"
assert len(mesh.data.materials) == 1
assert "ShaderNodeBsdfPrincipled" in vfx.audit("omega.vfx.create_grade", payload, ctx)["native"]["material_nodes"]
assert vfx.audit("omega.vfx.create_grade", payload, ctx)["native"]["raw_source_linked"]
assert "ShaderNodeBump" in vfx.audit("omega.vfx.create_grade", payload, ctx)["native"]["material_nodes"]
assert len(scene.node_tree.nodes) == 4
replay = vfx.execute("omega.vfx.create_grade", payload, ctx)
assert replay["details"]["replayed"] and len(mesh.data.materials) == 1

with tempfile.TemporaryDirectory(prefix="omega-p09-bpy-") as directory:
    render_path = Path(directory) / "render.png"
    scene.render.filepath = str(render_path)
    def pixels():
        bpy.ops.render.render(write_still=True)
        assert render_path.is_file() and render_path.stat().st_size > 200
        raw = render_path.read_bytes()
        assert raw.startswith(b"\x89PNG\r\n\x1a\n"), "Renderer did not generate valid PNG signature"
        image = bpy.data.images.load(str(render_path), check_existing=False)
        try:
            assert tuple(image.size) == (64, 64), image.size
            return raw, tuple(round(float(p), 4) for p in image.pixels[:192])
        finally:
            bpy.data.images.remove(image)
    raw_png, raw_pixels = pixels()
    final = dict(payload, mode="FINAL")
    final_receipt = vfx.execute("omega.vfx.create_grade", final, {"scene": scene, "job_id": "b" * 32})
    assert final_receipt["native_execution_verified"]
    final_png, final_pixels = pixels()
    assert raw_pixels != final_pixels, "RAW and FINAL must differ in actual output pixels"
    assert raw_png != final_png, "RAW and FINAL images must differ"
    assert before == vfx._quality(scene) | {"frame_current": scene.frame_current}, "Settings changed"
    save_path = Path(directory) / "p09_saved.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(save_path))
    bpy.ops.wm.open_mainfile(filepath=str(save_path))
    restored = bpy.context.scene
    audit = vfx.audit("omega.vfx.create_grade", final, {"scene": restored})
    assert audit["native"]["mode"] == "FINAL"
    assert audit["native"]["view_layer"] == restored.view_layers[0].name
    assert restored.objects.get("Omega09TestSphere") is not None
    assert vfx._quality(restored)["engine"] == "CYCLES"
    print("PASS REAL BPY P09: saved/reopened Principled + bump + RAW/FINAL compositor")
    print("PASS REAL RENDER P09: distinct RAW/FINAL 64x64 native CPU PNG pixels",
          hashlib.sha256(raw_png).hexdigest(), hashlib.sha256(final_png).hexdigest())
    print("LIMIT: no Android ARM64 compositor / 5-minute endurance proof")
