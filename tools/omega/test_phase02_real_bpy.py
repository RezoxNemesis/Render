# SPDX-License-Identifier: GPL-2.0-or-later
"""Native Blender bpy integration (not a mock).

Run from repository root:
blender -b -noaudio --python-exit-code 1 --python tools/omega/test_phase02_real_bpy.py

Renders five tiny Cycles PNGs using real bpy; tests kill/restart by clearing
process state and recovering the saved manifest. Requires a real Blender build.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import bpy

SCRIPTS = Path(__file__).resolve().parents[2] / "full-app/scripts"
sys.path.insert(0, str(SCRIPTS))
import render_production as Production
from omega import phase02_render as Durable

with tempfile.TemporaryDirectory(prefix="omega-native-render-") as directory:
    folder = Path(directory)
    spool = str(folder / "render_spool")
    scene = bpy.context.scene
    assert scene is not None
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 1
    # The CI Blender binary may be built without OpenImageDenoiser. This
    # lossless checkpoint/resume fixture explicitly requests no denoiser;
    # never change user-requested denoising in the installed Render engine.
    if hasattr(scene.cycles, "use_denoising"):
        scene.cycles.use_denoising = False
    for view in scene.view_layers:
        if hasattr(view, "cycles") and hasattr(view.cycles, "use_denoising"):
            view.cycles.use_denoising = False
    scene.render.resolution_x = 16
    scene.render.resolution_y = 16
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.fps_base = 1.001
    scene.frame_start = 101
    scene.frame_end = 105

    camera_data = bpy.data.cameras.new("Omega2Camera")
    camera = bpy.data.objects.new("Omega2Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0, -6, 3)
    camera.rotation_euler = (1.10, 0, 0)
    scene.camera = camera

    mesh = bpy.data.meshes.new("Omega2Mesh")
    mesh.from_pydata([(-1, -1, -1), (1, -1, -1), (0, 1, 1)],
                     [], [(0, 1, 2)])
    mesh.update()
    obj = bpy.data.objects.new("Omega2NativeTriangle", mesh)
    scene.collection.objects.link(obj)

    light_data = bpy.data.lights.new("Omega2Light", "AREA")
    light = bpy.data.objects.new("Omega2Light", light_data)
    scene.collection.objects.link(light)
    light.location = (1, -2, 4)
    light_data.energy = 500

    saved_count = len(scene.objects)
    render_spec = {
        "start": 101, "end": 105, "width": 16, "height": 16,
        "fps": 24, "engine": "CYCLES", "samples": 1,
        "bitrate": 16000000, "output_kind": "ANIMATION",
    }
    receipt = Production.execute(
        {"operation": "render.plan", "payload": render_spec},
        spool, "omega-phase2-test")
    job = receipt["job_id"]
    jobfolder = folder / "Production" / job
    manifest = json.loads((jobfolder / "manifest.json").read_text())
    assert abs(manifest["spec"]["fps_base"] - 1.001) < 0.0001
    assert manifest["snapshot"]["sha256"] == Durable._hash_file(
        jobfolder / "snapshot.blend")
    assert manifest["spec"]["samples"] == 1

    baseline = {}
    for frame in (101, 102, 103):
        result = Production.execute(
            {"operation": "render.step", "payload": {"job_id": job}},
            spool, "omega-phase2-test")
        assert result["next_frame"] == frame + 1, result
        path = jobfolder / ("frame_%06d.png" % frame)
        image = Durable.png_proof(path)
        assert (image["width"], image["height"]) == (16, 16), image
        baseline[frame] = (path.stat().st_mtime_ns, image["sha256"])

    # Simulated Android process death: the next Python runtime has no cache.
    Durable._JOB_CACHE.clear()
    resumed = []
    for frame in (104, 105):
        result = Production.execute(
            {"operation": "render.step", "payload": {"job_id": job}},
            spool, "omega-phase2-restarted")
        resumed.append(frame)
        assert result["next_frame"] == frame + 1, result
    assert resumed == [104, 105]
    assert result["state"] == "frames_complete"
    assert result["completed_frames"] == 5
    for frame in (101, 102, 103):
        path = jobfolder / ("frame_%06d.png" % frame)
        assert (path.stat().st_mtime_ns, Durable.png_proof(path)["sha256"]) == baseline[frame]

    # Native corrupted master must be detected and rendered anew on restart.
    bad = jobfolder / "frame_000102.png"
    bad.write_bytes(b"not an image" * 20)
    Durable._JOB_CACHE.clear()
    result = Production.execute(
        {"operation": "render.step", "payload": {"job_id": job}},
        spool, "omega-phase2-recovery")
    assert result["next_frame"] == 106, result
    assert Durable.png_proof(bad)["width"] == 16
    assert Durable.png_proof(jobfolder / "frame_000103.png")["sha256"] == baseline[103][1]
    assert scene.render.engine == "CYCLES"
    assert scene.cycles.samples == 1
    assert (scene.render.resolution_x, scene.render.resolution_y) == (16, 16)
    assert abs(scene.render.fps_base - 1.001) < 0.0001
    snapshot = jobfolder / "snapshot.blend"
    result_open = bpy.ops.wm.open_mainfile(filepath=str(snapshot), load_ui=False)
    assert "FINISHED" in result_open
    restored = bpy.data.scenes.get(manifest["source_scene"])
    assert restored is not None
    assert restored.objects.get("Omega2NativeTriangle") is not None
    assert len(restored.objects) == saved_count
    assert restored.render.engine == "CYCLES"
    assert abs(restored.render.fps_base - 1.001) < 0.0001
    print("PASS: real bpy Cycles native render frames 101-105; restart 104/105 only;")
    print("PASS: corrupt PNG repaired, SHA CRC dimensions and source snapshot reopened;")
    print("PASS: native samples/engine/dimensions/fps_base unchanged, no downgrade.")
    print("NOT TESTED: Android GPU, MediaCodec H264 and phone thermal stability.")
