# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Blender bpy smoke test: rig keys, facial keys, NLA, evaluated motion.

Uses synthetic geometry and a generated reference. No personal reference photos,
Android surface, video decoder or final photorealism is claimed.
"""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
source=ROOT/"full-app/scripts/render_reference_motion.py"
spec=importlib.util.spec_from_file_location("render_reference_motion_test",source)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
scene=bpy.context.scene
settings=(scene.render.engine,scene.render.resolution_x,scene.render.resolution_y,
          scene.render.fps,scene.render.fps_base,scene.frame_start,scene.frame_end)

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/"Production"
    assets=root/"Assets";assets.mkdir(parents=True)
    source_image=assets/"preview.png"
    generated=bpy.data.images.new("GeneratedTestReference",width=64,height=64,alpha=True)
    generated.generated_type="COLOR_GRID"
    generated.filepath_raw=str(source_image)
    generated.file_format="PNG";generated.save();bpy.data.images.remove(generated)
    digest=hashlib.sha256(source_image.read_bytes()).hexdigest()
    photo=assets/(digest+".png");source_image.rename(photo)

    def camera(name,position):
        data=bpy.data.cameras.new(name+"Data")
        cam=bpy.data.objects.new(name,data)
        scene.collection.objects.link(cam);cam.location=position
        cam.rotation_euler=(Vector((0,0,1))-cam.location).to_track_quat("-Z","Y").to_euler()
        return cam

    cam=camera("FrontCam",(0,-6,1.0))
    side=camera("SideCam",(6,-5,1.0))
    scene.camera=cam

    mesh=bpy.data.meshes.new("FigureGeometry")
    mesh.from_pydata([(-.2,0,.9),(.2,0,.9),(0,0,1.35)],[],[(0,1,2)])
    mesh.update()
    figure=bpy.data.objects.new("Figure",mesh)
    scene.collection.objects.link(figure)
    face=figure
    face.shape_key_add(name="Basis")
    face.shape_key_add(name="Blink")

    bound=M.execute("reference.workspace.open",{
        "asset":photo.name,"mode":"CAMERA","model":"Figure"},root,scene)
    assert bound["native_blender_panel_assigned"] and bound["packed_in_blend"],bound
    assert not bound["exact_3d_likeness_claimed"] and bound["not_in_final_camera_render"]

    views=[]
    bpy.context.view_layer.update()
    for camera_obj in (cam,side):
        points={}
        for label,index in (("left_eye",0),("right_eye",1),("nose",2)):
            uv=world_to_camera_view(scene,camera_obj,figure.matrix_world @ mesh.vertices[index].co)
            points[label]=[float(uv.x),float(1-uv.y)]
        views.append({"camera":camera_obj.name,"reference":points,
                      "model":{"left_eye":0,"right_eye":1,"nose":2}})
    alignment=M.execute("reference.compare.multiview",{"object":"Figure",
                 "views":views},root,scene)
    assert alignment["overall_rms_normalized_image_error"]<1e-8,alignment

    rig_data=bpy.data.armatures.new("FigureRigData")
    rig=bpy.data.objects.new("FigureRig",rig_data)
    scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active=rig;rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    head=rig_data.edit_bones.new("Head")
    head.head=(0,0,0);head.tail=(0,0,1)
    bpy.ops.object.mode_set(mode="OBJECT")
    assert "Head" in rig.pose.bones

    clip=M.execute("animation.clip.create",{
        "rig":"FigureRig","name":"TestMotionClip","interpolation":"LINEAR","nla":True,
        "poses":[
            {"frame":1,"bones":[{"bone":"Head","location":[0,0,0],
                                "rotation_euler":[0,0,0]}],
             "shapes":[{"object":"Figure","key":"Blink","value":0.0}]},
            {"frame":13,"bones":[{"bone":"Head","location":[.3,0,0],
                                 "rotation_euler":[0,.3,0]}],
             "shapes":[{"object":"Figure","key":"Blink","value":1.0}]}
        ]},root,scene)
    assert clip["real_blender_keyframes_inserted"],clip
    assert clip["bone_keyframe_points"]>0 and clip["shape_channels_keyed"]==2,clip
    assert len(clip["nla_strips"])==2,clip
    inspected=M.execute("animation.clip.inspect",{"rig":"FigureRig"},root,scene)
    assert inspected["rigs"][0]["nla_tracks"],inspected
    motion=M.execute("animation.motion.audit",{
        "rig":"FigureRig","bones":["Head"],"frames":[1,5,9,13]},root,scene)
    assert motion["native_pose_evaluated"] and motion["frame_restored"],motion
    assert motion["trajectories"][0]["total_path_distance"]>0.25,motion
    assert bound["asset"]==photo.name and scene["render_compare_source"]==photo.name
    assert settings==(scene.render.engine,scene.render.resolution_x,scene.render.resolution_y,
                     scene.render.fps,scene.render.fps_base,scene.frame_start,scene.frame_end)
print("PASS: actual Blender two-camera landmark audit, packed reference, armature, face keys, LINEAR NLA and evaluated motion")
print("NOT VERIFIED: live Android area split, MP4 movie decoding, physical phone playback, exact photo likeness")
