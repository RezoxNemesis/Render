# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender end-to-end fixture, including save and a clean reopen.

blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase08/test_phase08_bpy.py
The fixture saves only inside a temporary directory, not the user project.
"""
import importlib.util
import json
from pathlib import Path
import tempfile

import bpy

BASE=Path(__file__).resolve().parents[3]
path=BASE/'full-app/scripts/omega/phase08_world.py'
spec=importlib.util.spec_from_file_location('omega_phase08_world_native',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

bpy.ops.wm.read_factory_settings(use_empty=False)
scene=bpy.context.scene
camera_before=scene.camera
world_before=scene.world
render_before=(scene.render.engine,scene.render.resolution_x,scene.render.resolution_y,
               scene.render.resolution_percentage,scene.render.fps,scene.render.fps_base)
context={'scene':scene, 'available_memory_bytes':1024*1024*1024,
         'dry_run':False,'cancellation_requested':False}
payload={'name':'NativeRailTempleFixture','seed':31415,'trees':13,'grass':26}
dry=module.execute('omega.world.build_scene',payload,{**context,'dry_run':True})
assert dry['state']=='planned' and not dry['native_execution_verified']
assert scene.camera==camera_before and scene.world==world_before

receipt=module.execute('omega.world.build_scene',payload,context)
assert receipt['native_execution_verified'] and not receipt['quality_reduced']
assert not receipt['already_complete']
assert receipt['artifact']['sha256'] is None
check=module.audit('omega.world.audit',{'name':payload['name']},context)
assert check['complete'],check
assert check['counts']['meshes'] >= 50,check
assert check['counts']['mesh_instances'] >= 30,check
assert check['counts']['vertices_in_datablocks'] > 1600,check
assert check['counts']['native_cameras']==1 and check['counts']['native_lights']==1
assert check['external_assets_downloaded']==0
assert check['preview_proxy_count']==0
assert check['license']=='GPL-2.0-or-later'
assert all(mesh.materials for mesh in (o.data for o in scene.objects
                                        if o.name.startswith('P08_NativeRailTempleFixture_')
                                        and o.type=='MESH'))
assert (scene.render.engine,scene.render.resolution_x,scene.render.resolution_y,
        scene.render.resolution_percentage,scene.render.fps,scene.render.fps_base)==render_before

replay=module.execute('omega.world.build_scene',payload,context)
assert replay['already_complete'] and replay['created']==[]
assert check['source_revision']==replay['source_revision']
try:
    module.execute('omega.world.build_scene',{**payload,'seed':7},context)
except ValueError as error:
    assert str(error)=='CHECKPOINT_CONFLICT'
else:raise AssertionError('Different scene specification replay must fail')

with tempfile.TemporaryDirectory(prefix='omega-p08-real-blend-') as folder:
    saved=Path(folder)/'phase08_native_railway_temple.blend'
    assert 'FINISHED' in bpy.ops.wm.save_as_mainfile(filepath=str(saved),check_existing=False)
    assert saved.exists() and saved.stat().st_size > 1024
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert 'FINISHED' in bpy.ops.wm.open_mainfile(filepath=str(saved))
    reopened=bpy.context.scene
    reopened_check=module.audit('omega.world.audit',{'name':payload['name']}, {'scene':reopened})
    assert reopened_check['complete'],reopened_check
    assert reopened_check['source_revision']==check['source_revision'],(check,reopened_check)
    assert reopened_check['counts']==check['counts'],(check,reopened_check)
    print('PASS: REAL bpy create/save/reopen:',json.dumps(reopened_check,sort_keys=True))

# Rollback test in a separate fresh scene: interruption must leave no P08 meshes.
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
before_meshes=len(bpy.data.meshes)
count={'n':0}
def cancel_mid_build():
    count['n']+=1
    return count['n']>4
try:
    module.execute('omega.world.build_scene',{'name':'InterruptedFixture','trees':2,'grass':5},
                   {'scene':scene, 'cancellation_requested':cancel_mid_build})
except RuntimeError as error:
    assert str(error)=='CANCELLED',error
else:raise AssertionError('Cancelled native build must not succeed')
assert scene.collection.children.get('P08_InterruptedFixture') is None
assert len(bpy.data.meshes)==before_meshes
print('PASS: native Blender interruption rollback, no orphaned geometry')
