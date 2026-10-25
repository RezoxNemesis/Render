# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Blender window test: sculpt edit, live HUD marker and projection.

Never a fake mouse click, headless-only unit test or Android phone acceptance.
"""
import os
from pathlib import Path
import sys
import tempfile
import bpy

assert not bpy.app.background,"Windowed Blender required"
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_live_gestures as G
import render_native_hud as HUD

scratch=Path(tempfile.mkdtemp(prefix="render-hud-live-"))
spool=scratch/"render_bpy_jobs";spool.mkdir()
os.environ["RENDER_AGENT_SPOOL"]=str(spool)
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=10,
                                    location=(0,0,1))
ob=bpy.context.object
ob.name="VerifiedSculptActor"
scene=bpy.context.scene
before=G.mesh_inspect(scene,{"object":ob.name})
command={"object":ob.name,"expected_sha256":before["mesh_revision_sha256"],
         "expected_vertices":before["vertices"],"center":[.35,0,.15],
         "direction":[0,0,1],"radius":.88,
         "strength":.17,"mirror_x":True}
result=G.sculpt(scene,command)
assert result["native_blender_vertex_coordinates_updated"]
assert result["vertices_changed"]>0
HUD.install(lambda:None)
HUD.command_started({"args":{"operation":"studio.sculpt.brush","payload":command}})
HUD.command_finished({"state":"succeeded","result":result})
assert HUD.snapshot()["verified_sculpt_marker"]["object"]==ob.name
assert HUD.snapshot()["fabricated_ui_taps"] is False
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type=="VIEW_3D":area.tag_redraw()

cycles=[0]
def verify_and_quit():
    cycles[0]+=1
    snap=HUD.snapshot()
    if not snap["viewport_draw_observed"] and cycles[0]<12:
        return .5
    assert snap["viewport_draw_observed"],"Genuine Blender draw handler never fired"
    assert snap["last_draw_error"] is None, snap["last_draw_error"]
    marker=snap["verified_sculpt_marker"]
    assert marker and marker["source"]=="native_bpy_vertex_edit",marker
    print("PASS: actual Blender visible HUD projected a verified sculpt center",flush=True)
    print("PASS: native draw handler and GPU card reported zero draw errors",flush=True)
    print("NOT TESTED: Android phone GPU, touchscreen latency and photorealism",flush=True)
    bpy.ops.wm.quit_blender()
    return None

bpy.app.timers.register(verify_and_quit,first_interval=.7)
