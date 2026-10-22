# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender synthetic fixture, not a user-phone photorealism claim."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

root=Path(__file__).resolve().parents[1]
path=root/'full-app/scripts/render_studio_ops.py'
module_spec=importlib.util.spec_from_file_location('studio_ops_fixture',path)
ops=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(ops)

with tempfile.TemporaryDirectory() as d:
    folder=Path(d)/'Production';assets=folder/'Assets';assets.mkdir(parents=True)
    synthetic=assets/'synth.png'
    image=bpy.data.images.new('SyntheticReference',width=64,height=96,alpha=True)
    image.generated_type='COLOR_GRID';image.filepath_raw=str(synthetic);image.file_format='PNG'
    image.save();bpy.data.images.remove(image)
    digest=hashlib.sha256(synthetic.read_bytes()).hexdigest()
    target=assets/(digest+'.png');synthetic.rename(target)

    scene=bpy.context.scene
    cam=bpy.data.objects.get('Camera')
    if cam is None:
        cam=bpy.data.objects.new('StudioTestCamera',bpy.data.cameras.new('StudioTestCamera'))
        scene.collection.objects.link(cam)
    cam.location=[0,-5,2]
    cam.rotation_euler=(Vector([0,0,1])-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=cam
    bound=ops.execute('reference.bind',
        {'asset':target.name,'name':'SareeReferenceBoard','size':2,
         'location':[1,-1,1],'crop':[.1,.15,.9,.85],'opacity':.8},folder,scene)
    assert bound['native_uv_crop']==[.1,.15,.9,.85]
    assert bound['included_in_final_render'] is False
    ob=scene.objects['SareeReferenceBoard']
    assert ob.type=='MESH' and ob.hide_render
    assert ob.data.uv_layers.active and ob.data.materials[0].use_nodes
    assert ob['render_source_hash']==digest
    assert bound['packed'] is True, bound
    textures=[node.image for node in ob.data.materials[0].node_tree.nodes
              if node.type=='TEX_IMAGE' and node.image]
    assert textures and textures[0].packed_file is not None

    v=bpy.data.meshes.new('ModelFaceMesh')
    v.from_pydata([[-.2,-.1,1.0],[.2,-.1,1.0],[0,-.1,1.4]],[],[[0,1,2]])
    v.update()
    mesh=bpy.data.objects.new('ModelFace',v);scene.collection.objects.link(mesh)
    bpy.context.view_layer.update()
    landmarks={}
    for label,index in [('left_eye',0),('right_eye',1),('nose',2)]:
        ndc=world_to_camera_view(scene,scene.camera,mesh.matrix_world @ mesh.data.vertices[index].co)
        landmarks[label]=[float(ndc.x),float(1-ndc.y)]
    err=ops.execute('reference.landmarks',{'object':'ModelFace','reference':landmarks,
                                         'model':{'left_eye':0,'right_eye':1,'nose':2}},folder,scene)
    assert err['rms_normalized_image_error']<1e-8,err
    assert not err['visual_likeness_verified']
    page=ops.execute('object.geometry',{'object':'ModelFace','limit':2},folder,scene)
    assert page['total_vertices']==3 and len(page['vertex_page'])==2
    assert page['next_offset']==2
    result=ops.execute('operator.describe',{'operator':'object.shade_smooth'},folder,scene)
    assert result['arbitrary_python_allowed'] is False
    applied=ops.execute('operator.execute',
                        {'operator':'object.shade_smooth','expected_object':'ModelFace',
                         'parameters':{'object':'ModelFace'}},folder,scene)
    assert applied['performed_visible_pointer_click'] is False
    assert all(poly.use_smooth for poly in mesh.data.polygons)
    before=scene.render.resolution_x,scene.render.resolution_y
    inspection=ops.execute('viewport.inspect',{},folder,scene)
    assert not inspection['render_quality_modified']
    assert before==(scene.render.resolution_x,scene.render.resolution_y)
    try:
        clip=ops.execute('viewport.configure',{'radius':1,'distance':2},folder,scene)
        assert len(clip['viewports'])>0 and clip['viewport_only'],clip
        assert all(v['clip_end']/v['clip_start']<100000 for v in clip['viewports'])
        assert not clip['render_settings_changed'] and not clip['geometry_decimated']
    except ValueError as error:
        # -b can still hold VIEW_3D areas depending on the Blender fixture.
        assert 'NATIVE_VIEWPORT_NOT_OPEN' in str(error)
    assert before==(scene.render.resolution_x,scene.render.resolution_y)
    for op in ('python.eval','console.execute','wm.open_mainfile'):
        try:ops.execute('operator.execute',
                        {'operator':op,'expected_object':'ModelFace',
                         'parameters':{'object':'ModelFace'}},folder,scene)
        except ValueError:pass
        else:raise AssertionError('Denied operator unexpectedly ran')
print('PASS: native bpy reference UV crop, packed photo, camera projection, geometry paging and strict object tools')
print('NOT CLAIMED: identity likeness, Android frame stability, screenshot or video import')
