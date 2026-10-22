# SPDX-License-Identifier: GPL-2.0-or-later
"""Real bpy fixture. blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase05/test_native_character.py

Set OMEGA05_RENDER_IMAGES=1 to write front, side and 3/4 real rendered PNGs
(Cycles CPU required). Never equate mechanically verified pixels to visual likeness.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

import bpy
import bmesh

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("omega_phase05_character", ROOT / "full-app/scripts/omega/phase05_character.py")
phase = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phase)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
context = {"scene": scene, "job_id": "1" * 32, "dry_run": False,
           "available_memory_bytes": 1_000_000_000}
args = {"name": "SyntheticHero", "height_m": 1.75}
count_before = len(scene.objects)
receipt = phase.execute("omega.character.create", args, context)
assert receipt["state"] == "succeeded" and receipt["native_execution_verified"] is True, receipt
assert receipt["character_stage"] == "SCULPTED", receipt
assert receipt["visual_quality_verified"] is False
assert receipt["mesh_vertices"] > 3000 and receipt["mesh_faces"] > 3000
assert len(scene.objects) > count_before
assert all(receipt["checks"].values()), receipt
coll = bpy.data.collections[receipt["collection"]]
assert coll["omega_mesh_seams"].count(";") >= 4
assert len(json.loads(coll["omega_landmarks_json"])) >= 20
for ob in coll.objects:
    if ob.type != "MESH":
        continue
    assert ob.data.uv_layers, ob.name
    bm = bmesh.new()
    try:
        bm.from_mesh(ob.data)
        assert len(bm.faces) > 0, ob.name
        assert all(edge.is_manifold for edge in bm.edges), "Non-manifold edge: " + ob.name
        assert all(face.calc_area() > 1e-10 for face in bm.faces), "Degenerate polygon: " + ob.name
    finally:
        bm.free()
# Replay is idempotent, conflicts are not allowed to overwrite the character.
count_created = len(scene.objects)
replay = phase.execute("omega.character.create", args, context)
assert replay["already_complete"] and len(scene.objects) == count_created
try:
    phase.execute("omega.character.create", dict(args, height_m=1.81), context)
except ValueError as exc:
    assert str(exc) == "CHECKPOINT_CONFLICT"
else:
    raise AssertionError("Different source revisions must never overwrite the asset")
audit = phase.audit("omega.character.audit", {"name":"SyntheticHero"}, context)
assert audit["created"] == [] and audit["mesh_faces"] == receipt["mesh_faces"]
# Revision-specific export interface for Phase 06 without importing its code.
assert audit["landmarks"]["LeftKnee"][0] < 0 < audit["landmarks"]["RightKnee"][0]

output = Path(os.environ.get("OMEGA05_OUTPUT_DIR") or tempfile.mkdtemp(prefix="omega05-native-"))
output.mkdir(parents=True,exist_ok=True)
blend = output / "SyntheticHero.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
assert blend.read_bytes().startswith(b"BLENDER")
sha = hashlib.sha256(blend.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(blend))
reopened = bpy.context.scene
post = phase.audit("omega.character.audit", {"name":"SyntheticHero"}, {"scene":reopened})
assert post["mesh_vertices"] == receipt["mesh_vertices"], (post,receipt)
assert post["mesh_faces"] == receipt["mesh_faces"]
assert post["source_revision"] == receipt["source_revision"]
assert post["view_cameras"] == receipt["view_cameras"]

images = []
if os.environ.get("OMEGA05_RENDER_IMAGES") == "1":
    scene = bpy.context.scene
    if "CYCLES" not in [enum.identifier for enum in scene.render.bl_rna.properties["engine"].enum_items]:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE: Cycles CPU renderer unavailable")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 6
    scene.render.resolution_x = 256
    scene.render.resolution_y = 352
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    data = bpy.data.lights.new("SyntheticLight", type="AREA")
    lamp = bpy.data.objects.new("SyntheticLight", data)
    scene.collection.objects.link(lamp)
    lamp.location = (0,-2,3.8)
    data.energy = 900
    for label in ("Front", "Side", "ThreeQuarter"):
        scene.camera = bpy.data.objects["Omega_SyntheticHero_"+label+"Camera"]
        dst = output / (label + ".png")
        scene.render.filepath = str(dst)
        bpy.ops.render.render(write_still=True)
        assert dst.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), dst
        im = bpy.data.images.load(str(dst), check_existing=False)
        try:
            assert tuple(im.size) == (256,352), im.size[:]
        finally:
            bpy.data.images.remove(im)
        images.append({"path":str(dst), "sha256":hashlib.sha256(dst.read_bytes()).hexdigest()})
print(json.dumps({"state":"PASS","engine":"real_bpy","blend":str(blend),
                  "blend_sha256":sha,"reopened_vertices":post["mesh_vertices"],
                  "reopened_faces":post["mesh_faces"],"views":post["view_cameras"],
                  "images":images,"visual_quality_verified":False},sort_keys=True))
