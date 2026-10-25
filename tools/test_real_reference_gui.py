# SPDX-License-Identifier: GPL-2.0-or-later
"""Genuine Blender window: hashed owner MP4 and side-by-side sampled preview.

Checks actual Image Editor plus 3D viewport, no fabricated screen capture.
Android touchscreen/codec acceptance remains separate.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import bpy

assert not bpy.app.background, "Windowed Blender UI required"
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_reference_timeline as RT

tmp=Path(tempfile.mkdtemp(prefix="render-reference-gui-"))
spool=tmp/"render_bpy_jobs";spool.mkdir()
os.environ["RENDER_AGENT_SPOOL"]=str(spool)
production=tmp/"Production";assets=production/"Assets";assets.mkdir(parents=True)
source=assets/"test.mp4"
subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i","color=c=teal:size=128x96:rate=24",
                "-frames:v","32","-pix_fmt","yuv420p","-c:v","mpeg4",
                str(source)],check=True)
mp4_hash=hashlib.sha256(source.read_bytes()).hexdigest()
mp4=assets/(mp4_hash+".mp4");source.rename(mp4)

img=bpy.data.images.new("SampleImage",width=96,height=96,alpha=True)
img.generated_type="COLOR_GRID"
png=assets/"still.png"
img.file_format="PNG";img.filepath_raw=str(png)
img.save();bpy.data.images.remove(img)
still_hash=hashlib.sha256(png.read_bytes()).hexdigest()
still=assets/(still_hash+".png");png.rename(still)

scene=bpy.context.scene
result=RT.bind(scene,production,{"asset":mp4.name,
                                "name":"BenchmarkIn3DStudio",
                                "start_frame":4,"channel":2,
                                "display":"SPLIT","preview_asset":still.name,
                                "split_factor":.52})
assert result["native_sequencer_strip"] and result["original_video_kept"],result
assert result["native_preview_pane_available"],result
assert result["still_frame_sample_used"] and not result["video_scrubbing_native"],result
assert bpy.context.window is not None
areas=bpy.context.window.screen.areas
image_areas=[a for a in areas if a.type=="IMAGE_EDITOR" and a.spaces.active.image is not None]
model_areas=[a for a in areas if a.type=="VIEW_3D"]
assert image_areas and model_areas,[(a.type,a.width) for a in areas]
current=image_areas[0].spaces.active.image
assert current.get("render_reference_source")==mp4.name
assert current.packed_file is not None
assert current.get("render_reference_preview")==still.name

frame=RT.scrub(scene,production,{"name":"BenchmarkIn3DStudio","frame":15})
assert frame["video_timeline_in_range"] and scene.frame_current==15,frame
assert not frame["movie_frame_pixels_decoded"]
print("PASS: windowed native Blender original movie VSE + side-by-side Image Editor and VIEW_3D",flush=True)
print("PASS: original sampled still packed and tracked, Blender animation timeline synced",flush=True)
print("NOT VERIFIED: physical Android image panel, native MP4 frame decoding or live phone screen",flush=True)

def close():
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(close,first_interval=.35)
