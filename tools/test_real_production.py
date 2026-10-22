# SPDX-License-Identifier: GPL-2.0-or-later
"""Desktop CI semantic fixture tests only; not Android production rendering proof."""
import importlib.util
import json
from pathlib import Path
import tempfile
import bpy

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('render_production_under_test',ROOT/'full-app/scripts/render_production.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as tmp:
    spool=Path(tmp)/'render_bpy_jobs';spool.mkdir()
    def run(operation,payload):
        return module.execute({'operation':operation,'payload':payload},str(spool),'a'*32)
    head=run('mesh.create',{'name':'ProductionTestHead','kind':'UV_SPHERE','segments':64,'rings':32,'location':[2,0,0],'scale':[0.8,0.7,1.0]})
    assert head['vertices']>1000,head
    assert head['polygons']>1000,head
    run('material.assign',{'object':'ProductionTestHead','name':'ProductionTestSkin','color':[0.6,0.35,0.22],'roughness':0.55})
    ob=bpy.context.scene.objects['ProductionTestHead']
    assert ob.data.materials[0].use_nodes
    assert all(f.use_smooth for f in ob.data.polygons)
    before=ob.matrix_world.copy();bpy.context.view_layer.update();before=ob.matrix_world.copy()
    run('group.create',{'name':'ProductionTestRoot','children':['ProductionTestHead'],'location':[0,0,0]})
    bpy.context.view_layer.update()
    assert (ob.matrix_world.translation-before.translation).length<0.0001
    run('animation.keys',{'object':'ProductionTestRoot','keys':[{'frame':1,'path':'location','value':[0,0,0]},{'frame':10,'path':'location','value':[3,0,0]}]})
    bpy.context.scene.frame_set(10);bpy.context.view_layer.update()
    assert abs(ob.matrix_world.translation.x-5)<0.0001,ob.matrix_world.translation
    field=run('instances.create',{'name':'ProductionTestInstances','source':'ProductionTestHead','counts':[2,3,1],'spacing':[2,2,2],'available_memory_bytes':8*1024**3})
    assert field['instance_count']==6 and not field['realize_instances']
    group=bpy.context.scene.objects['ProductionTestInstances'].modifiers[0].node_group
    assert sum(n.bl_idname=='GeometryNodeInstanceOnPoints' for n in group.nodes)==3
    assert not any(n.bl_idname=='GeometryNodeRealizeInstances' for n in group.nodes)
    run('camera.aim',{'name':'ProductionTestCamera','location':[14,-18,14],'target':[1,1,1],'lens':35})
    run('world.configure',{'color':[0.25,0.4,0.6],'strength':1.0})
    checkpoint=run('project.checkpoint',{'name':'ProductionFixture'})
    assert checkpoint['bytes']>256
    page=run('scene.inspect',{'limit':1});assert len(page['objects'])==1 and page['next_offset']==1
    plan=run('render.plan',{'width':64,'height':64,'fps':24,'start':1,'end':1,'samples':2,'engine':'CYCLES'})
    done=run('render.step',{'job_id':plan['job_id']})
    assert done['state']=='frames_complete' and done['completed_frames']==1,done
    again=run('render.step',{'job_id':plan['job_id']});assert again['completed_frames']==1
    manifest=json.loads((Path(tmp)/'Production'/plan['job_id']/'manifest.json').read_text())
    frame=Path(tmp)/'Production'/plan['job_id']/manifest['frames']['1']['filename']
    assert frame.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert done['spec']['width']==64 and done['spec']['height']==64
print('PASS: real bpy geometry, PBR, hierarchy, instancing, checkpoint, pagination and immutable frame job')
print('NOT CLAIMED: physical Android GPU, hardware encoder, screenshots, image-to-3D or 10-million device stress test')
