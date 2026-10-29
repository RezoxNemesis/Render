# SPDX-License-Identifier: GPL-2.0-or-later
"""Windowed Blender N-panel smoke, never interpreted as Android device proof."""
import os
from pathlib import Path
import sys
import tempfile
import bpy
from mathutils import Quaternion

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_unified_workspace as S

assert not bpy.app.background,"Must execute with genuine Blender window"
folder=Path(tempfile.mkdtemp(prefix="render-unified-ui-"))
spool=folder/"render_bpy_jobs"
spool.mkdir()
os.environ["RENDER_AGENT_SPOOL"]=str(spool)
assert bpy.context.window is not None,"No live Blender window was created"
assert any(a.type=="VIEW_3D" for a in bpy.context.window.screen.areas)
S.install_ui()
assert S.INSTALLED
assert hasattr(bpy.types.Scene,"render_studio_section")
assert getattr(bpy.types,"RENDERSTUDIO_PT_unified_workspaces",None) is not None
scene=bpy.context.scene
selection=S.execute("studio.workspace.activate",{
    "workspace":"sculpt","show_sidebar":True},S._root(),scene)
assert selection["actual_scene_workspace_changed"]
assert scene.render_studio_section=="sculpt"
before=[area.spaces.active.region_3d.view_rotation.copy()
        for area in S._areas()]
rotation=S.execute("studio.view.orbit",{
    "yaw_degrees":17,"pitch_degrees":4,"zoom":.84},S._root(),scene)
assert rotation["native_view_rotation_applied"]
assert len(rotation["actual_blender_viewports"])==len(before)
changed=[area.spaces.active.region_3d.view_rotation.copy()
         for area in S._areas()]
assert any(sum(abs(u[i]-v[i]) for i in range(4))>.01
           for u,v in zip(before,changed)),"Native viewport did not actually move"
# A current source editor can be changed by an agent without fabricated clicks.
graph=S.execute("studio.editor.open",{"editor":"GRAPH_EDITOR"},S._root(),scene)
assert graph["native_editor_changed"],graph
restored=S.execute("studio.editor.open",{"editor":"VIEW_3D"},S._root(),scene)
assert restored["native_editor_changed"] and S._areas(),restored
assert not S.execute("studio.capabilities",{},S._root(),scene)["background_bpy"]
print("PASS: genuine Blender UI registered; workspace visible; real view rotated/zoomed; Graph Editor switched and restored",flush=True)
print("NOT PROVEN: Android GPU UI behavior, touch latency, or live phone screenshot",flush=True)
def quit_after_test():
    bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(quit_after_test,first_interval=.25)
