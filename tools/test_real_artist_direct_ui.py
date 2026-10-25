# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender VIEW_3D acceptance; no fake pointer or headless sculpt claim."""
import os
from pathlib import Path
import sys
import tempfile

import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_artist_direct as Artist
import render_artist_direct_ui as UI

assert not bpy.app.background,"TEST_NEEDS_REAL_BLENDER_WINDOW"
assert bpy.context.window is not None
scene=bpy.context.scene
previous=(scene.render.engine,scene.render.resolution_x,scene.render.resolution_y,scene.render.fps)
bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,radius=.7,location=(0,0,0))
obj=bpy.context.active_object
obj.name="DirectArtistSphere"
UI.install()
assert UI.installed()
assert hasattr(bpy.types,"RENDERSTUDIO_PT_direct_artist")
initial=Artist._revision(obj)
entered=bpy.ops.renderstudio.direct_sculpt_enter()
assert "FINISHED" in entered,entered
assert obj.mode=="SCULPT",obj.mode
inspection=Artist.inspect(scene,{"object":obj.name})
assert inspection["native_window_open"]
assert inspection["mesh_revision_sha256"]==initial
assert inspection["real_brush_stroke_requires_active_sculpt_mode"]
assert inspection["connected_components"]==1
assert not inspection["surface_beauty_or_likeness_verified"]
assert len(inspection["view_revision_sha256"])==64
payload={"object":obj.name,"expected_mesh_sha256":initial,
         "expected_view_sha256":"0"*64,
         "points":[{"x":.48,"y":.5},{"x":.52,"y":.5}]}
try:
    Artist.stroke(scene,payload)
    raise AssertionError("STALE_VIEW_ACCEPTED")
except ValueError as error:
    assert str(error)=="DIRECT_SCULPT_VIEW_REVISION_CONFLICT",error
assert Artist._revision(obj)==initial,"Stale command modified Blender geometry"
payload["expected_view_sha256"]=inspection["view_revision_sha256"]
payload["expected_mesh_sha256"]="f"*64
try:
    Artist.stroke(scene,payload)
    raise AssertionError("STALE_MESH_ACCEPTED")
except ValueError as error:
    assert str(error)=="DIRECT_SCULPT_MESH_REVISION_CONFLICT",error
assert Artist._revision(obj)==initial
assert "FINISHED" in bpy.ops.renderstudio.direct_sculpt_inspect()
assert "FINISHED" in bpy.ops.renderstudio.direct_sculpt_leave()
assert obj.mode=="OBJECT"
assert Artist._revision(obj)==initial
copy=Artist.surface_clone(scene,{"object":obj.name,
    "name":"SeparateConnectedSculptCopy","voxel_size_m":.035,
    "max_voxels":1500000,"location":[2.3,0,0]})
assert copy["connected_mesh_verified"] and copy["connected_components"]==1,copy
assert copy["source_mesh_preserved"] and copy["source_animation_preserved"]
assert scene.objects.get("SeparateConnectedSculptCopy") is not None
assert Artist._revision(obj)==initial,"Sculpt copy damaged original mesh"
# Two disconnected, visibly overlapping closed volumes: an authentic
# miniature of the old character's independent anatomical rings.
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.5,location=(0,0,0))
a=bpy.context.object;a.name="DetachedBodyRings"
bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.5,location=(.45,0,0))
b=bpy.context.object
bpy.ops.object.select_all(action="DESELECT")
a.select_set(True);b.select_set(True);bpy.context.view_layer.objects.active=a
assert "FINISHED" in bpy.ops.object.join()
assert Artist._components(a)["connected_components"]==2
original_rings=Artist._revision(a)
merged=Artist.surface_clone(scene,{"object":a.name,
    "name":"RealMergedAnatomyCopy","voxel_size_m":.04,
    "max_voxels":1500000,"location":[4,0,0]})
assert merged["connected_components"]==1,merged
assert Artist._components(a)["connected_components"]==2
assert Artist._revision(a)==original_rings
assert previous==(scene.render.engine,scene.render.resolution_x,
                 scene.render.resolution_y,scene.render.fps)
print("PASS: real Blender live Sculpt Mode, actual VIEW_3D, topology and revision protection",flush=True)
print("PASS: actual native voxel-remeshed connected copy, original retained",flush=True)
print("PASS: two disconnected anatomical volumes genuinely united in a separate surface",flush=True)
print("NOT YET VERIFIED: operator sculpt stroke changed mesh or Android touch mapping",flush=True)
def close():
    bpy.ops.wm.quit_blender()
    return None
bpy.app.timers.register(close,first_interval=.5)
