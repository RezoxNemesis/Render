# SPDX-License-Identifier: GPL-2.0-or-later
"""Visible native Blender Creator acceptance; requires a real VIEW_3D window.

Runs the production dispatcher and real durable queue, and inspects editable
Blender results. It does not claim Android touch or GPU-driver acceptance.
"""
import os
from pathlib import Path
import sys
import tempfile

import bpy

assert not bpy.app.background, "CREATOR_UI_TEST_REQUIRES_NATIVE_WINDOW"
assert bpy.context.window is not None
bpy.context.preferences.view.show_splash = False
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
folder = Path(tempfile.mkdtemp(prefix="render-creator-ui-"))
spool = folder / "render_bpy_jobs"
spool.mkdir()
os.environ["RENDER_AGENT_SPOOL"] = str(spool)
os.environ.pop("RENDER_CREATOR_FOCUS", None)

import render_creator_ui as UI
import render_unified_queue as Queue
import render_unified_workspace as Studio

scene = bpy.context.scene
original = {obj.name: obj.as_pointer() for obj in scene.objects}
settings = (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
            scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end,
            scene.frame_current)
UI.install()
UI.install()  # Idempotent registration is needed after native launch retries.
assert UI.installed()
assert hasattr(bpy.types, "RENDERSTUDIO_PT_creator")
assert hasattr(bpy.types, "RENDERSTUDIO_MT_creator")
assert len([handler for handler in bpy.app.handlers.load_post if handler is UI._loaded]) == 1
assert "FINISHED" in bpy.ops.renderstudio.creator_open()
assert any(area.type == "VIEW_3D" and area.spaces.active.show_region_ui
           for area in bpy.context.window.screen.areas)
assert original == {obj.name: obj.as_pointer() for obj in scene.objects}, "Opening Creator changed scene data"


def select(obj):
    for item in tuple(bpy.context.selected_objects):
        item.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def expect_rejected(callback, text):
    try:
        result = callback()
        assert "CANCELLED" in result, result
    except RuntimeError as error:
        assert text in str(error), error
    assert UI._NOTICES[UI._key(scene)][1], "Rejected action must explain the problem in the native panel"


# A click produces nontrivial actual mesh data, then selects it for the next tool.
scene.render_creator_model_name = "UiCreatorCrate"
scene.render_creator_model_kind = "crate"
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="MODEL")
crate = scene.objects["UiCreatorCrate"]
assert crate.type == "MESH" and len(crate.data.vertices) > 8
assert bpy.context.active_object == crate
assert UI._NOTICES[UI._key(scene)][1] is False

# Selection errors stop before checkpointing or editing an unrelated object.
for obj in tuple(bpy.context.selected_objects):
    obj.select_set(False)
bpy.context.view_layer.objects.active = None
checkpoint_count = len(list((folder / "Production" / "Projects").glob("*.blend")))
expect_rejected(lambda: bpy.ops.renderstudio.creator_tool(tool="MATERIAL"), "Select an editable mesh")
assert len(list((folder / "Production" / "Projects").glob("*.blend"))) == checkpoint_count
select(crate)
scene.render_creator_material = "metal"
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="MATERIAL")
material = crate.data.materials[crate.data.polygons[0].material_index]
assert material.use_nodes
assert any(node.type == "BSDF_PRINCIPLED" for node in material.node_tree.nodes)
assert len(material.node_tree.links) > 1

scene.render_creator_motion = "bounce"
scene.render_creator_start = 1
scene.render_creator_end = 48
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="MOTION")
assert crate.animation_data and crate.animation_data.action
assert len(crate.animation_data.action.fcurves) >= 3
assert any(len(curve.keyframe_points) > 2 for curve in crate.animation_data.action.fcurves)

scene.render_creator_terrain_name = "UiCreatorIsland"
scene.render_creator_terrain_size = 16
scene.render_creator_resolution = 8
scene.render_creator_height = 3
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="TERRAIN")
terrain = scene.objects["UiCreatorIsland"]
assert len(terrain.data.vertices) == 81 and len(terrain.data.polygons) == 64
assert max(vertex.co.z for vertex in terrain.data.vertices) > min(vertex.co.z for vertex in terrain.data.vertices)
assert len(terrain.data.uv_layers) >= 1

select(crate)
scene.render_creator_scatter_name = "UiCreatorScatter"
scene.render_creator_count = 5
scene.render_creator_extent = 8
scene.render_creator_scatter_terrain = terrain
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="SCATTER")
scatter = scene.objects["UiCreatorScatter"]
assert len(scatter.data.vertices) == 5
modifier = next(mod for mod in scatter.modifiers if mod.type == "NODES")
assert any(node.bl_idname == "GeometryNodeInstanceOnPoints" for node in modifier.node_group.nodes)
assert any(node.bl_idname == "GeometryNodeObjectInfo" and node.inputs["Object"].default_value == crate
           for node in modifier.node_group.nodes)

# Rig starter binds real vertices; it is not represented as a humanoid auto-rig.
scene.render_creator_model_name = "UiCreatorColumn"
scene.render_creator_model_kind = "column"
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="MODEL")
column = scene.objects["UiCreatorColumn"]
scene.render_creator_rig_name = "UiCreatorRig"
scene.render_creator_segments = 4
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="RIG")
rig = scene.objects["UiCreatorRig"]
assert rig.type == "ARMATURE" and len(rig.data.bones) == 4
assert any(mod.type == "ARMATURE" and mod.object == rig for mod in column.modifiers)
assert len(column.vertex_groups) >= 4
assert all(len(vertex.groups) > 0 for vertex in column.data.vertices)

select(crate)
scene.render_creator_camera_name = "UiCreatorCamera"
scene.render_creator_camera = "orbit"
assert "FINISHED" in bpy.ops.renderstudio.creator_tool(tool="CAMERA")
camera = scene.objects["UiCreatorCamera"]
assert camera.type == "CAMERA" and scene.camera == camera
assert camera.animation_data and camera.animation_data.action
assert len(camera.animation_data.action.fcurves) >= 7

# Preview is read-only. Editing form fields invalidates the reviewed digest.
scene.render_creator_recipe_name = "UiRecipe"
scene.render_creator_recipe = "asset"
scene.render_creator_quality = "draft"
objects_before = set(scene.objects.keys())
plans_path = folder / "Production" / "StudioPlans"
plans_before = list(plans_path.glob("*.json"))
scene.render_creator_brief = "create a PrivateCastleNeverEcho"
expect_rejected(lambda: bpy.ops.renderstudio.creator_preview(), "not a built-in recipe")
assert "PrivateCastleNeverEcho" not in UI._NOTICES[UI._key(scene)][0]
assert UI._key(scene) not in UI._PREVIEWS
scene.render_creator_brief = "wooden crate and metal barrel"
expect_rejected(lambda: bpy.ops.renderstudio.creator_preview(), "Choose one recipe at a time")
assert "wooden crate and metal barrel" not in UI._NOTICES[UI._key(scene)][0]
assert set(scene.objects.keys()) == objects_before
assert list(plans_path.glob("*.json")) == plans_before
scene.render_creator_brief = "wooden crate asset"
assert "FINISHED" in bpy.ops.renderstudio.creator_preview()
preview = UI._PREVIEWS[UI._key(scene)]["result"]
assert preview["ready_to_submit"] and preview["planner_type"] == "deterministic_local_recipes"
assert preview["language_model"] is False
assert set(scene.objects.keys()) == objects_before
assert list(plans_path.glob("*.json")) == plans_before
scene.render_creator_seed += 1
expect_rejected(lambda: bpy.ops.renderstudio.creator_apply(), "Preview this recipe again")
assert set(scene.objects.keys()) == objects_before

# A scene edit made after preview is caught by the actual planner, not a UI mock.
assert "FINISHED" in bpy.ops.renderstudio.creator_preview()
stale = bpy.data.objects.new("UiOutsideEdit", None)
scene.collection.objects.link(stale)
expect_rejected(lambda: bpy.ops.renderstudio.creator_apply(), "The scene or plan changed")
assert list(plans_path.glob("*.json")) == plans_before

assert "FINISHED" in bpy.ops.renderstudio.creator_preview()
preview = UI._PREVIEWS[UI._key(scene)]["result"]
objects_before_submit = set(scene.objects.keys())
assert "FINISHED" in bpy.ops.renderstudio.creator_apply()
job = UI._JOBS[UI._key(scene)]
assert job["state"] == "queued" and job["completed_steps"] == 0
assert set(scene.objects.keys()) == objects_before_submit, "Submit must queue rather than claim completed geometry"
assert "FINISHED" in bpy.ops.renderstudio.creator_plan_control(action="pause")
assert UI._JOBS[UI._key(scene)]["state"] == "paused"
assert Queue.tick(folder / "Production", Studio._execute_step)["executed_steps"] == 0
assert "FINISHED" in bpy.ops.renderstudio.creator_plan_control(action="resume")
for _ in preview["steps"]:
    result = Queue.tick(folder / "Production", Studio._execute_step)
    assert result["executed_steps"] == 1, result
assert "FINISHED" in bpy.ops.renderstudio.creator_plan_control(action="refresh")
completed = UI._JOBS[UI._key(scene)]
assert completed["state"] == "completed", completed
assert completed["completed_steps"] == len(preview["steps"])
created = [step["payload"]["name"] for step in preview["steps"]
           if step["operation"] in {"studio.create.model", "studio.create.terrain",
                                    "studio.create.scatter", "studio.create.camera", "studio.create.rig"}]
assert created and all(name in scene.objects for name in created)

# A changed prefix can be previewed; colliding names block creation visibly.
assert "FINISHED" in bpy.ops.renderstudio.creator_preview()
blocked = UI._PREVIEWS[UI._key(scene)]["result"]
assert not blocked["ready_to_submit"] and blocked["preflight"]["collisions"]
expect_rejected(lambda: bpy.ops.renderstudio.creator_apply(), "Resolve the preview issues")
assert all(scene.objects[name].as_pointer() == pointer for name, pointer in original.items())
assert settings == (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
                    scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end,
                    scene.frame_current), "Creator tools changed unrelated render or timeline settings"
assert len(list((folder / "Production" / "Projects").glob("*.blend"))) >= 9

# All advertised recipe choices reach a concrete valid local preview.
for index, row in enumerate(UI._RECIPE_ROWS):
    scene.render_creator_recipe = row[0]
    scene.render_creator_recipe_name = "UiTemplate" + str(index)
    assert "FINISHED" in bpy.ops.renderstudio.creator_preview(), row
    reviewed = UI._PREVIEWS[UI._key(scene)]["result"]
    assert reviewed["ready_to_submit"] and reviewed["steps"], reviewed

# Registration cleanup removes callbacks and fields as well as class names.
UI.uninstall()
assert not UI.installed()
assert not hasattr(bpy.types.Scene, "render_creator_recipe")
UI.install()
assert UI.installed()
assert "FINISHED" in bpy.ops.renderstudio.creator_open()
scene.render_creator_recipe_name = "VisibleRecipe"
assert "FINISHED" in bpy.ops.renderstudio.creator_preview()
print("PASS: genuine Blender Creator sidebar/menu and seven checkpointed native tools", flush=True)
print("PASS: editable mesh, node material, terrain UVs, linked scatter, action, camera and weighted rig", flush=True)
print("PASS: read-only preview, stale-plan rejection, real queue pause/resume and receipt-backed completion", flush=True)
print("PASS: ten visible recipes preview successfully; original objects and render settings retained", flush=True)
print("NOT VERIFIED: Android touch responsiveness or device Vulkan compatibility", flush=True)


capture_drawn = False


def close():
    global capture_drawn
    assert any(region.type == "UI" and getattr(region, "active_panel_category", "") == "Create"
               for area in bpy.context.window.screen.areas if area.type == "VIEW_3D"
               for region in area.regions), "CREATOR_CATEGORY_NOT_ACTIVATED_AFTER_REDRAW"
    screenshot = os.environ.get("RENDER_CREATOR_UI_SCREENSHOT", os.environ.get("RENDER_CREATOR_TEST_SCREENSHOT"))
    if screenshot:
        if not capture_drawn:
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
            capture_drawn = True
            return 2.0
        bpy.ops.screen.screenshot(filepath=screenshot)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(close, first_interval=1.5)
