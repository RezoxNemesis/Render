# SPDX-License-Identifier: GPL-2.0-or-later
"""Host-only security, schema, and durable cache tests (NOT bpy physics)."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2] / 'full-app/scripts/omega/phase13_simulation.py'
spec = importlib.util.spec_from_file_location('phase13_simulation_under_test', PATH)
p13 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p13)


def request():
    return {"expected_scene_revision": "a" * 64,
            "frame_start": 1, "frame_end": 32,
            "objects": [{"name": "Debris", "role": "ACTIVE", "mass": 2.5},
                        {"name": "Ground", "role": "PASSIVE"}],
            "cache_mode": "SAMPLED_NATIVE_PHYSICS", "save_blend_copy": True}


class Phase13Contracts(unittest.TestCase):
    def test_pure_import_and_exports(self):
        self.assertEqual(p13.CONTRACT_VERSION, "RENDER-OMEGA-1")
        self.assertEqual(p13.OPERATION_NAMES,
                         ("omega.simulation.bake", "omega.simulation.inspect_cache"))
        self.assertNotIn('bpy', p13.__dict__, 'No Blender import at module load time')

    def test_normalized_typed_payload(self):
        p = p13.validate("omega.simulation.bake", request())
        self.assertEqual(p["objects"][0]["mass"], 2.5)
        self.assertEqual(p["objects"][1]["shape"], "BOX")
        self.assertEqual(p["objects"][0]["collision_group"], 0)
        self.assertEqual(p["cache_mode"], "SAMPLED_NATIVE_PHYSICS")
        self.assertEqual(p["frame_end"] - p["frame_start"] + 1, 32)

    def test_point_cache_default_never_silent_sample_fallback(self):
        p = request()
        del p["cache_mode"]
        self.assertEqual(p13.validate("omega.simulation.bake", p)["cache_mode"],
                         "NATIVE_POINT_CACHE")

    def test_rejects_untrusted_paths_and_operators(self):
        for field, value in (("root", "/tmp/owned"), ("filepath", "../../secret"),
                             ("operator", "bpy.ops.script.python_file_run"),
                             ("script", "import os")):
            p = request(); p[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "INVALID_ARGUMENTS"):
                p13.validate("omega.simulation.bake", p)
        with self.assertRaisesRegex(ValueError, 'UNSUPPORTED_NATIVE_FEATURE'):
            p13.validate('omega.simulation.execute_python', {})

    def test_frame_and_memory_budgets(self):
        for start, end in ((1, 23), (1, 121), (2, 10000), (1, True), (50, 49)):
            p = request(); p['frame_start'] = start; p['frame_end'] = end
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                p13.validate('omega.simulation.bake', p)
        p = request(); p['frame_end'] = 120
        self.assertEqual(p13.validate('omega.simulation.bake', p)['frame_end'], 120)

    def test_rejects_duplicate_or_missing_colliders(self):
        for objects in ([], [request()['objects'][0]],
                        [{"name": 'Same', 'role': 'ACTIVE'}, {"name": 'Same', 'role': 'PASSIVE'}],
                        [{"name": 'A', 'role': 'ACTIVE'}, {"name": 'B', 'role': 'ACTIVE'}]):
            p = request(); p['objects'] = objects
            with self.subTest(objects=objects), self.assertRaises(ValueError):
                p13.validate('omega.simulation.bake', p)

    def test_rejects_nonfinite_mass_and_bad_colliders(self):
        for key, value in (("mass", float('nan')), ("mass", float('inf')),
                           ("mass", -1), ("mass", 0), ("friction", 1.01),
                           ("restitution", -0.1), ("collision_group", 20),
                           ("shape", "MESH")):
            p = request(); p['objects'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                p13.validate('omega.simulation.bake', p)
        p = request(); p['save_blend_copy'] = 1
        with self.assertRaises(ValueError):
            p13.validate('omega.simulation.bake', p)

    def test_revision_and_role_integrity(self):
        p = request(); p['expected_scene_revision'] = 'notahash'
        with self.assertRaises(ValueError): p13.validate('omega.simulation.bake', p)
        p = request(); p['objects'][1]['mass'] = 10
        with self.assertRaises(ValueError): p13.validate('omega.simulation.bake', p)
        p = request(); p['objects'][0]['name'] = '../escape'
        with self.assertRaises(ValueError): p13.validate('omega.simulation.bake', p)

    def test_cache_atomic_write_and_hash_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame = root / 'frame_000001.json'
            digest = p13._write_json(frame, {'frame': 1, 'objects': {'Box': {'location': [0, 0, 2]}}})
            self.assertEqual(digest, p13._sha_file(frame))
            self.assertEqual(p13._read_json(frame)['frame'], 1)
            manifest = {'frames': [{'frame': 1, 'file': frame.name, 'sha256': digest}],
                        'snapshot': None}
            self.assertEqual(p13._verify_entries(root, manifest), 1)
            frame.write_bytes(b'corrupted')
            with self.assertRaisesRegex(ValueError, 'CACHE_CORRUPT'):
                p13._verify_entries(root, manifest)

    def test_cache_symlink_and_directory_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                p13._cache_directory({'job_id': '../escape', 'production_root': root}, True)
            with self.assertRaises(ValueError):
                p13._cache_directory({'job_id': 'a' * 32, 'production_root': 'relative'}, True)
            (root / 'omega-simulation').symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'CACHE_OUTSIDE_SCOPE'):
                p13._cache_directory({'job_id': 'a' * 32, 'production_root': root}, True)

    def test_no_fake_success_without_native_runtime(self):
        with self.assertRaises(ValueError):
            p13.execute('omega.simulation.bake', request(), {})
        self.assertEqual(p13.validate('omega.simulation.inspect_cache', {}), {})
        with self.assertRaises(ValueError):
            p13.validate('omega.simulation.inspect_cache', {'folder': '/secret'})


if __name__ == '__main__':
    unittest.main()
