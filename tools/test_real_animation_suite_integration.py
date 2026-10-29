# SPDX-License-Identifier: GPL-2.0-or-later
"""Public dispatcher, actual checkpoint and queued Animation Studio semantics."""
import os
from pathlib import Path
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_animation_suite as Suite
import render_production as Production
import render_unified_workspace as Studio
import render_unified_queue as Queue


def rejected(code, callback):
    try:
        callback()
    except (ValueError, RuntimeError) as error:
        assert code in str(error), (code, str(error))
    else:
        raise AssertionError("Expected rejection: " + code)


with tempfile.TemporaryDirectory() as temporary:
    spool = Path(temporary) / "render_bpy_jobs"
    spool.mkdir()
    os.environ["RENDER_AGENT_SPOOL"] = str(spool)
    root = Path(temporary) / "Production"
    scene = bpy.context.scene

    def call(operation, payload=None):
        return Production.execute({"operation": operation, "payload": payload or {}},
                                  str(spool), "b" * 32)

    supported = call("studio.capabilities")["api_supported_ops"]
    assert set(Suite.OPS) <= set(supported)
    index = {row["operation"]: row for row in Studio._tool_index()}
    for operation in Suite.OPS:
        assert index[operation]["known_in_native_registry"]
        assert index[operation]["batch_supported"]
        assert index[operation]["input_schema"]["additionalProperties"] is False

    original = {obj.name: obj.as_pointer() for obj in scene.objects}
    catalog = call("studio.animation.catalog")
    assert original == {obj.name: obj.as_pointer() for obj in scene.objects}
    result = call("studio.animation.layer.create", {"name": "PublicForeground", "depth": 1})
    checkpoint = result["checkpoint_before_change"]["filename"]
    assert (root / "Projects" / checkpoint).stat().st_size > 1000
    assert scene.objects["PublicForeground"].type == "MESH"
    count = len(list((root / "Projects").glob("*.blend")))
    rejected("FIELDS_INVALID", lambda: call("studio.animation.layer.create", {
        "name": "Rejected", "python": "unsafe"}))
    assert len(list((root / "Projects").glob("*.blend"))) == count
    scene["production_frozen_job"] = "f" * 32
    rejected("RENDER_SNAPSHOT_IMMUTABLE", lambda: call("studio.animation.layer.create", {"name": "Frozen"}))
    assert not bpy.data.objects.get("Frozen")
    assert call("studio.finish.inspect")["render_started"] is False
    del scene["production_frozen_job"]

    plan = call("studio.plan.submit", {"name": "Animation integration", "steps": [
        {"operation": "studio.animation.layer.create", "payload": {"name": "PublicBackground", "depth": -2}},
        {"operation": "studio.animation.parallax.create", "payload": {
            "name": "PublicParallax", "layers": ["PublicForeground", "PublicBackground"], "end": 49}},
        {"operation": "studio.finish.preset", "payload": {"preset": "draft", "fps": 24, "start": 1, "end": 49}},
    ]})
    for _ in range(3):
        result = Queue.tick(root, Studio._execute_step, on_finish=Studio._step_end)
        assert result["result"] == "succeeded", result
    status = call("studio.plan.status", {"plan_id": plan["plan_id"]})
    assert status["state"] == "completed" and status["completed_steps"] == 3
    assert scene.camera.name == "PublicParallax"
    assert scene.render.resolution_x == 854 and scene.frame_end == 49
    assert len(list((root / "Projects").glob("*.blend"))) == count + 3
    assert Queue.tick(root, Studio._execute_step)["executed_steps"] == 0
    print("PASS: Animation Studio public schemas, native checkpoints, frozen writes and durable plan")
    print("Desktop Blender:", bpy.app.version_string, "— Android hardware not verified here")
