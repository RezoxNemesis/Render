# SPDX-License-Identifier: GPL-2.0-or-later
"""Run with real Blender: blender -b --python-exit-code 1 --python <this>.

Genuine native physics and a saved/reopened .blend. No mock bpy or hand-keyframes.
"""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[3]
module_path = ROOT / 'full-app/scripts/omega/phase13_simulation.py'
spec = importlib.util.spec_from_file_location('phase13_simulation_fixture', module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


FACES = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
VERTS = [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, .5, -.5), (-.5, .5, -.5),
         (-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)]


def cube(scene, name, position, scale):
    mesh = bpy.data.meshes.new(name + '_Mesh')
    mesh.from_pydata(VERTS, [], FACES)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    obj.location = position
    obj.scale = scale
    return obj


def run():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 48
    scene.gravity = (0, 0, -9.81)
    floor = cube(scene, 'Ground', (0, 0, -.5), (12, 12, 1))
    first = cube(scene, 'DebrisOne', (0, 0, 3.2), (1, 1, 1))
    second = cube(scene, 'DebrisTwo', (.7, 0, 4.8), (.75, .75, .75))
    names = [first.name, second.name, floor.name]
    revision = module.scene_revision(scene, names)
    request = {'objects': [{'name': 'DebrisOne', 'role': 'ACTIVE', 'mass': 2.0},
                           {'name': 'DebrisTwo', 'role': 'ACTIVE', 'mass': 0.7},
                           {'name': 'Ground', 'role': 'PASSIVE', 'shape': 'BOX'}],
               'frame_start': 1, 'frame_end': 36, 'expected_scene_revision': revision,
               'cache_mode': 'SAMPLED_NATIVE_PHYSICS', 'save_blend_copy': True}
    quality_before = (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
                      scene.render.fps, scene.render.fps_base)
    with tempfile.TemporaryDirectory(prefix='omega-phase13-bpy-') as root:
        context = {'scene': scene, 'production_root': root, 'job_id': '7' * 32,
                   'dry_run': False, 'cancellation_requested': False}
        result = module.execute('omega.simulation.bake', request, context)
        assert result['state'] == 'succeeded', result
        assert result['native_execution_verified'] is True
        assert result['native_point_cache_baked'] is False
        assert result['sampled_frames'] == 36
        assert result['movement_meters']['DebrisOne'] > 0.2, result
        assert result['movement_meters']['DebrisTwo'] > 0.2, result
        assert scene.rigidbody_world is not None
        assert all(scene.objects[name].rigid_body is not None for name in names)
        assert all(scene.objects[name].animation_data is None for name in names), 'Keyframes not physics'
        assert first.rigid_body.type == 'ACTIVE' and floor.rigid_body.type == 'PASSIVE'
        assert (scene.render.engine, scene.render.resolution_x, scene.render.resolution_y,
                scene.render.fps, scene.render.fps_base) == quality_before
        assert bpy.data.filepath == '', 'Save-copy must not change active project'
        readback = module.audit('omega.simulation.inspect_cache', {}, context)
        assert readback['scene_revision_verified'] and readback['sampled_frames'] == 36
        repeated = module.execute('omega.simulation.bake', request, context)
        assert repeated['idempotent_replay'] is True
        job_dir = Path(root) / 'omega-simulation' / ('7' * 32)
        checkpoint = job_dir / result['recovery_checkpoint']['file']
        assert checkpoint.is_file() and checkpoint.read_bytes().startswith(b'BLENDER')
        manifest = json.loads((job_dir / 'manifest.json').read_text(encoding='utf8'))
        assert len(manifest['frames']) == 36
        snapshot = job_dir / result['snapshot']['file']
        assert snapshot.is_file() and snapshot.read_bytes().startswith(b'BLENDER')
        for f in (1, 12, 24, 36):
            sample = json.loads((job_dir / ('frame_%06d.json' % f)).read_text())
            assert sample['frame'] == f and len(sample['objects']) == 3
        bpy.ops.wm.open_mainfile(filepath=str(snapshot), load_ui=False)
        scene = bpy.context.scene
        assert scene.objects['DebrisOne'].rigid_body.type == 'ACTIVE'
        assert scene.objects['Ground'].rigid_body.type == 'PASSIVE'
        assert all(scene.objects[name].animation_data is None for name in names)
        scene.frame_set(1)
        z1 = scene.objects['DebrisOne'].evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.z
        for f in range(2, 37):
            scene.frame_set(f)
        z2 = scene.objects['DebrisOne'].evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.z
        assert z1 - z2 > .1, (z1, z2)
        print('PASS: REAL bpy rigid colliders, 36 evaluated physics frames, '
              'checked sample hashes, idempotence, unchanged render settings, .blend reopen',
              json.dumps({'z_initial': z1, 'z_last': z2, 'snapshot_sha256': result['snapshot']['sha256']}))


if __name__ == '__main__':
    run()
