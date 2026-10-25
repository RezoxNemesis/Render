# SPDX-License-Identifier: GPL-2.0-or-later
"""REAL Blender bpy fixture: select -> edit -> 2 surface strokes -> modifier.

Run from repository root:
  blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase11/test_phase11_bpy.py

This file MUST run under Blender, never with mocks. Saves/reopens an editable
.blend inside a temporary owner root, and proves persisted geometry + modifier.
It does not certify an Android viewport or Blender's SCULPT brush operator.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

import bpy  # Deliberately required; fails rather than faking native execution.

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "full-app/scripts/omega/phase11_artist.py"
spec = importlib.util.spec_from_file_location("phase11_artist_native", MODULE_PATH)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def main():
    with tempfile.TemporaryDirectory(prefix="omega-p11-native-") as folder:
        production = Path(folder) / "Production"
        projects = production / "Projects"
        projects.mkdir(parents=True)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0)
        sphere = bpy.context.object
        sphere.name = "OmegaMesh"
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=(3, 0, 0))
        cube = bpy.context.object
        cube.name = "OtherTarget"
        bpy.ops.wm.save_as_mainfile(filepath=str(projects / "phase11_edit_fixture.blend"))

        ctx = {"scene": bpy.context.scene, "production_root": production,
               "dry_run": False, "cancellation_requested": False}
        n = 0

        def inspect():
            return a.execute("omega.artist.inspect_ui", {"target": "OmegaMesh"}, ctx)

        def tool(name, expected_mode, postcondition, params):
            nonlocal n
            n += 1
            pre = inspect()["source_revision"]
            payload = {"tool": name, "target": "OmegaMesh",
                       "expected_mode": expected_mode,
                       "expected_scene_revision": pre,
                       "parameters": params, "postcondition": postcondition}
            ctx["job_id"] = "{:032x}".format(n)
            result = a.execute("omega.artist.execute_tool", payload, ctx)
            assert result["state"] == "succeeded", result
            assert result["native_execution_verified"] is True
            assert result["quality_reduced"] is False
            assert result["new_scene_revision"] != result["source_revision"]
            # Replaying a previously executed job must not repeat a stroke.
            if name == "mesh.edit_surface_stroke":
                repeat = a.execute("omega.artist.execute_tool", payload, ctx)
                assert repeat["replayed"] is True
                assert repeat["new_scene_revision"] == result["new_scene_revision"]
            return result

        baseline = inspect()
        assert baseline["detail"]["active_object"] == "OtherTarget"
        before_hash = baseline["detail"]["mesh_sha256"]
        selected = tool("object.select", "OBJECT", "selection_active", {})
        assert bpy.context.view_layer.objects.active == sphere
        assert selected["detail"]["new_active"] == "OmegaMesh"
        assert selected["detail"]["touch_event_observed"] is False
        changed_mode = tool("object.mode_set", "OBJECT", "mode_changed", {"mode": "EDIT"})
        assert changed_mode["detail"]["old_mode"] == "OBJECT"
        assert sphere.mode == "EDIT"
        assert inspect()["detail"]["active_mode"] == "EDIT"

        # Pure native BMesh edits, object-local mesh coordinates. No SCULPT operator claim.
        edit1 = tool("mesh.edit_surface_stroke", "EDIT", "evaluated_mesh_changed",
                     {"radius": 0.55, "strength": 0.18,
                      "direction": [0, 0, 1], "samples": [[0, 0, 1]]})
        assert edit1["detail"]["changed_vertex_count"] > 0
        edit2 = tool("mesh.edit_surface_stroke", "EDIT", "evaluated_mesh_changed",
                     {"radius": 0.6, "strength": 0.12,
                      "direction": [0.3, 0, 1], "samples": [[0.2, 0.1, 0.85]]})
        assert edit2["detail"]["old_mesh_sha256"] == edit1["detail"]["new_mesh_sha256"]
        assert edit2["detail"]["new_mesh_sha256"] != before_hash

        # If interrupted after first sample, BMesh is rolled back (no receipt committed).
        pre_abort = inspect()["detail"]["mesh_sha256"]
        calls = []
        def cancelled():
            calls.append(1)
            return len(calls) >= 3
        ctx["cancellation_requested"] = cancelled
        ctx["job_id"] = "{:032x}".format(999)
        payload = {"tool": "mesh.edit_surface_stroke", "target": "OmegaMesh",
                   "expected_mode": "EDIT",
                   "expected_scene_revision": inspect()["source_revision"],
                   "postcondition": "evaluated_mesh_changed",
                   "parameters": {"radius": 0.9, "strength": 0.6,
                                  "direction": [0, 0, 1],
                                  "samples": [[0, 0, 1], [0, 0, 1]]}}
        try:
            a.execute("omega.artist.execute_tool", payload, ctx)
            raise AssertionError("Cancelled partial edit incorrectly reported success")
        except RuntimeError as error:
            assert "CANCELLED_AT_SAFE_BOUNDARY" in str(error), error
        assert inspect()["detail"]["mesh_sha256"] == pre_abort
        ctx["cancellation_requested"] = False
        ctx["job_id"] = None

        tool("object.mode_set", "EDIT", "mode_changed", {"mode": "OBJECT"})
        mod = tool("modifier.add", "OBJECT", "modifier_present",
                   {"kind": "BEVEL", "name": "NativeSurfaceBevel",
                    "width": 0.025, "segments": 3})
        assert mod["detail"]["created_modifier"] == "NativeSurfaceBevel"
        assert sphere.modifiers["NativeSurfaceBevel"].segments == 3
        finished = inspect()
        assert finished["detail"]["mesh_sha256"] != before_hash
        assert finished["detail"]["vertices"] == baseline["detail"]["vertices"]
        assert finished["detail"]["faces"] == baseline["detail"]["faces"]
        checksum_before_save = finished["detail"]["mesh_sha256"]

        bpy.ops.wm.save_as_mainfile(filepath=str(projects / "phase11_edit_fixture.blend"))
        saved_bytes = (projects / "phase11_edit_fixture.blend").read_bytes()
        file_sha = hashlib.sha256(saved_bytes).hexdigest()
        assert len(saved_bytes) > 1024
        bpy.ops.wm.open_mainfile(filepath=str(projects / "phase11_edit_fixture.blend"))
        ctx["scene"] = bpy.context.scene
        reopened = inspect()
        assert reopened["detail"]["mesh_sha256"] == checksum_before_save
        assert {"name": "NativeSurfaceBevel", "type": "BEVEL"} in reopened["detail"]["target_modifiers"]
        assert bpy.context.scene.objects["OmegaMesh"].type == "MESH"
        print("PHASE11_NATIVE_BPY_PASS:" + json.dumps({
            "blender": bpy.app.version_string,
            "selected_target": selected["target"],
            "mode_changed": changed_mode["detail"]["new_mode"],
            "before_mesh_sha256": before_hash,
            "after_mesh_sha256": checksum_before_save,
            "stroke_1_vertices": edit1["detail"]["changed_vertex_count"],
            "stroke_2_vertices": edit2["detail"]["changed_vertex_count"],
            "cancel_rollback": True,
            "saved_reopened_blend_sha256": file_sha,
            "modifier": "NativeSurfaceBevel",
            "blender_sculpt_brush_operator_tested": False,
            "android_runtime_tested": False
        }, sort_keys=True))


if __name__ == "__main__":
    main()
