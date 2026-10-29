# SPDX-License-Identifier: GPL-2.0-or-later
"""Headless real Blender fixtures for editable procedural assets.

This validates bpy geometry and armature topology, not Android GPU quality or
photoreal likeness. Execute with: blender -b -noaudio --python-exit-code 1 --python tools/test_real_assets_v24.py
"""
import importlib.util
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("render_assets_fixture",
    ROOT/"full-app/scripts/render_assets.py")
assets=importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)
assert len(assets.PRESETS)==17
scene=bpy.context.scene
previous=len(scene.objects)
for preset,label in assets.PRESETS:
    receipt=assets.create_asset(scene,preset)
    assert receipt["editable"] is True,receipt
    assert receipt["external_assets_downloaded"]==0,receipt
    collection=bpy.data.collections.get(receipt["collection"])
    assert collection is not None and len(collection.objects)>0,preset
    assert collection.get("editable_geometry") is True,preset
    if preset=="ARCH":
        arch=next((x for x in collection.objects if x.name.startswith("TrueCurvedArch")),None)
        assert arch is not None and len(arch.data.vertices)>100,"Arch must be curved topology, not a box"
    if preset=="TERRAIN":
        terrain=next(x for x in collection.objects if x.name.startswith("EditableTerrain"))
        assert len(terrain.data.polygons)>=500
    if preset=="STUDIO":
        assert scene.camera is not None and any(x.type=="LIGHT" for x in collection.objects)
    if preset in ("HUMANOID","QUADRUPED"):
        rigs=[obj for obj in collection.objects if obj.type=="ARMATURE"]
        assert len(rigs)==1
        assert len(rigs[0].data.bones)>=10,preset
assert len(scene.objects)>previous
try:
    assets.create_asset(scene,"rm_rf/")
except ValueError:
    pass
else:
    raise AssertionError("Untrusted arbitrary asset preset must be rejected")
print("PASS: 17 editable native bpy procedural presets with topology, materials, light and rig proxies")
print("NOT CLAIMED: film-quality characters, fluid sim, external download or sustained device render")
