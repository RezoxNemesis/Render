# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender VSE movie and synchronized camera/reference frame tests.

Generate a synthetic local MP4 with test FFmpeg, import by verified source SHA.
No Gallery, external owner's footage, fake movie pixels or rendered benchmark.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_reference_timeline as RT
import render_production
import render_unified_workspace as Studio

with tempfile.TemporaryDirectory() as tmp:
    spool=Path(tmp)/"render_bpy_jobs";spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"]=str(spool)
    root=Path(tmp)/"Production";assets=root/"Assets";assets.mkdir(parents=True)
    original=assets/"synthetic-source.mp4"
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
        "-f","lavfi","-i","testsrc2=size=128x96:rate=24",
        "-frames:v","48","-pix_fmt","yuv420p",
        "-c:v","mpeg4",str(original)],check=True)
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    source=assets/(digest+".mp4");original.rename(source)
    assert source.stat().st_size>1000
    scene=bpy.context.scene
    before=(scene.render.engine,scene.render.fps,scene.render.fps_base,
            scene.render.resolution_x,scene.render.resolution_y)

    first=render_production.execute({"operation":"studio.reference.timeline.bind",
        "payload":{"asset":source.name,"name":"ShotReference",
                   "start_frame":10,"channel":4,
                   "display":"NONE"}},str(spool),"a"*32)
    assert first["native_sequencer_strip"]
    assert first["original_video_kept"]
    assert first["scene_frame_start"]==10
    assert first["duration_scene_frames"]>=45,first
    assert not first["native_movie_frame_decode_verified"]
    assert not first["native_preview_pane_available"]
    reused=RT.bind(scene,root,{"asset":source.name,"name":"ShotReference",
                              "start_frame":10,"channel":4})
    assert reused["reused_existing_strip"]
    clips=RT.inspect(scene,root,{"name":"ShotReference"})
    assert len(clips["clips"])==1 and clips["clips"][0]["asset"]==source.name

    scene.frame_set(1)
    ref=RT.scrub(scene,root,{"name":"ShotReference","frame":25})
    assert ref["video_timeline_in_range"] and scene.frame_current==25
    assert ref["approximate_source_frame_index"]==15
    assert not ref["movie_frame_pixels_decoded"]
    assert before==(scene.render.engine,scene.render.fps,scene.render.fps_base,
                    scene.render.resolution_x,scene.render.resolution_y)
    for bad_frame in (1,9,ref["scene_frame_end_exclusive"],1000001):
        try:
            RT.scrub(scene,root,{"name":"ShotReference","frame":bad_frame})
            raise AssertionError("Out-of-strip movie frame accepted")
        except ValueError:pass

    # Synthesized one-frame still is a verified fallback, NOT an invented
    # live-video decoder. Native Blender camera background really displays it.
    generated=bpy.data.images.new("LocalTestStill",width=96,height=96,alpha=True)
    generated.generated_type="COLOR_GRID"
    temp_png=assets/"synthetic-frame.png"
    generated.file_format="PNG";generated.filepath_raw=str(temp_png)
    generated.save()
    bpy.data.images.remove(generated)
    hash_png=hashlib.sha256(temp_png.read_bytes()).hexdigest()
    still=assets/(hash_png+".png");temp_png.rename(still)
    cam=bpy.data.objects.new("ReferenceTestCamera",bpy.data.cameras.new("RefCamData"))
    scene.collection.objects.link(cam);scene.camera=cam
    second=RT.bind(scene,root,{
        "asset":source.name,"name":"AdditionalShotReference",
        "start_frame":55,"channel":5,
        "display":"CAMERA","preview_asset":still.name})
    assert second["native_preview_pane_available"],second
    assert second["still_frame_sample_used"] and not second["video_scrubbing_native"]
    assert scene.camera.data.background_images
    assert scene.camera.data.background_images[-1].image.packed_file is not None
    at=RT.scrub(scene,root,{"name":"ShotReference",
                            "frame":26,"preview_asset":still.name})
    assert at["preview_sample_asset"]==still.name
    assert not at["preview_editor_updated"] # Headless Blender has no image pane.

    # No non-owner strip can be laundered through a SHA-formatted basename.
    strip=scene.sequence_editor.sequences.get("ShotReference")
    strip.filepath=str(Path(tmp)/source.name)
    try:
        RT.inspect(scene,root,{"name":"ShotReference"})
        raise AssertionError("Unowned VSE file path accepted")
    except ValueError as e:
        assert "STUDIO_VIDEO_EXTERNAL_STRIP_NOT_OWNED" in str(e)
    strip.filepath=str(source)
    assert RT.inspect(scene,root,{"name":"ShotReference"})["clips"]
    checkpoints=list((root/"Projects").glob("*.blend"))
    assert len(checkpoints)>=1
    print("PASS: actual Blender VSE imported original SHA-verified MP4",source.stat().st_size,flush=True)
    print("PASS: VSE timeline at scene frame 25, sampled native camera background still, owned-path checks",flush=True)
    print("NOT VERIFIED: Android hardware movie decoder, real phone split pane or matching still pixels per frame",flush=True)
