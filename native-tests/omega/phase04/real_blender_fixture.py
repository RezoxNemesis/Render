# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender fixture: arch BMesh bridge, save/reopen, exact rollback.

Run from repository root:
    blender -b --factory-startup --python-exit-code 1 --python \
      native-tests/omega/phase04/real_blender_fixture.py

This is NOT a mock. It must run against bpy and the Blender BMesh implementation.
"""
import importlib.util
import json
import math
from pathlib import Path
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "full-app/scripts/omega/phase04_geometry.py"
spec = importlib.util.spec_from_file_location("phase04_geometry", MODULE)
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)


def expect(code, operation, args, context):
    try:
        geo.execute(operation, args, context)
    except ValueError as err:
        assert str(err) == code, (str(err), code)
    else:
        raise AssertionError("Expected failure: " + code)


def make_real_arch():
    """Disconnected rings describing 2 legs and a smooth semicircular lintel.

    The bridge calls weld the ring surfaces *topologically* (shared edges and
    vertices), not by visual proximity or disconnected overlapping primitives.
    """
    stations = [(-2., 0.2), (-2., 2.)]
    stations += [(-2 * math.cos(math.pi * i / 16),
                  2 + 2 * math.sin(math.pi * i / 16))
                 for i in range(17)]
    stations += [(2., 0.2)]
    verts = []
    rings = []
    for i, (x, z) in enumerate(stations):
        prev = stations[max(0, i-1)]
        next_ = stations[min(len(stations)-1, i+1)]
        dx, dz = next_[0]-prev[0], next_[1]-prev[1]
        norm = math.hypot(dx, dz)
        nx, nz = -dz/norm, dx/norm
        ring = []
        for width, depth in ((-.22, -.28), (.22, -.28),
                             (.22, .28), (-.22, .28)):
            ring.append(len(verts))
            verts.append((x + nx * width, depth, z + nz * width))
        rings.append(ring)
    edges = []
    for ring in rings:
        edges += [(ring[i], ring[(i+1) % 4]) for i in range(4)]
    # Two native end caps; interior ring edges begin as wire geometry.
    faces = [rings[0][:], list(reversed(rings[-1]))]
    mesh = bpy.data.meshes.new("OmegaArchDisconnectedRings")
    mesh.from_pydata(verts, edges, faces)
    mesh.update()
    mesh.uv_layers.new(name="OriginalUV")
    stone = bpy.data.materials.new("OmegaStone")
    mesh.materials.append(stone)
    ob = bpy.data.objects.new("OmegaArch", mesh)
    bpy.context.scene.collection.objects.link(ob)
    return ob, rings


def run():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ob, rings = make_real_arch()
    ctx = {"scene": bpy.context.scene, "available_memory_bytes": 1000000000,
           "job_id": "a" * 32, "cancellation_requested": False}
    original = geo.execute("omega.geometry.inspect", {"object": ob.name}, ctx)
    initial_hash = original["source_revision"]
    initial = original["result"]["topology"]
    assert initial["connected_components"] > 1 and not initial["watertight"], initial
    source_pointer = ob.data.as_pointer()
    payload = {"object": ob.name, "expected_revision": initial_hash,
               "loops": rings, "closed": True, "smooth": True,
               "require_manifold": True}
    malformed = dict(payload, loops=[list(reversed(rings[0])),
                                       [rings[1][0], rings[1][2], rings[1][1], rings[1][3]]])
    expect("INVALID_EDGE_LOOPS", "omega.geometry.bridge_loops", malformed, ctx)
    assert ob.data.as_pointer() == source_pointer
    expect("CANCELLED", "omega.geometry.bridge_loops", payload,
           dict(ctx, cancellation_requested=True))
    assert ob.data.as_pointer() == source_pointer
    expect("OUT_OF_MEMORY_PAUSED", "omega.geometry.bridge_loops", payload,
           dict(ctx, available_memory_bytes=100))
    assert ob.data.as_pointer() == source_pointer
    result = geo.execute("omega.geometry.bridge_loops", payload, ctx)
    assert result["native_execution_verified"] and not result["quality_reduced"]
    stats = result["result"]["after"]
    assert result["result"]["native_operator"] == "bmesh.ops.bridge_loops"
    assert stats["watertight"] and stats["connected_components"] == 1, stats
    assert stats["boundary_edges"] == stats["wire_edges"] == 0, stats
    assert stats["degenerate_faces"] == stats["winding_conflicts"] == 0, stats
    assert stats["euler_characteristic"] == 2, stats
    assert stats["polygons"] == 4*(len(rings)-1)+2, stats
    assert len(ob.data.materials) == 1 and len(ob.data.uv_layers) == 1
    revised = result["source_revision"]
    assert revised != initial_hash
    again = geo.execute("omega.geometry.bridge_loops", payload, ctx)
    assert again["result"]["already_complete"] is True
    assert geo.execute("omega.geometry.inspect", {"object": ob.name}, ctx)["source_revision"] == revised
    expect("MESH_REVISION_CONFLICT", "omega.geometry.bridge_loops", payload,
           dict(ctx, job_id="b"*32))
    with tempfile.TemporaryDirectory(prefix="render-omega-p04-") as tmp:
        file = str(Path(tmp) / "arch.blend")
        assert "FINISHED" in bpy.ops.wm.save_as_mainfile(filepath=file, check_existing=False)
        assert Path(file).stat().st_size > 1024
        assert "FINISHED" in bpy.ops.wm.open_mainfile(filepath=file)
        reopened = bpy.data.objects["OmegaArch"]
        ctx["scene"] = bpy.context.scene
        rescan = geo.execute("omega.geometry.inspect", {"object": "OmegaArch"}, ctx)
        assert rescan["source_revision"] == revised, (rescan, revised)
        assert rescan["result"]["topology"]["watertight"]
        assert rescan["result"]["stored_undo_checkpoints"] == 1
        undo = geo.execute("omega.geometry.bridge_loops", {
            "object": "OmegaArch", "action": "restore", "expected_revision": revised,
        }, dict(ctx, job_id="c"*32))
        assert undo["result"]["restored"] is True
        assert undo["source_revision"] == initial_hash, undo
        assert reopened.data is not None and len(reopened.data.materials) == 1
        assert len(reopened.data.uv_layers) == 1
        assert "FINISHED" in bpy.ops.wm.save_as_mainfile(filepath=file, check_existing=False)
        assert "FINISHED" in bpy.ops.wm.open_mainfile(filepath=file)
        restored = geo.execute("omega.geometry.inspect", {"object": "OmegaArch"},
                               dict(ctx, scene=bpy.context.scene))
        assert restored["source_revision"] == initial_hash
        assert restored["result"]["stored_undo_checkpoints"] == 0
        print("PHASE04_REAL_BPY_OK " + json.dumps({
            "blender": bpy.app.version_string,
            "object": "OmegaArch",
            "native_operator": "bmesh.ops.bridge_loops",
            "ring_count": len(rings),
            "reopened_watertight": rescan["result"]["topology"]["watertight"],
            "closed_mesh": stats,
            "undo_restored_revision": initial_hash,
            "material_and_uv_preserved": True,
        }, sort_keys=True))


if __name__ == "__main__":
    run()
