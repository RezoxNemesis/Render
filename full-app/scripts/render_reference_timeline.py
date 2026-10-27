# SPDX-License-Identifier: GPL-2.0-or-later
"""Owner-imported MP4 timeline guides inside the actual Blender project.

The native Sequencer strip follows bpy scene frames. An IMAGE_EDITOR preview
may be a real movie or a SHA-verified sampled still when Android lacks a movie
decoder. Never claim VSE timeline time == proof of decoded frame pixels.
"""
import math
import re
from pathlib import Path

import bpy

NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
ASSET=re.compile(r"^[a-f0-9]{64}\.(?:png|jpg|jpeg|webp|mp4)$")
OPS=frozenset(("studio.reference.timeline.bind",
               "studio.reference.timeline.inspect",
               "studio.reference.timeline.scrub"))
MUTATE=OPS-{"studio.reference.timeline.inspect"}

def _fields(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_VIDEO_FIELDS_INVALID")

def _name(x):
    if not isinstance(x,str) or not NAME.fullmatch(x):
        raise ValueError("STUDIO_VIDEO_NAME_INVALID")
    return x

def _frame(x):
    if type(x) is not int or not 1<=x<=1000000:
        raise ValueError("STUDIO_VIDEO_FRAME_INVALID")
    return x

def _asset(root,name,require_movie=False):
    if not isinstance(name,str) or not ASSET.fullmatch(name):
        raise ValueError("STUDIO_VIDEO_OWNER_ASSET_INVALID")
    if require_movie and not name.endswith(".mp4"):
        raise ValueError("STUDIO_VIDEO_MP4_REQUIRED")
    if not require_movie and name.endswith(".mp4"):
        raise ValueError("STUDIO_VIDEO_SAMPLE_IMAGE_REQUIRED")
    # Existing hash-and-ownership validator rejects path escapes/symlinks.
    from render_studio_ops import _asset as existing_asset
    return existing_asset(Path(root),name)

def _strips(scene):
    editor=scene.sequence_editor
    if editor is None:return []
    result=getattr(editor,"strips",None)
    if result is None:result=getattr(editor,"sequences",None)
    return [] if result is None else result

def _movie(scene,name):
    strip=next((s for s in _strips(scene) if s.name==_name(name)),None)
    if strip is None or strip.type!="MOVIE":
        raise ValueError("STUDIO_VIDEO_STRIP_NOT_FOUND")
    return strip

def _owner_movie(strip,root):
    native_path=Path(bpy.path.abspath(strip.filepath)).resolve()
    filename=native_path.name
    owned=_asset(root,filename,require_movie=True)
    if native_path!=owned.resolve():
        raise ValueError("STUDIO_VIDEO_EXTERNAL_STRIP_NOT_OWNED")
    return filename

def _metadata(strip,asset):
    final_start=int(strip.frame_final_start)
    final_end=int(strip.frame_final_end)
    if final_end<=final_start:
        raise ValueError("STUDIO_VIDEO_STRIP_EMPTY")
    source_fps=getattr(strip,"fps",None)
    if type(source_fps) not in (int,float) or not math.isfinite(source_fps) or source_fps<=0:
        source_fps=None
    return {"strip":strip.name,"asset":asset,"type":strip.type,
            "channel":int(strip.channel),
            "scene_frame_start":final_start,
            "scene_frame_end_exclusive":final_end,
            "duration_scene_frames":final_end-final_start,
            "native_sequencer_strip":True,
            "source_fps_reported":float(source_fps) if source_fps else None,
            "native_movie_frame_decode_verified":False}

def bind(scene,root,p):
    _fields(p,("asset","name","start_frame","channel","display",
               "preview_asset","model","split_factor"),
            ("asset","name"))
    name=_name(p["name"])
    start=_frame(p.get("start_frame",scene.frame_current))
    channel=p.get("channel",1)
    if type(channel) is not int or not 1<=channel<=16:
        raise ValueError("STUDIO_VIDEO_CHANNEL_INVALID")
    display=p.get("display","NONE")
    if display not in ("NONE","SPLIT","CAMERA"):
        raise ValueError("STUDIO_VIDEO_DISPLAY_MODE_INVALID")
    if "preview_asset" in p:
        if display=="NONE":raise ValueError("STUDIO_VIDEO_PREVIEW_REQUIRES_DISPLAY")
        _asset(root,p["preview_asset"],require_movie=False)
    if "model" in p:_name(p["model"])
    factor=p.get("split_factor",.52)
    if type(factor) not in (int,float) or not math.isfinite(factor) or not .3<=factor<=.7:
        raise ValueError("STUDIO_VIDEO_SPLIT_FACTOR_INVALID")
    original=_asset(root,p["asset"],require_movie=True)
    editor=scene.sequence_editor_create()
    collection=getattr(editor,"strips",None)
    if collection is None:collection=getattr(editor,"sequences",None)
    if collection is None:
        raise ValueError("STUDIO_NATIVE_VIDEO_SEQUENCER_UNAVAILABLE")
    existing=collection.get(name)
    if existing:
        if existing.type!="MOVIE" or existing.filepath!=str(original) or (
                existing.frame_start!=start or existing.channel!=channel):
            raise ValueError("STUDIO_VIDEO_NAME_CONFLICT")
        strip=existing;reused=True
    else:
        # No unscoped path; the original is in verified app-private Assets.
        try:strip=collection.new_movie(name,str(original),channel,start)
        except (RuntimeError,OSError,ValueError) as exc:
            raise ValueError("STUDIO_NATIVE_VIDEO_STRIP_DECODER_UNAVAILABLE") from exc
        reused=False
    result=_metadata(strip,original.name)
    result.update(reused_existing_strip=reused,
                  scene_fps=scene.render.fps/scene.render.fps_base,
                  original_video_kept=True,
                  scene_fps_modified=False,
                  source_audio_imported=False,
                  native_preview_pane_available=False,
                  side_by_side_pixels_verified=False)
    if display!="NONE":
        params={"asset":original.name,
                "mode":"SPLIT" if display=="SPLIT" else "CAMERA"}
        if "preview_asset" in p:params["preview_asset"]=p["preview_asset"]
        if "model" in p:params["model"]=p["model"]
        params["split_factor"]=factor
        try:
            import render_reference_motion
            preview=render_reference_motion.execute(
                "reference.workspace.open",params,root,scene)
            result["native_preview_pane_available"]=preview["native_blender_panel_assigned"]
            result["preview_mode"]=preview["mode"]
            result["video_scrubbing_native"]=preview.get("video_scrubbing_native",False)
            result["still_frame_sample_used"]=preview.get("still_frame_sample_used",False)
        except (ValueError,RuntimeError,AttributeError,TypeError):
            # Original video strip remains in the Blender timeline; a missing
            # Android Image Editor or codec must never destroy an imported movie.
            result["native_preview_pane_available"]=False
            result["preview_error"]="NATIVE_REFERENCE_PANE_OR_DECODER_UNAVAILABLE"
            result["preview_fallback"]="Use reference.video_frame then preview_asset"
    return result

def inspect(scene,root,p):
    _fields(p,("name","limit"))
    limit=p.get("limit",16)
    if type(limit) is not int or not 1<=limit<=32:
        raise ValueError("STUDIO_VIDEO_PAGE_INVALID")
    if "name" in p:rows=[_movie(scene,p["name"])]
    else:rows=[s for s in _strips(scene) if s.type=="MOVIE"][:limit]
    clips=[]
    for row in rows:
        try:
            name=_owner_movie(row,root)
            clips.append(_metadata(row,name))
        except ValueError:
            if "name" in p:raise
            # Do not disclose foreign media paths owned by another project.
            continue
    return {"clips":clips,"current_scene_frame":scene.frame_current,
            "blender_scene_fps":scene.render.fps/scene.render.fps_base,
            "owner_sources_verified_by_sha256":True,
            "video_frame_pixels_verified":False,
            "no_gallery_search_performed":True,
            "native_editor_scene_modified":False}

def _reference_editor():
    window=bpy.context.window
    if window is None or not window.screen:return None
    for area in window.screen.areas:
        if area.type!="IMAGE_EDITOR":continue
        im=area.spaces.active.image
        if im is not None and im.get("render_reference_workspace",False):
            return area
    return None

def scrub(scene,root,p):
    _fields(p,("name","frame","preview_asset"),("name","frame"))
    strip=_movie(scene,p["name"])
    original=_owner_movie(strip,root)
    requested=_frame(p["frame"])
    meta=_metadata(strip,original)
    start,end=meta["scene_frame_start"],meta["scene_frame_end_exclusive"]
    if not start<=requested<end:
        raise ValueError("STUDIO_VIDEO_FRAME_OUTSIDE_STRIP")
    preview=None
    if "preview_asset" in p:
        preview=_asset(root,p["preview_asset"],require_movie=False)
    area=_reference_editor()
    if preview is not None and area is not None:
        try:
            image=bpy.data.images.load(str(preview),check_existing=True)
            if min(image.size[:2])<1:
                raise ValueError("STUDIO_VIDEO_SAMPLE_CORRUPT")
            if not image.packed_file:image.pack()
            image["render_reference_workspace"]=True
            image["render_reference_source"]=original
            image["render_reference_preview"]=preview.name
            area.spaces.active.image=image
            area.tag_redraw()
        except (OSError,RuntimeError,ValueError) as exc:
            raise ValueError("STUDIO_VIDEO_PREVIEW_UPDATE_FAILED") from exc
    old=scene.frame_current
    scene.frame_set(requested)
    for window in bpy.context.window_manager.windows:
        for window_area in window.screen.areas:
            if window_area.type in ("IMAGE_EDITOR","VIEW_3D","SEQUENCE_EDITOR",
                                    "DOPESHEET_EDITOR"):
                window_area.tag_redraw()
    result=dict(meta,scene_frame_now=scene.frame_current,
                scene_frame_was=old,
                video_timeline_in_range=True,
                approximate_source_frame_index=requested-start,
                actual_blender_scene_frame_changed=scene.frame_current!=old,
                preview_sample_asset=preview.name if preview is not None else None,
                preview_editor_updated=preview is not None and area is not None,
                movie_frame_pixels_decoded=False,
                matching_3d_pose_evaluated=True,
                manual_video_frame_sample_required_if_decoder_missing=True)
    return result

def execute(op,p,root,scene):
    if op=="studio.reference.timeline.bind":return bind(scene,root,p)
    if op=="studio.reference.timeline.inspect":return inspect(scene,root,p)
    if op=="studio.reference.timeline.scrub":return scrub(scene,root,p)
    raise ValueError("STUDIO_REFERENCE_TIMELINE_OPERATION_UNAVAILABLE")

def capabilities():
    asset={"type":"string","pattern":ASSET.pattern}
    title={"type":"string","pattern":NAME.pattern}
    props={"name":title,"asset":asset,"start_frame":{"type":"integer","minimum":1},
           "channel":{"type":"integer","minimum":1,"maximum":16},
           "display":{"enum":["NONE","SPLIT","CAMERA"]},
           "preview_asset":asset,"model":title,
           "split_factor":{"type":"number","minimum":.3,"maximum":.7},
           "frame":{"type":"integer","minimum":1,"maximum":1000000},
           "limit":{"type":"integer","minimum":1,"maximum":32}}
    defs=(
      ("studio.reference.timeline.bind",False,("asset","name"),
       ("asset","name","start_frame","channel","display",
        "preview_asset","model","split_factor")),
      ("studio.reference.timeline.inspect",True,(),("name","limit")),
      ("studio.reference.timeline.scrub",False,("name","frame"),
       ("name","frame","preview_asset"))
    )
    return [
        {"operation":op,"workspace":"assets","read_only":read,
         "input_schema":{"type":"object","properties":{k:props[k] for k in fields},
                         "required":list(required),"additionalProperties":False},
         "native_video_pixel_decode_not_guaranteed":True}
         for op,read,required,fields in defs]
