# SPDX-License-Identifier: GPL-2.0-or-later
"""Render Studio native motion visual acceptance fixture.

Original synthetic art only. Blender creates actual keyed armature + facial
motion, renders new PNG for each frame and saves an editable .blend. This
desktop-CI fixture is NOT proof of running on the Android phone or matching
the owner's character benchmarks.
"""
import argparse
from pathlib import Path
import math
import sys
import json
import hashlib

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_reference_motion as director

def material(name,color,metallic=0,roughness=.5,emission=0):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    shader=mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value=(*color,1)
    shader.inputs["Metallic"].default_value=metallic
    shader.inputs["Roughness"].default_value=roughness
    if emission:
        key="Emission Color" if "Emission Color" in shader.inputs else "Emission"
        shader.inputs[key].default_value=(*color,1)
        strength=shader.inputs.get("Emission Strength")
        if strength:strength.default_value=emission
    return mat

def sphere(name,location,scale,mat,segments=24,rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=location)
    ob=bpy.context.object
    ob.name=name
    ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    ob.data.materials.append(mat)
    for face in ob.data.polygons:face.use_smooth=True
    return ob

def point_camera(camera,lookat):
    direction=Vector(lookat)-camera.location
    camera.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()

def attach_to_bone(ob,armature,bone):
    before=ob.matrix_world.copy()
    ob.parent=armature
    ob.parent_type="BONE"
    ob.parent_bone=bone
    ob.matrix_world=before.copy()
    bpy.context.view_layer.update()

def make_rig(scene):
    data=bpy.data.armatures.new("MotionDirectorArmature")
    rig=bpy.data.objects.new("MotionDirectorRig",data)
    scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones={
      "Torso":((0,0,.65),(0,0,1.5),None),
      "Head":((0,0,1.53),(0,0,2.0),"Torso"),
      "LeftArm":((-.33,0,1.43),(-.75,-.015,1.04),"Torso"),
      "RightArm":((.33,0,1.43),(.75,-.015,1.04),"Torso")
    }
    for name,(head,tail,parent) in bones.items():
        edit=data.edit_bones.new(name)
        edit.head=head
        edit.tail=tail
        if parent:edit.parent=data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front=True
    return rig

def setup_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.samples=12
    scene.cycles.use_denoising=False
    scene.render.resolution_x=320
    scene.render.resolution_y=480
    scene.render.resolution_percentage=100
    scene.render.fps=24
    scene.frame_start=1
    scene.frame_end=48
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.world.color=(.06,.06,.09)
    if scene.world and scene.world.use_nodes:
        bg=scene.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Color"].default_value=(.08,.10,.17,1)
            bg.inputs["Strength"].default_value=.6
    skin=material("Clay skin",(.53,.38,.30),0,.72)
    coat=material("Matte midnight coat",(.055,.075,.12),.13,.56)
    gold=material("Worn bronze trim",(.60,.38,.13),.64,.29)
    hair=material("Dark aubergine hair",(.08,.06,.09),.05,.47)
    iris=material("Eyes",(.68,.75,.84),.03,.22)
    black=material("Pupils",(.02,.02,.03),.08,.28)
    stage=material("Concrete floor",(.16,.18,.21),.04,.81)
    mist=material("Backdrop indigo",(.095,.105,.18),.0,.96)
    bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,0))
    plane=bpy.context.object;plane.name="Floor";plane.data.materials.append(stage)
    bpy.ops.mesh.primitive_cube_add(size=2,location=(0,2.2,2.2))
    wall=bpy.context.object;wall.name="Cyclorama";wall.scale=(12,.08,4)
    wall.data.materials.append(mist)

    rig=make_rig(scene)
    body=sphere("Coat torso",(0,0,1.09),(.40,.27,.62),coat)
    attach_to_bone(body,rig,"Torso")
    neck=sphere("Neck",(0,0,1.56),(.12,.13,.18),skin)
    attach_to_bone(neck,rig,"Torso")
    head=sphere("Head mesh",(0,-.015,1.88),(.27,.26,.35),skin)
    attach_to_bone(head,rig,"Head")
    hair_top=sphere("Hair cap",(0,.025,2.105),(.285,.28,.14),hair)
    attach_to_bone(hair_top,rig,"Head")
    for side in [-1,1]:
        sleeve=sphere("Sleeve_"+str(side),(.47*side,.0,1.22),(.14,.17,.38),coat)
        attach_to_bone(sleeve,rig,"LeftArm" if side<0 else "RightArm")
        cuff=sphere("Wrist_"+str(side),(.66*side,-.015,.96),(.12,.12,.15),gold)
        attach_to_bone(cuff,rig,"LeftArm" if side<0 else "RightArm")
        eye=sphere("Eye_"+str(side),(.115*side,-.246,1.96),(.063,.04,.041),iris)
        # Morph shape keys drive real geometry, not opacity or a frozen still.
        eye.shape_key_add(name="Basis",from_mix=False)
        blink=eye.shape_key_add(name="Blink",from_mix=False)
        for vertex in blink.data: vertex.co.z *= .08
        eye["reference_motion_eye"]=True
        attach_to_bone(eye,rig,"Head")
        pupil=sphere("Pupil_"+str(side),(.115*side,-.280,1.962),(.027,.014,.027),black)
        attach_to_bone(pupil,rig,"Head")
        brow=sphere("Brow_"+str(side),(.115*side,-.24,2.039),(.091,.027,.018),hair)
        attach_to_bone(brow,rig,"Head")
        leg=sphere("Trouser_"+str(side),(.15*side,0,.44),(.16,.20,.44),coat)
        shoe=sphere("Boot_"+str(side),(.15*side,-.13,.10),(.19,.32,.105),black)
    belt=sphere("Copper belt buckle",(0,-.265,1.03),(.11,.04,.11),gold)
    attach_to_bone(belt,rig,"Torso")
    sphere("Ground pedestal",(0,0,.055),(.83,.75,.075),gold,48,16)

    def area_light(name,loc,power,radius,color):
        data=bpy.data.lights.new(name,"AREA")
        data.energy=power
        data.shape="DISK"
        data.size=radius
        data.color=color
        obj=bpy.data.objects.new(name,data)
        scene.collection.objects.link(obj)
        obj.location=loc
        point_camera(obj,(0,0,1.3))
    area_light("Key softbox",(-3,-4,4),410,3.0,(1,.84,.67))
    area_light("Cool rim",(2,2,3.5),500,2.5,(.53,.65,1))
    area_light("Soft fill",(3,-2,2.4),130,3,(.65,.76,1))

    camera_data=bpy.data.cameras.new("PortraitLens")
    camera=bpy.data.objects.new("PortraitCamera",camera_data)
    scene.collection.objects.link(camera)
    camera.location=(3.15,-7.9,2.40)
    point_camera(camera,(0,-.04,1.12))
    camera_data.type="PERSP"
    camera_data.lens=46
    scene.camera=camera
    return scene,rig

def animate(scene,rig):
    shapes=[]
    for side in [-1,1]:
        shapes.append({"object":"Eye_"+str(side),"key":"Blink","value":0.0})
    def pose(frame,head_pitch,rightarm,blink,torso=.0):
        return {"frame":frame,"bones":[
            {"bone":"Torso","rotation_euler":[0,0,torso]},
            {"bone":"Head","rotation_euler":[head_pitch,.06*math.sin(frame*.12),head_pitch*.35]},
            {"bone":"RightArm","rotation_euler":[0,rightarm,0.18*math.sin(frame*.08)]},
            {"bone":"LeftArm","rotation_euler":[0,-.09,0]}
        ],"shapes":[dict(value=blink,object=e["object"],key="Blink") for e in shapes]}
    director.execute("animation.clip.create",{
        "rig":rig.name,"name":"CinematicActingTake01","nla":True,
        "interpolation":"BEZIER","poses":[
            pose(1,-.08,0,0),pose(12,-.02,-.48,0,torso=.03),
            pose(18,.06,-.82,1,torso=.04),pose(23,.12,-.86,0),
            pose(34,.10,-.65,0,torso=-.02),
            pose(39,.03,-.36,1),pose(43,-.01,-.2,0),
            pose(48,-.045,-.04,0,torso=0)
        ]},Path("/"),scene)
    report=director.execute("animation.motion.audit",{
       "rig":rig.name,"bones":["Head","RightArm"],"frames":[1,12,18,24,34,43,48]
    },Path("/"),scene)
    assert report["trajectories"][1]["total_path_distance"]>.05,report
    assert report["trajectories"][0]["total_path_distance"]>.01,report
    return report

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as inp:
        for item in iter(lambda:inp.read(2**20),b""):digest.update(item)
    return digest.hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    folder=Path(args.output)
    folder.mkdir(parents=True,exist_ok=True)
    scene,rig=setup_scene()
    report=animate(scene,rig)
    project=folder/"CinematicActingTake01.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(project),compress=True)
    frame_dir=folder/"png_masters"
    frame_dir.mkdir(exist_ok=True)
    frame_hashes={}
    for frame in range(1,49):
        scene.frame_set(frame)
        target=frame_dir/f"acting_{frame:04d}.png"
        scene.render.filepath=str(target)
        result=bpy.ops.render.render(write_still=True)
        if "FINISHED" not in result or not target.is_file() or target.stat().st_size<1000:
            raise RuntimeError(f"RENDER_FRAME_UNVERIFIED:{frame}")
        frame_hashes[str(frame)]=sha(target)
    if len(set(frame_hashes.values()))<30:
        raise RuntimeError("ANIMATION_APPEARS_STATIC_NOT_NATIVE_MOTION")
    metadata={
       "format":"RenderStudioNativeMotionFixtureV1",
       "original_synthetic_character":True,
       "engine":str(scene.render.engine),
       "resolution":[scene.render.resolution_x,scene.render.resolution_y],
       "fps":scene.render.fps,
       "frames":48,
       "actual_image_hashes":frame_hashes,
       "native_pose_audit":report,
       "blend_project_sha256":sha(project),
       "phone_mp4_render_proven":False,
       "reference_benchmark_likeness_proven":False
    }
    (folder/"evidence.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print("PASS: 48 individually rendered PNGs, multiple distinct frames, "
          "rig, shape-key motion, NLA, and editable .blend; NOT a static zoom.")

if __name__=="__main__":
    main()
