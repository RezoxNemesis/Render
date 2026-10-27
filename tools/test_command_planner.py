# SPDX-License-Identifier: GPL-2.0-or-later
"""Host contract/queue tests; these do not claim native Blender execution."""
import copy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "full-app/scripts"))
import render_command_contract as C
import render_command_planner as Planner
import render_creator_contract as Creator
import render_production_contract as Production
import render_unified_contract as Unified
import render_unified_queue as Queue


class CommandContractTests(unittest.TestCase):
    def test_every_catalog_recipe_compiles_at_every_quality_and_seed_boundary(self):
        catalog = C.catalog()
        self.assertFalse(catalog["language_model"])
        self.assertFalse(catalog["general_free_text_supported"])
        self.assertFalse(catalog["network_requests"])
        self.assertEqual(len(catalog["recipes"]), 10)
        for recipe in catalog["recipes"]:
            for quality in C.QUALITY:
                for seed in (0, C.MAX_SEED):
                    with self.subTest(recipe=recipe["id"], quality=quality, seed=seed):
                        request = {"brief": recipe["brief"], "quality": quality, "seed": seed}
                        before = copy.deepcopy(request)
                        plan = C.compile_request(request)
                        self.assertEqual(request, before)
                        self.assertEqual(plan["recipe"]["id"], recipe["id"])
                        self.assertLessEqual(len(plan["steps"]), 16)
                        self.assertGreater(len(plan["steps"]), 1)
                        self.assertFalse(plan["scene_modified_by_command"])
                        self.assertLessEqual(plan["estimated_complexity"]["scatter_instances"], 180)
                        self.assertFalse(plan["estimated_complexity"]["render_time_estimated"])
                        Unified.plan({"name": plan["name"], "steps": plan["steps"]})
                        for step in plan["steps"]:
                            self.assertEqual(Creator.validate(step["operation"], step["payload"]),
                                             step["payload"])

    def test_material_model_motion_combinations_remain_typed_and_bounded(self):
        for material in Creator.MATERIAL_PRESETS:
            for kind in Creator.MODEL_KINDS:
                for motion in Creator.MOTION_PRESETS:
                    plan = C.compile_request({"brief": f"animated {material} {kind} {motion}"})
                    self.assertEqual(plan["recipe"]["kind"], kind)
                    self.assertEqual(plan["recipe"]["material"], material)
                    self.assertEqual(plan["recipe"]["motion"], motion)
                    self.assertEqual(len(plan["steps"]), 4)
                    self.assertEqual(plan["steps"][2]["operation"], "studio.create.motion")

    def test_all_plan_references_belong_to_earlier_new_objects(self):
        for row in C.catalog()["recipes"]:
            plan = C.compile_request({"brief": row["brief"]})
            created = set()
            for step in plan["steps"]:
                p = step["payload"]
                for reference in ("object", "target", "source", "terrain"):
                    if reference in p:
                        self.assertIn(p[reference], created)
                if "name" in p:
                    self.assertNotIn(p["name"], created)
                    created.add(p["name"])

    def test_friendly_prefixes_and_documented_defaults(self):
        for brief in ("please create a wooden crate asset!", "Make an island scene.",
                      "build a studio turntable", "add a flexible rig starter",
                      "asset", "product scene", "animated prop", "mountains landscape"):
            with self.subTest(brief=brief):
                self.assertGreater(C.compile_request({"brief": brief})["total_steps"], 1)
        plan = C.compile_request({"brief": "wooden crate"})
        explicit = C.compile_request({"brief": "wooden crate", "seed": 0, "quality": "standard",
                                      "name": plan["request"]["name"]})
        self.assertEqual(plan, explicit)

    def test_unknown_words_negation_injection_and_combined_intents_are_rejected(self):
        attacks = ["dragon", "crate but remove everything first", "do not create a crate",
                   "create a crate; import os", "__import__('os').system('id')", "$(id)",
                   "create a crate && rm -rf /", "create a photo realistic human",
                   "forest environment with 999999 trees", "crate exec python",
                   "forest or island", "wooden metal crate", "crate and barrel",
                   "forest island environment", "create a crate\nimport os",
                   "create a crate\x00", "cráte", "https://example.com/model.blend"]
        for brief in attacks:
            with self.subTest(brief=brief):
                with self.assertRaises(ValueError):
                    C.compile_request({"brief": brief})
        with self.assertRaises(C.BriefError) as caught:
            C.compile_request({"brief": "flying dragon"})
        self.assertEqual(caught.exception.code, "STUDIO_COMMAND_UNSUPPORTED_BRIEF")
        self.assertIn("studio.command.catalog", str(caught.exception))
        self.assertNotIn("dragon", str(caught.exception))
        with self.assertRaises(C.BriefError) as caught:
            C.compile_request({"brief": "crate or barrel"})
        self.assertEqual(caught.exception.code, "STUDIO_COMMAND_AMBIGUOUS_BRIEF")

    def test_strict_fields_nonfinite_and_name_limits(self):
        attacks = [None, [], {"brief": None}, {"brief": ""}, {"brief": "  "},
                   {"brief": "x" * 241}, {"brief": "crate", "steps": []},
                   {"brief": "crate", "python": "print(1)"},
                   {"brief": "crate", "name": "../path"},
                   {"brief": "crate", "name": "A "},
                   {"brief": "crate", "name": "A" * 41},
                   {"brief": "crate", "name": None},
                   {"brief": "crate", "quality": "ultra"},
                   {"brief": "crate", "quality": ["detail"]},
                   {"brief": "crate", "seed": True},
                   {"brief": "crate", "seed": -1},
                   {"brief": "crate", "seed": 2**31},
                   {"brief": "crate", "seed": 10**10000},
                   {"brief": "crate", "seed": float("nan")},
                   {"brief": "crate", "seed": float("inf")},
                   {"brief": "crate", "seed": float("-inf")},
                   {"brief": "crate", "seed": 1.0}]
        for index, payload in enumerate(attacks):
            with self.subTest(index=index):
                with self.assertRaises(ValueError):
                    C.compile_request(payload)
        self.assertEqual(C.compile_request({"brief": "crate", "name": "A" * 40})["name"],
                         "A" * 40)
        for value in ({"a": float("nan")}, {"a": float("inf")}, {"a": object()}):
            with self.assertRaises(ValueError):
                C.digest(value)
        recursive = []
        recursive.append(recursive)
        with self.assertRaises(ValueError):
            C.digest(recursive)

    def test_digest_binds_every_preview_field_without_mutating_input(self):
        value = C.compile_request({"brief": "forest environment", "seed": 7})
        before = copy.deepcopy(value)
        preview = C.seal_preview(value)
        self.assertEqual(value, before)
        self.assertEqual(preview, C.seal_preview(value))
        self.assertEqual(preview, C.seal_preview(preview))
        for field, change in (("name", "Changed"), ("warnings", []), ("steps", []),
                              ("estimated_complexity", {}), ("request", {})):
            altered = dict(value, **{field: change})
            self.assertNotEqual(C.seal_preview(altered)["preview_sha256"], preview["preview_sha256"])

    def test_catalog_and_schemas_are_fresh_read_only_values(self):
        caps = Planner.capabilities()
        self.assertEqual(set(row["operation"] for row in caps), set(Planner.OPS))
        for row in caps:
            self.assertEqual(row["read_only"], row["operation"] in Planner.READ_ONLY)
            self.assertFalse(row["input_schema"]["additionalProperties"])
        self.assertNotIn("studio.command.submit", Planner.READ_ONLY)
        self.assertIn("studio.command.preview", Planner.READ_ONLY)
        caps[1]["input_schema"]["properties"]["quality"]["enum"].clear()
        self.assertEqual(len(Planner.capabilities()[1]["input_schema"]["properties"]["quality"]["enum"]), 3)
        catalog = Planner.execute("studio.command.catalog", {}, None, None)
        catalog["recipes"].clear()
        self.assertEqual(len(C.catalog()["recipes"]), 10)
        with self.assertRaises(ValueError):
            Planner.execute("studio.command.catalog", {"brief": "crate"}, None, None)
        with self.assertRaises(ValueError):
            Planner.execute("studio.command.python", {}, None, None)


class Inventory(dict):
    def __iter__(self):
        return iter(self.values())


class Scene(dict):
    def __init__(self):
        super().__init__()
        self.name = "Host Test Scene"
        self.objects = Inventory()
        self.camera = None
        self.frame_start, self.frame_end, self.frame_current = 1, 250, 1
        self.library = None
        self.is_editable = True


class CommandQueueTests(unittest.TestCase):
    """Uses real durable queue storage with an explicitly stubbed native surface."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Production"
        self.scene = Scene()
        self.bpy = types.SimpleNamespace(data=types.SimpleNamespace(objects=Inventory(), collections=Inventory()),
                                        context=types.SimpleNamespace(scene=self.scene, mode="OBJECT"),
                                        app=types.SimpleNamespace(version_string="Host test stub"))
        self.routes = []

        def execute(operation, payload, root, scene):
            self.assertEqual(operation, "studio.plan.submit")
            self.assertIs(scene, self.scene)
            self.routes.append((operation, copy.deepcopy(payload)))
            return Queue.submit(root, payload)

        patch = mock.patch.dict(sys.modules, {"bpy": self.bpy,
                    "render_unified_workspace": types.SimpleNamespace(execute=execute)})
        patch.start()
        self.addCleanup(patch.stop)

    def preview(self, **fields):
        return Planner.execute("studio.command.preview", dict({"brief": "wooden crate asset"}, **fields),
                               self.root, self.scene)

    def submit(self, preview, **changes):
        return Planner.execute("studio.command.submit",
                               dict(preview["request"], preview_sha256=preview["preview_sha256"], **changes),
                               self.root, self.scene)

    def add_object(self, name, kind="MESH", local=True):
        item = types.SimpleNamespace(name=name, type=kind)
        self.bpy.data.objects[name] = item
        if local:
            self.scene.objects[name] = item
        return item

    def test_preview_is_deterministic_without_scene_disk_or_timer_mutations(self):
        first = self.preview(brief="forest environment", seed=42)
        second = self.preview(brief="forest environment", seed=42)
        self.assertEqual(first, second)
        self.assertTrue(first["ready_to_submit"])
        self.assertTrue(first["preflight"]["creator_payloads_validated"])
        self.assertTrue(first["preview_only_no_job_created"])
        self.assertFalse(self.root.exists())
        self.assertEqual(self.routes, [])
        self.assertEqual(len(self.scene.objects), 0)
        self.assertEqual(len(self.bpy.data.objects), 0)

    def test_submit_uses_existing_queue_and_never_fabricates_completion(self):
        preview = self.preview()
        result = self.submit(preview)
        self.assertEqual(result["state"], "queued")
        self.assertEqual(result["completed_steps"], 0)
        self.assertTrue(result["submitted_to_queue"])
        self.assertFalse(result["scene_modified_by_command"])
        self.assertEqual(len(self.routes), 1)
        self.assertEqual(self.routes[0][1]["steps"], preview["steps"])
        self.assertEqual(result["preview_sha256"], preview["preview_sha256"])
        record = json.loads((self.root / "StudioPlans" / (result["plan_id"] + ".json")).read_text())
        self.assertEqual(record["receipts"], [])
        self.assertEqual(record["next"], 0)
        self.assertEqual(len(self.scene.objects), 0)
        self.assertEqual(len(self.bpy.data.objects), 0)
        retry = self.submit(preview)
        self.assertTrue(retry["idempotent"])
        self.assertEqual(retry["plan_id"], result["plan_id"])
        self.assertEqual(len(self.routes), 1)
        Queue.cancel(self.root, result["plan_id"])
        self.assertEqual(self.submit(preview)["state"], "cancelled")
        self.assertEqual(len(self.routes), 1)
        # A newly reviewed attempt after cancellation is a new job; retrying
        # the old hash still reports the old cancelled job without replay.
        fresh = self.preview()
        self.assertNotEqual(fresh["preview_sha256"], preview["preview_sha256"])
        replacement = self.submit(fresh)
        self.assertEqual(replacement["state"], "queued")
        self.assertNotEqual(replacement["plan_id"], result["plan_id"])
        self.assertEqual(self.submit(preview)["state"], "cancelled")

    def test_no_preview_hash_altered_request_and_raw_steps_are_rejected(self):
        preview = self.preview()
        base = dict(preview["request"], preview_sha256=preview["preview_sha256"])
        for field, value in (("preview_sha256", "0" * 64), ("seed", 9), ("quality", "detail"),
                             ("name", "Different"), ("brief", "metal barrel asset"),
                             ("brief", "wooden  crate asset")):
            changed = dict(base, **{field: value})
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "STUDIO_COMMAND_PREVIEW_STALE"):
                    Planner.submit(changed, self.root, self.scene)
        for value in (None, "", "A" * 64, "a" * 63, True, float("nan")):
            with self.assertRaises(ValueError):
                Planner.submit(dict(base, preview_sha256=value), self.root, self.scene)
        with self.assertRaises(ValueError):
            Planner.submit(preview["request"], self.root, self.scene)
        with self.assertRaises(ValueError):
            Planner.submit(dict(base, steps=preview["steps"]), self.root, self.scene)
        self.assertFalse(self.root.exists())
        self.assertEqual(self.routes, [])

    def test_changed_scene_inventory_camera_or_frame_invalidates_preview(self):
        preview = self.preview()
        self.add_object("Unrelated")
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(preview)
        preview = self.preview()
        self.scene.frame_current = 9
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(preview)
        preview = self.preview()
        self.scene.camera = self.add_object("Camera", "CAMERA")
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(preview)
        self.assertEqual(self.routes, [])

    def test_identical_named_replacement_scene_requires_a_new_preview(self):
        reviewed = self.preview()
        self.scene = Scene()
        self.bpy.context.scene = self.scene
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(reviewed)
        self.assertEqual(self.routes, [])

    def test_native_runtime_reload_invalidates_unsubmitted_preview(self):
        reviewed = self.preview()
        importlib.reload(Planner)
        fresh = self.preview()
        self.assertNotEqual(fresh["preview_sha256"], reviewed["preview_sha256"])
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(reviewed)
        self.assertEqual(fresh, self.preview())
        self.assertEqual(self.routes, [])

    def test_scene_identity_cache_is_bounded_and_invalid_rna_address_is_not_reused(self):
        class NativeScene:
            session_uid = None
            def __init__(self, pointer):
                self.pointer = pointer
                self.valid = True
            def as_pointer(self):
                if not self.valid:
                    raise ReferenceError("removed RNA")
                return self.pointer
        first = NativeScene(12345)
        old = Planner._scene_identity(first)
        self.assertEqual(old, Planner._scene_identity(first))
        first.valid = False
        replacement = NativeScene(12345)
        self.assertNotEqual(old, Planner._scene_identity(replacement))
        for pointer in range(20000, 20000 + Planner._MAX_SCENE_IDENTITIES + 4):
            Planner._scene_identity(NativeScene(pointer))
        self.assertLessEqual(len(Planner._SCENE_IDENTITIES), Planner._MAX_SCENE_IDENTITIES)

    def test_name_collision_in_other_scene_blocks_matching_preview(self):
        preview = self.preview()
        name = preview["preflight"]["objects_to_create"][0]
        self.add_object(name, local=False)
        reviewed = self.preview()
        self.assertFalse(reviewed["ready_to_submit"])
        self.assertEqual(reviewed["preflight"]["collisions"], [name])
        with self.assertRaisesRegex(ValueError, "PREFLIGHT_BLOCKED.*NAME_COLLISION"):
            self.submit(reviewed)
        self.assertFalse(self.root.exists())

    def test_collection_name_collision_blocks_preview_and_changes_its_digest(self):
        preview = self.preview()
        name = preview["preflight"]["objects_to_create"][0]
        self.bpy.data.collections[name] = types.SimpleNamespace(name=name)
        reviewed = self.preview()
        self.assertFalse(reviewed["ready_to_submit"])
        self.assertEqual(reviewed["preflight"]["collisions"], [name])
        self.assertEqual(reviewed["preflight"]["collection_collisions"], [name])
        self.assertEqual(reviewed["preflight"]["object_collisions"], [])
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(preview)
        with self.assertRaisesRegex(ValueError, "PREFLIGHT_BLOCKED.*COLLECTION_NAME_COLLISION"):
            self.submit(reviewed)
        self.assertFalse(self.root.exists())

    def test_queued_names_are_reserved_and_queue_change_invalidates_hash(self):
        preview = self.preview()
        Queue.submit(self.root, {"name": preview["name"], "steps": preview["steps"]})
        with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
            self.submit(preview)
        reviewed = self.preview()
        self.assertFalse(reviewed["ready_to_submit"])
        self.assertEqual(reviewed["preflight"]["queue_conflicts"],
                         preview["preflight"]["objects_to_create"])
        with self.assertRaisesRegex(ValueError, "PREFLIGHT_BLOCKED.*QUEUED_NAME_COLLISION"):
            self.submit(reviewed)

    def test_capacity_limit_mode_frozen_and_missing_native_op_are_explicit(self):
        for n in range(4):
            other = C.compile_request({"brief": "crate", "name": "Other" + str(n)})
            Queue.submit(self.root, {"name": other["name"], "steps": other["steps"]})
        reviewed = self.preview()
        self.assertFalse(reviewed["ready_to_submit"])
        self.assertIn("STUDIO_PLAN_QUEUE_FULL", reviewed["preflight"]["issues"])
        with self.assertRaisesRegex(ValueError, "PREFLIGHT_BLOCKED"):
            self.submit(reviewed)
        for record in Queue.list_jobs(self.root)["jobs"]:
            Queue.cancel(self.root, record["plan_id"])
        self.bpy.context.mode = "EDIT_MESH"
        self.assertIn("STUDIO_COMMAND_OBJECT_MODE_REQUIRED", self.preview()["preflight"]["issues"])
        self.bpy.context.mode = "OBJECT"
        self.scene["production_frozen_job"] = "snapshot"
        self.assertIn("RENDER_SNAPSHOT_IMMUTABLE", self.preview()["preflight"]["issues"])
        self.scene.pop("production_frozen_job")
        with mock.patch.object(Production, "OPERATIONS", Production.OPERATIONS - {"studio.create.model"}):
            reviewed = self.preview()
            self.assertEqual(reviewed["preflight"]["missing_operations"], ["studio.create.model"])
            with self.assertRaisesRegex(ValueError, "PREFLIGHT_BLOCKED"):
                self.submit(reviewed)

    def test_mutated_returned_steps_cannot_change_submitted_recipe(self):
        preview = self.preview()
        original_steps = copy.deepcopy(preview["steps"])
        preview["steps"][0]["payload"]["size"] = 99
        result = self.submit(preview)
        self.assertEqual(result["state"], "queued")
        self.assertEqual(self.routes[0][1]["steps"], original_steps)

    def test_altered_request_cannot_reuse_an_existing_submission_hash(self):
        preview = self.preview()
        self.submit(preview)
        for change in ({"brief": "wooden  crate asset"}, {"name": "Second"}, {"seed": 2}):
            changed = dict(preview["request"], **change, preview_sha256=preview["preview_sha256"])
            with self.assertRaisesRegex(ValueError, "PREVIEW_STALE"):
                Planner.submit(changed, self.root, self.scene)
        self.assertEqual(len(self.routes), 1)

    def test_symlink_and_corrupt_queue_receipts_fail_closed(self):
        self.root.mkdir()
        target = Path(self.temporary.name) / "Elsewhere"
        target.mkdir()
        folder = self.root / "StudioPlans"
        folder.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "SYMLINK"):
            self.preview()
        folder.unlink()
        preview = self.preview()
        result = self.submit(preview)
        path = folder / (result["plan_id"] + ".json")
        record = json.loads(path.read_text())
        record["steps"][0]["payload"]["size"] = 4
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            self.preview()
        with self.assertRaisesRegex(ValueError, "REVISION_CONFLICT"):
            self.submit(preview)


if __name__ == "__main__":
    unittest.main()
