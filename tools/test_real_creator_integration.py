# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise the public native dispatcher, durable plans and recovery barriers."""
import os
from pathlib import Path
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_production as Production
import render_creator_contract as Creator
import render_command_contract as Commands
import render_unified_workspace as Studio
import render_unified_queue as Queue


def rejected(code, function):
    try:
        function()
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
                                  str(spool), "a" * 32)

    all_new = set(Creator.OPS) | set(Commands.OPS)
    assert all_new <= Production.C.OPERATIONS
    capabilities = call("studio.capabilities")
    assert all_new <= set(capabilities["api_supported_ops"])
    indexed = {row["operation"]: row for row in Studio._tool_index()}
    for operation in all_new:
        assert indexed[operation]["known_in_native_registry"], operation
        assert indexed[operation]["input_schema"]["additionalProperties"] is False
    assert not indexed["studio.command.submit"]["batch_supported"]
    assert indexed["studio.command.preview"]["read_only"]
    assert call("studio.tool.search", {"query": "terrain", "limit": 30})["matches"]

    made = call("studio.create.model", {"name": "PublicAsset", "kind": "barrel"})
    checkpoint = made["checkpoint_before_change"]
    saved = root / "Projects" / checkpoint["filename"]
    assert saved.is_file() and saved.stat().st_size > 1000
    assert scene.objects["PublicAsset"].type == "MESH"
    checkpoint_count = len(list((root / "Projects").glob("*.blend")))
    rejected("CREATOR_", lambda: call("studio.create.model", {
        "name": "Malformed", "kind": "crate", "python": "print('unsafe')"}))
    assert not bpy.data.objects.get("Malformed")
    assert len(list((root / "Projects").glob("*.blend"))) == checkpoint_count
    scene["production_frozen_job"] = "f" * 32
    rejected("RENDER_SNAPSHOT_IMMUTABLE", lambda: call("studio.create.model", {
        "name": "FrozenWrite", "kind": "crate"}))
    assert not bpy.data.objects.get("FrozenWrite")
    del scene["production_frozen_job"]

    # Preview and submit are not completion. Only actual timer-step receipts
    # establish that new native objects and materials now exist.
    request = {"brief": "forest environment", "name": "IntegrationForest",
               "seed": 9, "quality": "draft"}
    before_objects = set(bpy.data.objects.keys())
    reviewed = call("studio.command.preview", request)
    assert reviewed["ready_to_submit"], reviewed
    assert set(bpy.data.objects.keys()) == before_objects
    submitted = call("studio.command.submit", dict(request,
                     preview_sha256=reviewed["preview_sha256"]))
    assert submitted["state"] == "queued" and submitted["completed_steps"] == 0
    assert submitted["bound_scene"] == scene.name
    assert set(bpy.data.objects.keys()) == before_objects
    for _ in reviewed["steps"]:
        tick = Queue.tick(root, Studio._execute_step,
                          on_finish=Studio._step_end)
        assert tick["result"] == "succeeded", tick
    status = call("studio.plan.status", {"plan_id": submitted["plan_id"]})
    assert status["state"] == "completed"
    assert status["completed_steps"] == len(reviewed["steps"])
    assert len(set(bpy.data.objects.keys()) - before_objects) >= 3
    after = set(bpy.data.objects.keys())
    retry = call("studio.command.submit", dict(request,
                 preview_sha256=reviewed["preview_sha256"]))
    assert retry["idempotent"] and retry["state"] == "completed"
    assert set(bpy.data.objects.keys()) == after
    assert Queue.tick(root, Studio._execute_step)["executed_steps"] == 0

    # A scene switch can never redirect an accepted command into another project.
    plan = call("studio.plan.submit", {"name": "Bound scene", "steps": [
        {"operation": "studio.create.model", "payload": {
            "name": "WrongSceneAsset", "kind": "crate"}}]})
    other = bpy.data.scenes.new("DifferentProject")
    bpy.context.window.scene = other
    blocked = Queue.tick(root, Studio._execute_step)
    assert blocked["result"] == "needs_review", blocked
    assert blocked["error_code"] == "STUDIO_PLAN_SCENE_CHANGED", blocked
    assert not bpy.data.objects.get("WrongSceneAsset")
    bpy.context.window.scene = scene
    assert Queue.tick(root, Studio._execute_step)["executed_steps"] == 0
    call("studio.plan.cancel", {"plan_id": plan["plan_id"]})
    bpy.data.scenes.remove(other)

    restart = call("studio.plan.submit", {"name": "Native restart", "steps": [
        {"operation": "studio.create.model", "payload": {
            "name": "ReplayedAsset", "kind": "rock"}}]})
    old_session = Studio._PLAN_SESSION
    Studio._PLAN_SESSION = "f" * 32
    try:
        blocked = Queue.tick(root, Studio._execute_step)
        assert blocked["error_code"] == "STUDIO_PLAN_SESSION_CHANGED", blocked
        assert not bpy.data.objects.get("ReplayedAsset")
        assert Queue.tick(root, Studio._execute_step)["executed_steps"] == 0
    finally:
        Studio._PLAN_SESSION = old_session
    call("studio.plan.cancel", {"plan_id": restart["plan_id"]})
    print("PASS: 11 public operations discoverable; native checkpoint and frozen-write rejection")
    print("PASS: real forest recipe, durable completion and no-replay idempotent retry")
    print("PASS: scene switch and native-session restart stop before any scene mutation")
    print("Desktop Blender:", bpy.app.version_string, "— Android device behavior unverified")
