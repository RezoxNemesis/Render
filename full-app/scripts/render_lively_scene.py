# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed, on-device Blender scene tools. No remote code or path execution.

Every operation runs from Render's existing Blender bpy main-thread timer.
This module is packaged alongside render_agent_startup.py in the native APK.
"""
import hashlib
import math
from pathlib import Path
import re

import bpy
from mathutils import Vector

_PROJECT_NAME = re.compile(r"Render_[a-f0-9]{32}\.blend\Z")
_PREFIX = "RS_"


def restore_scene(args, spool):
    """Import the selected Render-owned saved scene without replacing other tabs/scenes."""
    if set(args) != {"filename"}:
        raise ValueError("INVALID_RESTORE_ARGUMENTS")
    filename = args["filename"]
    if not isinstance(filename, str) or not _PROJECT_NAME.fullmatch(filename):
        raise ValueError("INVALID_SAVED_PROJECT_FILENAME")
    if not spool:
        raise RuntimeError("RENDER_SPOOL_UNAVAILABLE")
    projects = Path(spool).resolve().parent / "Projects"
    file = projects / filename
    if not file.is_file() or file.is_symlink() or file.resolve().parent != projects.resolve():
        raise ValueError("SAVED_PROJECT_NOT_FOUND")
    if file.stat().st_size < 256:
        raise ValueError("SAVED_PROJECT_INCOMPLETE")
    scene_before = bpy.context.scene
    with bpy.data.libraries.load(str(file), link=False) as (source, target):
        if not source.scenes:
            raise ValueError("SAVED_PROJECT_HAS_NO_SCENE")
        target.scenes = [source.scenes[0]]
    restored = target.scenes[0]
    if restored is None or len(restored.objects) < 1:
        raise RuntimeError("SAVED_SCENE_RECOVERY_FAILED")
    window = bpy.context.window
    if window is None:
        raise RuntimeError("BLENDER_WINDOW_UNAVAILABLE")
    window.scene = restored
    return {
        "restored_scene": restored.name,
        "objects": len(restored.objects),
        "previous_scene_preserved": scene_before in bpy.data.scenes,
        "source_file": filename,
        "executed_by": "bpy-main-thread-on-android",
    }


def _mat(name, rgb, metallic=0.0, roughness=0.62):
    material = bpy.data.materials.get(_PREFIX + name)
    if material is None:
        material = bpy.data.materials.new(_PREFIX + name)
    material.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = (*rgb, 1.0)
        shader.inputs["Metallic"].default_value = metallic
        shader.inputs["Roughness"].default_value = roughness
    return material


def _mesh(name, shape, loc, scale, mat, collection, parent=None):
    if shape == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=1.0)
    elif shape == "cone":
        bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=1.0, radius2=0.0, depth=2.0)
    elif shape == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=1.0, depth=2.0)
    else:
        bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = bpy.context.object
    ob.name = _PREFIX + name
    for previous in list(ob.users_collection):
        previous.objects.unlink(ob)
    collection.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.scale = scale
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    if shape == "sphere":
        for polygon in ob.data.polygons:
            polygon.use_smooth = True
    return ob


def _root(name, collection, location):
    ob = bpy.data.objects.new(_PREFIX + name, None)
    collection.objects.link(ob)
    ob.location = location
    return ob


def _animate_travel(root, start, end, frames, hop=0.05):
    first, last = frames
    middle = (first + last) // 2
    # Characters and quadrupeds have local -Y forward; turn them toward the
    # actual path so their walk cycles don't appear to slide sideways.
    dx, dy = end[0] - start[0], end[1] - start[1]
    if abs(dx) + abs(dy) > 0.001:
        root.rotation_euler.z = math.atan2(dx, -dy)
        root.keyframe_insert(data_path="rotation_euler", frame=first)
    for frame, progress in ((first, 0.0), (middle, 0.5), (last, 1.0)):
        root.location = (
            start[0] + (end[0] - start[0]) * progress,
            start[1] + (end[1] - start[1]) * progress,
            start[2] + hop * (1.0 if progress == 0.5 else 0.0),
        )
        root.keyframe_insert(data_path="location", frame=frame)


def _walk_limb(ob, frames, phase):
    start, end = frames
    for frame in range(start, end + 1, 8):
        ob.rotation_euler.x = phase * 0.42 * math.sin((frame - start) * math.pi / 12.0)
        ob.keyframe_insert(data_path="rotation_euler", frame=frame)
    ob.rotation_euler.x = 0.0
    ob.keyframe_insert(data_path="rotation_euler", frame=end)


def _person(name, start, end, clothes, skin, collection, frames, child=False):
    size = 0.72 if child else 1.0
    root = _root("Walker_" + name, collection, start)
    _mesh(name + "_Body", "sphere", (0, 0, 1.35*size), (.39*size, .24*size, .59*size), clothes, collection, root)
    _mesh(name + "_Head", "sphere", (0, 0, 2.14*size), (.28*size, .27*size, .32*size), skin, collection, root)
    hair = _mat("Hair", (.12, .08, .06))
    _mesh(name + "_Hair", "sphere", (0, .01*size, 2.36*size), (.27*size,.28*size,.13*size),hair,collection,root)
    for side in (-1, 1):
        leg = _mesh(name + ("_LeftLeg" if side < 0 else "_RightLeg"), "cylinder",
            (.19*side*size,0,.52*size),(.12*size,.13*size,.48*size),clothes,collection,root)
        arm = _mesh(name + ("_LeftArm" if side < 0 else "_RightArm"), "cylinder",
            (.48*side*size,0,1.40*size),(.115*size,.12*size,.43*size),skin,collection,root)
        _walk_limb(leg,frames,side)
        _walk_limb(arm,frames,-side)
    _animate_travel(root,start,end,frames,hop=.025*size)
    return root


def _animal(name, start, end, fur, collection, frames, cat=False):
    size = 0.62 if cat else 0.96
    root = _root(name, collection, start)
    _mesh(name+"_Body","sphere",(0,0,.53*size),(.75*size,.30*size,.34*size),fur,collection,root)
    _mesh(name+"_Head","sphere",(0,-.63*size,.62*size),(.33*size,.35*size,.34*size),fur,collection,root)
    muzzle = _mat("AnimalMuzzle",(.88,.79,.67))
    _mesh(name+"_Muzzle","sphere",(0,-.93*size,.48*size),(.20*size,.17*size,.13*size),muzzle,collection,root)
    for side in (-1,1):
        _mesh(name+("_EarL" if side<0 else "_EarR"),"cone",(.19*side*size,-.68*size,.97*size),
            (.12*size,.12*size,.23*size),fur,collection,root)
        for front in (-1,1):
            leg = _mesh(name+"_Paw"+str(side)+str(front),"cylinder",(
                .45*side*size,.19*front*size,.25*size),
                (.11*size,.10*size,.25*size),fur,collection,root)
            _walk_limb(leg,frames,side*front)
    _mesh(name+"_Tail","cone",(0,.86*size,.73*size),(.10*size,.12*size,.36*size),fur,collection,root)
    _animate_travel(root,start,end,frames,hop=.015)
    return root



def create_lively_project(args):
    """Build a separate, editable building and lively animation in native bpy.

    Never clear the old scene, close other windows, or overwrite a .blend file.
    On failure return to the previous scene and remove only our new scene.
    Persistence requires the separate, owner-approved save_copy command.
    """
    if args:
        raise ValueError("UNEXPECTED_ARGUMENT")
    window = bpy.context.window
    if window is None or window.scene is None:
        raise RuntimeError("BLENDER_WINDOW_UNAVAILABLE")
    previous = window.scene
    if any(s.get("render_fresh_lively_complete", False) for s in bpy.data.scenes):
        raise ValueError("FRESH_LIVELY_PROJECT_ALREADY_EXISTS")

    scene = bpy.data.scenes.new("Lively Building - New Project")
    try:
        window.scene = scene
        building = bpy.data.collections.new(_PREFIX + "NewBuilding")
        scene.collection.children.link(building)
        cream = _mat("FreshFacade", (.80, .74, .63), roughness=.76)
        stone = _mat("FreshStone", (.69, .67, .63), roughness=.81)
        brass = _mat("FreshBrass", (.71, .54, .23), metallic=.65, roughness=.33)
        window_glass = _mat("FreshGlass", (.11, .29, .38), metallic=.24, roughness=.18)
        charcoal = _mat("FreshFrame", (.20, .24, .27), metallic=.45, roughness=.30)
        wood = _mat("FreshDoor", (.32, .19, .11), roughness=.47)

        def part(name, shape, loc, half_size, material):
            ob = _mesh(name, shape, loc, half_size, material, building)
            # Keep the architectural identifiers used by the typed decoration command.
            ob.name = name
            return ob

        # Four-storey architecture. Every object stays independently editable.
        part("MainBuilding", "cube", (0, 2.0, 6.2), (9.0, 5.0, 6.2), cream)
        part("StonePlinth", "cube", (0, 2.0, .15), (9.35, 5.35, .32), stone)
        part("RoofCap", "cube", (0, 2.0, 12.70), (9.60, 5.50, .38), brass)
        part("RoofParapetFront", "cube", (0, -3.31, 13.15), (9.52, .22, .49), stone)
        part("RoofParapetBack", "cube", (0, 7.33, 13.15), (9.52, .22, .49), stone)
        for side, xx in (("L", -9.38), ("R", 9.38)):
            part("RoofParapet" + side, "cube", (xx, 2, 13.15), (.21, 5.40, .49), stone)
        for index, z in enumerate((3.33, 6.49, 9.66), start=1):
            part("FloorBand" + str(index), "cube",
                 (0, -3.16, z), (9.33, .24, .12), brass)
        for floor, z in enumerate((2.14, 5.29, 8.43, 11.54), start=1):
            for column, x in enumerate((-6.65, -3.26, 3.26, 6.65), start=1):
                prefix = "Window" + str(floor) + "_" + str(column)
                part(prefix + "Pane", "cube", (x, -3.16, z),
                     (1.05, .105, .94), window_glass)
                for side, dx in (("L", -1.15), ("R", 1.15)):
                    part(prefix + "Frame" + side, "cube", (x + dx, -3.24, z),
                         (.10, .14, 1.04), charcoal)
                for edge, dz in (("Top", 1.02), ("Base", -1.02)):
                    part(prefix + "Frame" + edge, "cube", (x, -3.24, z + dz),
                         (1.22, .14, .10), charcoal)
                part(prefix + "Mullion", "cube", (x, -3.30, z),
                     (.045, .09, .92), charcoal)

        # Balconies, railings, doorway and architectural details.
        for level, z in enumerate((5.30, 8.45), start=1):
            for side, x in (("L", -5.05), ("R", 5.05)):
                tag = str(level) + side
                part("BalconyDeck" + tag, "cube", (x, -4.22, z-1.22),
                     (1.67, 1.30, .14), stone)
                part("BalconyRail" + tag, "cube", (x, -5.42, z-.63),
                     (1.67, .10, .56), charcoal)
                for dx, end in ((-1.54, "L"), (1.54, "R")):
                    part("BalconyRailPost" + tag + end, "cube",
                         (x + dx, -5.42, z-.64), (.11, .13, .57), brass)
        part("FrontDoor", "cube", (0, -3.22, 1.35), (1.19, .16, 1.35), wood)
        for side, x in (("L", -1.30), ("R", 1.30)):
            part("DoorFrame" + side, "cube", (x, -3.35, 1.48),
                 (.12, .17, 1.52), charcoal)
        part("DoorFrameTop", "cube", (0, -3.35, 2.95), (1.43, .17, .12), charcoal)
        part("DoorHandle", "sphere", (.76, -3.41, 1.27),
             (.09, .09, .16), brass)
        part("EntryCanopy", "cube", (0, -4.34, 3.34), (2.20, 1.56, .18), brass)
        part("FrontStep1", "cube", (0, -4.10, .09), (1.69, 1.00, .18), stone)
        part("FrontStep2", "cube", (0, -5.14, -.10), (1.95, .58, .12), stone)

        environment = populate_lively(scene, {})
        scene["render_fresh_lively_complete"] = True
        return {
            "new_scene": scene.name,
            "new_building_objects": len(building.objects),
            "environment_objects": environment["environment_objects"],
            "walking_people": environment["walking_people"],
            "walking_dogs": environment["walking_dogs"],
            "walking_cats": environment["walking_cats"],
            "duration_seconds": environment["duration_seconds"],
            "fps": environment["fps"],
            "previous_scene_preserved": previous in bpy.data.scenes,
            "previous_scene_name": previous.name,
            "new_scene_needs_save_copy": True,
            "executed_by": "bpy-main-thread-on-android",
        }
    except Exception:
        window.scene = previous
        bpy.data.scenes.remove(scene, do_unlink=True)
        raise


def populate_lively(scene, args):
    if args:
        raise ValueError("UNEXPECTED_ARGUMENT")
    # Never populate the accidental empty Blender tab. Require the saved building.
    if "RoofCap" not in scene.objects or "EntryCanopy" not in scene.objects:
        raise ValueError("BUILDING_MODEL_NOT_LOADED")
    existing = scene.collection.children.get(_PREFIX+"LivelyEnvironment")
    if existing is not None:
        if existing.get("render_populate_complete", False):
            raise ValueError("LIVELY_SCENERY_ALREADY_PRESENT")
        # An interrupted native command may leave half-built scenery behind.
        # Delete ONLY our incomplete collection, never user building objects.
        for incomplete in list(existing.objects):
            if incomplete.name.startswith(_PREFIX):
                bpy.data.objects.remove(incomplete, do_unlink=True)
            else:
                raise RuntimeError("SCENERY_RECOVERY_CONFLICT")
        scene.collection.children.unlink(existing)
        bpy.data.collections.remove(existing)
    collection = bpy.data.collections.new(_PREFIX+"LivelyEnvironment")
    scene.collection.children.link(collection)
    collection["render_populate_complete"] = False

    grass = _mat("GardenGrass",(.22,.43,.16))
    road = _mat("Road",(.22,.23,.26))
    path = _mat("StonePath",(.69,.63,.55))
    leaf = _mat("TreeLeaf",(.12,.40,.19))
    leaf_light = _mat("TreeLeafSunlit",(.25,.55,.25))
    bark = _mat("Bark",(.34,.20,.11))
    flower = _mat("Flowers",(.85,.20,.30))
    cream = _mat("Facade",(.77,.72,.62))
    tinted = _mat("Windows",(.12,.29,.40),metallic=.27,roughness=.20)
    steel = _mat("Trim",(.46,.51,.56),metallic=.6,roughness=.24)
    wood = _mat("Door",(.34,.18,.10),roughness=.35)
    bronze = _mat("Bronze",(.73,.52,.22),metallic=.75,roughness=.3)
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        name=ob.name
        material = cream
        if "Window" in name: material=tinted
        elif name.startswith("FloorBand") or name.startswith("RoofParapet") or name.startswith("BalconyRail"): material=steel
        elif "Door" in name: material=wood
        elif name=="Cube": material=cream
        if "Canopy" in name or "RoofCap" in name: material=bronze
        ob.data.materials.clear()
        ob.data.materials.append(material)

    _mesh("Garden", "cube", (0,0,-.72),(32,27,.18),grass,collection)
    _mesh("Street", "cube", (0,-16,-.49),(35,4,.11),road,collection)
    _mesh("GardenPath", "cube", (0,-9,-.43),(1.8,5.2,.09),path,collection)
    _mesh("SunMarker", "sphere", (-23,20,40),(2.1,2.1,2.1),
        _mat("SunGold",(1.0,.72,.22),roughness=.4),collection)
    _mesh("CloudOne","sphere",(-16,15,29),(5,2,1.2),_mat("CloudWhite",(.91,.94,.95)),collection)
    _mesh("CloudTwo","sphere",(17,17,28),(4,2,1.1),_mat("CloudWhite",(.91,.94,.95)),collection)
    # Small planted trees on both sides of the pedestrian approach.
    for i,(x,y) in enumerate(((-14,-5),(-18,4),(14,-5),(18,4),(-21,-13),(21,-13))):
        _mesh("TreeTrunk"+str(i),"cylinder",(x,y,2.2),(.35,.35,2.25),bark,collection)
        _mesh("TreeCrown"+str(i),"sphere",(x,y,5.45),(2.05,1.9,2.3),
              leaf if i%2 else leaf_light,collection)
        for j in range(3):
            _mesh("Flower"+str(i)+"_"+str(j),"sphere",(x-1.0+j,y-1.1,.08),
                  (.16,.16,.22),flower,collection)
    # Moving pedestrians and friendly animals, authored as independently editable parts.
    _person("AdultA",(-8,-10,.0),(-1,-6,.0),_mat("CoatBlue",(.12,.28,.58)),
            _mat("SkinWarm",(.67,.40,.25)),collection,(1,192))
    _person("AdultB",(9,-10,.0),(2,-6,.0),_mat("CoatCoral",(.68,.26,.20)),
            _mat("SkinLight",(.86,.67,.52)),collection,(1,192))
    _person("Child",(-12,-12,.0),(-5,-8,.0),_mat("CoatYellow",(.91,.67,.12)),
            _mat("SkinWarm",(.67,.40,.25)),collection,(18,192),child=True)
    _animal("Dog", (7,-12,.0),(-1,-10,.0),_mat("DogBrown",(.48,.27,.12)),
            collection,(1,192),cat=False)
    _animal("Cat", (-14,-4,.0),(-10,-7,.0),_mat("CatGray",(.50,.50,.53)),
            collection,(24,192),cat=True)

    # Actual daylight and sky, not a flat coloured backdrop.
    world=scene.world or bpy.data.worlds.new(_PREFIX+"SunnyWorld")
    scene.world=world
    world.use_nodes=True
    nodes=world.node_tree.nodes
    background=nodes.get("Background")
    if background:
        background.inputs["Color"].default_value=(.29,.61,.92,1)
        background.inputs["Strength"].default_value=.8
    sun=bpy.data.lights.new(_PREFIX+"Sunlight","SUN")
    sun.energy=2.4
    sunlight=bpy.data.objects.new(_PREFIX+"Sunlight",sun)
    collection.objects.link(sunlight)
    sunlight.rotation_euler=(.45,-.55,-.6)

    camera=scene.camera
    if camera is None or camera.type!="CAMERA":
        cam_data=bpy.data.cameras.new(_PREFIX+"Camera")
        camera=bpy.data.objects.new(_PREFIX+"Camera",cam_data)
        collection.objects.link(camera)
        scene.camera=camera
    for frame, location in ((1,(24,-37,20)),(96,(18,-34,18)),(192,(13,-31,16))):
        camera.location=location
        camera.rotation_euler=(Vector((0,0,8))-camera.location).to_track_quat("-Z","Y").to_euler()
        camera.keyframe_insert(data_path="location",frame=frame)
        camera.keyframe_insert(data_path="rotation_euler",frame=frame)
    scene.frame_start=1
    scene.frame_end=192
    scene.render.fps=24
    # 720p frames at 24 fps: a cinematic target without assuming desktop GPU.
    scene.render.resolution_x=1280
    scene.render.resolution_y=720
    scene.render.resolution_percentage=100
    scene.frame_set(1)
    collection["render_populate_complete"] = True
    return {
        "environment_objects": len(collection.objects),
        "walking_people": 3,
        "walking_dogs": 1,
        "walking_cats": 1,
        "sky": "daylight-blue",
        "sunlight": True,
        "animated_frames": 192,
        "fps": 24,
        "duration_seconds": 8,
        "engine": scene.render.engine,
        "executed_by": "bpy-main-thread-on-android",
        "note": "Playable animation timeline, saved only by explicit save_copy action",
    }


def render_video(scene, args, uid, spool):
    """Render native MP4 in app-owned Renders; no cloud process or upload."""
    if args:
        raise ValueError("UNEXPECTED_ARGUMENT")
    completed = scene.collection.children.get(_PREFIX+"LivelyEnvironment")
    if completed is None or not completed.get("render_populate_complete", False):
        raise ValueError("SCENERY_NOT_READY")
    if not spool or not re.fullmatch(r"[a-f0-9]{32}",str(uid)):
        raise ValueError("INVALID_RENDER_JOB_ID")
    if not getattr(bpy.app.build_options,"ffmpeg",False):
        raise RuntimeError("NATIVE_FFMPEG_NOT_BUILT")
    if scene.frame_end-scene.frame_start+1 > 240:
        raise ValueError("ANIMATION_FRAME_LIMIT")
    output_dir=Path(spool).resolve().parent/"Renders"
    output_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    prefix=output_dir/("RenderVideo_"+uid)
    if any(output_dir.glob(prefix.name+"*")):
        raise ValueError("RENDER_OUTPUT_ALREADY_EXISTS")
    render=scene.render
    old=(render.filepath,render.image_settings.file_format,
         render.resolution_percentage,render.engine)
    try:
        render.engine="BLENDER_EEVEE"
        render.filepath=str(prefix)
        render.resolution_percentage=100
        render.image_settings.file_format="FFMPEG"
        render.ffmpeg.format="MPEG4"
        render.ffmpeg.codec="H264"
        render.ffmpeg.constant_rate_factor="MEDIUM"
        result=bpy.ops.render.render(animation=True)
        if "FINISHED" not in result:
            raise RuntimeError("BLENDER_VIDEO_RENDER_FAILED")
    finally:
        render.filepath,render.image_settings.file_format,render.resolution_percentage,render.engine=old
    files=[f for f in output_dir.glob(prefix.name+"*") if f.is_file() and f.suffix.lower()==".mp4"]
    if len(files)!=1 or files[0].stat().st_size<1000:
        raise RuntimeError("NATIVE_MP4_NOT_PRODUCED")
    file=files[0]
    digest=hashlib.sha256()
    with file.open("rb") as stream:
        for part in iter(lambda:stream.read(1048576),b""):
            digest.update(part)
    return {
        "filename":file.name, "mime_type":"video/mp4",
        "bytes":file.stat().st_size,"sha256":digest.hexdigest(),
        "frames":scene.frame_end-scene.frame_start+1,
        "fps":scene.render.fps,
        "rendered_on":"android-native-blender",
        "executed_by":"bpy-main-thread-on-android",
        "note":"MP4 stored in Render private Renders folder; not automatically shared to ChatGPT",
    }
