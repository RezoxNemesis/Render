# SPDX-License-Identifier: GPL-2.0-or-later
"""Real bpy fixture for Phase 12: mesh measurements, bounded proposal and save/reopen.

blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase12/test_phase12_native_bpy.py

Blender only: this cannot be passed by a host-side bpy mock. Blender is not
available in every runner. No on-phone GPU or photoreal likeness is implied.
"""
import copy
import importlib.util
from pathlib import Path
import tempfile

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "full-app/scripts/omega/phase12_quality.py"
spec = importlib.util.spec_from_file_location("native_phase12_quality", SOURCE)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)


def bad_character_fixture(scene):
    ring_levels = ((0.45, 0.36), (1.18, 0.4), (1.65, 0.95),
                   (1.91, 0.15), (2.24, 0.18), (2.54, 0.18))
    verts = []
    for z, half in ring_levels:
        verts.extend(((-half, -0.16, z), (half, -0.16, z),
                      (half, 0.16, z), (-half, 0.16, z)))
    faces = []
    for ring in range(5):
        if ring == 2:  # physical gap at neck/shoulders; two disconnected islands
            continue
        a, b = 4 * ring, 4 * (ring + 1)
        faces.extend((a + i, a + (i + 1) % 4, b + (i + 1) % 4, b + i)
                     for i in range(4))
    mesh = bpy.data.meshes.new("BadCharacterEditableTopology")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new("CharacterBody", mesh)
    scene.collection.objects.link(ob)
    material = bpy.data.materials.new("FixtureMaterial")
    mesh.materials.append(material)
    return ob


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    obj = bad_character_fixture(scene)
    camera = bpy.data.cameras.new("Phase12Camera")
    camera_obj = bpy.data.objects.new("Phase12Camera", camera)
    scene.collection.objects.link(camera_obj)
    camera_obj.location = (0.0, -7.0, 2.0)
    camera_obj.rotation_euler = (1.57079632679, 0, 0)
    scene.camera = camera_obj
    review = bpy.data.images.new("Phase12ReviewBuffer", width=4, height=4, alpha=True)
    review.pixels[:] = [0.5, 0.1, 0.1, 1.0] * 16
    request = {"target_object": "CharacterBody", "scene_scale": 1.0,
               "landmarks": {"shoulder_L": 8, "shoulder_R": 9,
                             "neck_L": 12, "neck_R": 13,
                             "head_L": 16, "head_R": 17},
               "reference_target": {"measurement": "shoulder_width_over_head_width",
                                    "min": 1.8, "max": 2.5,
                                    "provenance": "synthetic_fixture"},
               "shoulder_region_vertices": [8, 9, 10, 11],
               "image_name": review.name}
    context = {"scene": scene, "dry_run": False, "job_id": None,
               "production_root": None, "capability_revision": "fixture"}
    original_names = set(bpy.data.objects.keys())
    original_coords = [tuple(vertex.co) for vertex in obj.data.vertices]
    before_settings = (scene.render.resolution_x, scene.render.resolution_y,
                       scene.render.resolution_percentage, scene.render.engine)

    observed = quality.execute("omega.quality.inspect", request, context)
    assert observed["native_execution_verified"] and not observed["visual_quality_verified"]
    assert observed["source_kind"] == "native_bpy_mesh"
    assert observed["metrics"]["shoulder_width_over_head_width"] > 5
    assert observed["metrics"]["face_components"] == 2
    assert any(f["code"] == "DISCONNECTED_MESH_COMPONENTS" for f in observed["findings"])
    assert observed["pixel_evidence"]["state"] == "sampled_native_image_buffer"
    assert observed["pixel_evidence"]["saved_file_sha256"] is None
    assert observed["scene_facts"]["material_slot_count"] == 1
    assert observed["scene_facts"]["camera_framing"]["state"] == "measured"
    assert set(bpy.data.objects.keys()) == original_names
    assert [tuple(vertex.co) for vertex in obj.data.vertices] == original_coords
    assert before_settings == (scene.render.resolution_x, scene.render.resolution_y,
                               scene.render.resolution_percentage, scene.render.engine)

    plan_request = copy.deepcopy(request)
    plan_request["checkpoint_sha256"] = "a" * 64  # supplied token; NOT claimed verified
    planned = quality.execute("omega.quality.revise_plan", plan_request, context)
    assert len(planned["proposals"]) == 1, planned
    proposal = planned["proposals"][0]
    assert proposal["repair"]["operation"] == "omega.artist.execute_tool"
    assert not proposal["approved_for_auto_execution"]
    assert proposal["checkpoint_verification_required"]
    assert [tuple(vertex.co) for vertex in obj.data.vertices] == original_coords
    before_guard = planned["protected_geometry_sha256"]

    # Test-only manual Blender geometry edit, NOT an executed Phase 12 proposal
    # and NOT a claim that Phase 11 currently registers mesh.adjust_region.
    factor = proposal["repair"]["parameters"]["scale_factor"]
    for index in proposal["repair"]["parameters"]["vertex_indices"]:
        obj.data.vertices[index].co.x *= factor
    obj.data.update()
    checked = quality.audit("omega.quality.inspect", request, context)
    assert checked["metrics"]["reference_passed"]
    assert checked["metrics"]["face_components"] == 2
    assert checked["source_revision"] != observed["source_revision"]
    assert checked["protected_geometry_sha256"] == before_guard
    assert all(tuple(obj.data.vertices[i].co) == original_coords[i]
               for i in range(len(original_coords)) if i not in (8, 9, 10, 11))

    followup = dict(plan_request, max_iterations=2, attempts_used=1,
                    previous_source_revision=observed["source_revision"],
                    previous_metric=observed["metrics"]["shoulder_width_over_head_width"],
                    previous_guard_sha256=before_guard)
    follow = quality.execute("omega.quality.revise_plan", followup, context)
    assert follow["stopped_reason"] == "TARGET_MET_MEASURED_ONLY"
    assert follow["proposals"] == []

    # Separate *explicit* native topology repair: bridge four real BMesh faces.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    for i in range(4):
        bm.faces.new((bm.verts[8 + i], bm.verts[8 + (i + 1) % 4],
                      bm.verts[12 + (i + 1) % 4], bm.verts[12 + i]))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    connected = quality.execute("omega.quality.inspect", request, context)
    assert connected["metrics"]["face_components"] == 1
    assert connected["metrics"]["reference_passed"]
    assert connected["metrics"]["mesh_face_count"] == observed["metrics"]["mesh_face_count"] + 4
    assert before_settings == (scene.render.resolution_x, scene.render.resolution_y,
                               scene.render.resolution_percentage, scene.render.engine)

    with tempfile.TemporaryDirectory(prefix="omega-phase12-bpy-") as folder:
        saved = str(Path(folder) / "quality_fixture.blend")
        assert "FINISHED" in bpy.ops.wm.save_as_mainfile(filepath=saved)
        assert Path(saved).is_file() and Path(saved).stat().st_size > 100
        assert "FINISHED" in bpy.ops.wm.open_mainfile(filepath=saved)
        reread = quality.execute("omega.quality.inspect", request,
                                 dict(context, scene=bpy.context.scene))
        assert reread["metrics"]["reference_passed"]
        assert reread["metrics"]["face_components"] == 1
        assert reread["metrics"]["mesh_face_count"] == connected["metrics"]["mesh_face_count"]
        assert reread["source_revision"] == connected["source_revision"]
        assert bpy.context.scene.objects["CharacterBody"].data.materials[0].name == "FixtureMaterial"
    print("PASS REAL BPY: bad ratio + disconnected topology measured; correction read back;")
    print("       protected geometry stable; joined BMesh topology persists after save/reopen")
    print("NOT VERIFIED: Android-native execution, P11 dispatcher, visual likeness, saved PNG")


if __name__ == "__main__":
    main()
