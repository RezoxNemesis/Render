# SPDX-License-Identifier: GPL-2.0-or-later
"""Free procedural starter assets for the native Render Studio Blender editor.

Generated in bpy as editable meshes and collections. No downloaded models,
copyrighted third-party textures, or paid catalog dependencies are bundled.
The generators provide starting geometry, not film-quality prebuilt characters.
"""
import math
import re
import uuid

import bpy

PRESETS = (
    ("COLUMN", "Classical Column"),
    ("ARCH", "Curved Stone Arch"),
    ("STAIRS", "Architectural Staircase"),
    ("WALL", "Stone Wall / Panels"),
    ("WINDOW", "Window Frame"),
    ("ROOF", "Tiled Sloping Roof"),
    ("TREE", "Leafy Tree"),
    ("SHRUB", "Flowering Shrub"),
    ("ROCK", "Organic Boulder"),
    ("GRASS", "Grass Tufts"),
    ("BENCH", "Wooden Bench"),
    ("LAMP", "Park Lamp + Real Light"),
    ("WATER", "Reflective Water Plane"),
    ("TERRAIN", "Undulating Terrain"),
    ("HUMANOID", "Human Rig Proxy"),
    ("QUADRUPED", "Four-legged Rig Proxy"),
    ("STUDIO", "Camera + Area Lights"),
)
_IDS = {key for key, _ in PRESETS}
_INSTALLED = False

def _material(name, rgb, rough=0.68, metal=0.0):
    mat = bpy.data.materials.new("RS_" + name)
    mat.diffuse_color = (*rgb, 1.0)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    if shader:
        shader.inputs["Base Color"].default_value = (*rgb, 1.0)
        shader.inputs["Roughness"].default_value = rough
        shader.inputs["Metallic"].default_value = metal
    return mat

def _mesh(collection, label, vertices, faces, material, smooth=False, bevel=0):
    mesh = bpy.data.meshes.new(label + "_Topology")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(label, mesh)
    collection.objects.link(ob)
    if material is not None:
        ob.data.materials.append(material)
    for face in mesh.polygons:
        face.use_smooth = smooth and len(face.vertices) == 4
    if bevel:
        modifier = ob.modifiers.new("PhysicalEdgeBevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        try:
            ob.modifiers.new("WeightedSurfaceNormals", "WEIGHTED_NORMAL")
        except RuntimeError:
            pass
    return ob

def _box(group, name, center, size, mat, bevel=0.015):
    x, y, z = center
    w, d, h = (q / 2 for q in size)
    v = [(x+a*w, y+b*d, z+c*h) for a,b,c in (
        (-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
        (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
    f = [(0,3,2,1),(4,5,6,7),(0,1,5,4),
         (1,2,6,5),(2,3,7,6),(3,0,4,7)]
    return _mesh(group,name,v,f,mat,bevel=bevel)

def _lathe(group, name, center, radius, height, mat, rings=12, segments=32,
           top_radius=None, taper=False):
    cx,cy,cz=center
    if top_radius is None:top_radius=radius
    verts=[]
    for j in range(rings+1):
        k=j/rings
        r=radius+(top_radius-radius)*k
        if taper:r*=0.9+0.1*math.sin(math.pi*k)
        z=cz+height*(k-0.5)
        for i in range(segments):
            angle=i*2*math.pi/segments
            verts.append((cx+r*math.cos(angle),cy+r*math.sin(angle),z))
    faces=[]
    for j in range(rings):
        for i in range(segments):
            q=j*segments+i;n=j*segments+(i+1)%segments
            faces.append((q,n,n+segments,q+segments))
    faces.extend((tuple(reversed(range(segments))),
                  tuple(rings*segments+i for i in range(segments))))
    return _mesh(group,name,verts,faces,mat,smooth=True)

def _ellipsoid(group, name, center, radii, mat, noisy=False):
    cx,cy,cz=center
    segments,rings=24,12
    vertices=[]
    for j in range(1,rings):
        latitude=math.pi*j/rings
        for i in range(segments):
            longitude=2*math.pi*i/segments
            factor=(1+0.07*math.sin(7*longitude+3*latitude)+
                       0.06*math.cos(5*latitude+2*longitude)) if noisy else 1.0
            vertices.append((cx+radii[0]*factor*math.sin(latitude)*math.cos(longitude),
                             cy+radii[1]*factor*math.sin(latitude)*math.sin(longitude),
                             cz+radii[2]*factor*math.cos(latitude)))
    north=len(vertices);vertices.append((cx,cy,cz+radii[2]))
    south=len(vertices);vertices.append((cx,cy,cz-radii[2]))
    faces=[]
    for i in range(segments):
        nxt=(i+1)%segments
        faces.append((north,i,nxt))
        for j in range(rings-2):
            a=j*segments+i;b=j*segments+nxt
            faces.append((a,a+segments,b+segments,b))
        end=(rings-2)*segments
        faces.append((end+i,south,end+nxt))
    return _mesh(group,name,vertices,faces,mat,smooth=True)

def _arch(group, stone):
    segments=32;inner=1.20;outer=1.65;width=0.45
    vertices=[]
    for j in range(segments+1):
        theta=math.pi*j/segments
        for r in (inner,outer):
            for side in (-width/2,width/2):
                vertices.append((r*math.cos(theta),side,2.3+r*math.sin(theta)))
    faces=[]
    for j in range(segments):
        a=j*4;b=a+4
        faces.extend(((a,b,b+1,a+1),(a+2,a+3,b+3,b+2),
                      (a,a+2,b+2,b),(a+1,b+1,b+3,a+3)))
    faces.extend(((0,1,3,2),(segments*4,segments*4+2,segments*4+3,segments*4+1)))
    _mesh(group,"TrueCurvedArch",vertices,faces,stone,bevel=0.01)
    for sign in (-1,1):
        _box(group,"ArchPillar",(sign*1.48,0,1.15),(.45,.52,2.3),stone,0.04)

def _rig(group, kind, material, dark):
    # Real Blender armature + editable individual anatomy pieces. This is a
    # starter control rig, NOT a weighted/deforming production character.
    ob=bpy.data.objects.new("Editable_"+kind+"_Skeleton",
                            bpy.data.armatures.new("RS_"+kind+"_Bones"))
    group.objects.link(ob)
    current=bpy.context.view_layer.objects.active
    old_selected=[o for o in bpy.context.selected_objects]
    try:
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active=ob
        bpy.ops.object.mode_set(mode="EDIT")
        bones=ob.data.edit_bones
        if kind=="Human":
            bonespec=[
                ("Root",None,(0,0,0.1),(0,0,1.0)),
                ("Spine","Root",(0,0,1.0),(0,0,1.75)),
                ("Neck","Spine",(0,0,1.75),(0,0,2.1)),
                ("Head","Neck",(0,0,2.1),(0,0,2.5)),
                ("LeftUpperArm","Spine",(-.20,0,1.75),(-.70,0,1.35)),
                ("LeftForearm","LeftUpperArm",(-.70,0,1.35),(-.90,0,.95)),
                ("RightUpperArm","Spine",(.20,0,1.75),(.70,0,1.35)),
                ("RightForearm","RightUpperArm",(.70,0,1.35),(.90,0,.95)),
                ("LeftThigh","Root",(-.14,0,1.0),(-.17,0,.52)),
                ("LeftShin","LeftThigh",(-.17,0,.52),(-.17,0,.10)),
                ("RightThigh","Root",(.14,0,1.0),(.17,0,.52)),
                ("RightShin","RightThigh",(.17,0,.52),(.17,0,.10))]
        else:
            bonespec=[("Root",None,(0,0,.8),(0,0,1.15)),
                ("Spine","Root",(0,0,1.1),(0,.6,1.1)),
                ("Neck","Spine",(0,.6,1.1),(0,.95,1.15)),
                ("Head","Neck",(0,.95,1.15),(0,1.25,1.1))]
            for side in (-1,1):
                for fore in (-1,1):
                    label=("Left" if side==-1 else "Right")+("Front" if fore==1 else "Back")
                    pos=.42*side;long=.55*fore
                    bonespec.append((label+"Upper","Root",(pos,long,1.05),(pos,long,.50)))
                    bonespec.append((label+"Lower",label+"Upper",(pos,long,.50),(pos,long,.10)))
        for name,parent,head,tail in bonespec:
            bone=bones.new(name)
            bone.head=head;bone.tail=tail
            if parent is not None:bone.parent=bones[parent]
        bpy.ops.object.mode_set(mode="OBJECT")
    finally:
        if ob.mode!="OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        for selected in old_selected:
            if selected.name in bpy.data.objects:
                selected.select_set(True)
        bpy.context.view_layer.objects.active=current
    if kind=="Human":
        parts=[("Torso",(0,0,1.48),(.32,.23,.51),"Spine"),
               ("Face",(0,0,2.20),(.20,.19,.26),"Head"),
               ("LeftArm",(-.50,0,1.35),(.12,.12,.40),"LeftUpperArm"),
               ("RightArm",(.50,0,1.35),(.12,.12,.40),"RightUpperArm"),
               ("LeftLeg",(-.17,0,.53),(.14,.14,.50),"LeftThigh"),
               ("RightLeg",(.17,0,.53),(.14,.14,.50),"RightThigh")]
    else:
        parts=[("Torso",(0,0,1.02),(.4,.78,.38),"Spine"),
               ("Head",(0,1.06,1.20),(.28,.27,.26),"Head")]
        for side in (-1,1):
            for fore in (-1,1):
                label=("Left" if side==-1 else "Right")+("Front" if fore==1 else "Back")
                parts.append((label+"Leg",(.37*side,.55*fore,.5),(.15,.14,.47),label+"Upper"))
    for name,center,radii,bone in parts:
        part=_ellipsoid(group,name,center,radii,material if name!="Face" else dark)
        part.parent=ob;part.parent_type="BONE";part.parent_bone=bone
        # Fixed world shape when binding; bone-relative local transform.
        part.matrix_parent_inverse=ob.matrix_world.inverted()
    return ob

def create_asset(scene, preset, name=None):
    if preset not in _IDS:
        raise ValueError("UNKNOWN_FREE_ASSET_PRESET")
    if name is not None and (not isinstance(name,str) or
                             not re.fullmatch("[A-Za-z][A-Za-z0-9_-]{0,63}",name)):
        raise ValueError("INVALID_ASSET_NAME")
    title=name or preset.title()
    suffix=uuid.uuid4().hex[:6]
    collection=bpy.data.collections.new("RS_"+title+"_"+suffix)
    scene.collection.children.link(collection)
    collection["source"]="Render Studio built-in procedural generator"
    collection["commercial_asset_dependency"]=False
    collection["editable_geometry"]=True
    try:
        stone=_material("Stone",(.46,.48,.5))
        dark=_material("DarkMetal",(.1,.12,.15),.22,.65)
        wood=_material("Wood",(.38,.22,.12))
        leaf=_material("Leaf",(.15,.36,.13))
        earth=_material("Earth",(.29,.23,.17))
        water=_material("Water",(.07,.31,.44),.12,.05)
        bright=_material("Bright",(.82,.69,.40),.25,.18)
        if preset=="COLUMN":
            _lathe(collection,"FlutedShaft",(0,0,1.55),.28,2.6,stone,top_radius=.24)
            _box(collection,"ColumnBase",(0,0,.16),(.88,.88,.32),stone,.04)
            _box(collection,"ColumnCapital",(0,0,2.96),(1.05,1.05,.29),stone,.035)
        elif preset=="ARCH":
            _arch(collection,stone)
        elif preset=="STAIRS":
            for i in range(9):
                _box(collection,"Stair_%02d"%i,(0,.21*i,.12+.14*i),
                     (2.6,2.2-.21*i,.24),stone,.02)
        elif preset=="WALL":
            _box(collection,"StoneWall",(0,0,1.25),(3,.36,2.5),stone,.04)
            for j in range(4):
                for i in range(6):
                    _box(collection,"WallPanel",(i*.50-1.25,-.198,j*.55+.3),
                         (.48,.028,.52),stone,.02)
        elif preset=="WINDOW":
            _box(collection,"WindowLeft",(-.85,0,1.2),(.16,.2,2.4),wood)
            _box(collection,"WindowRight",(.85,0,1.2),(.16,.2,2.4),wood)
            _box(collection,"WindowTop",(0,0,2.35),(1.8,.2,.2),wood)
            _box(collection,"WindowBottom",(0,0,.1),(1.8,.2,.2),wood)
            _box(collection,"WindowMullion",(0,0,1.2),(.08,.20,2.25),wood)
        elif preset=="ROOF":
            verts=[(-2,-1,1),(2,-1,1),(0,-1,2.25),
                   (-2,1,1),(2,1,1),(0,1,2.25)]
            _mesh(collection,"ActualRoofSlope",verts,[(0,1,2),(3,5,4),(0,3,4,1),(0,2,5,3),(2,1,4,5)],stone)
            for i in range(12):
                _box(collection,"RidgeTiles",(0,-.92+i*.17,2.26),
                     (.24,.16,.085),earth,.02)
        elif preset=="TREE":
            _lathe(collection,"TreeTrunk",(0,0,1.4),.28,2.8,wood,top_radius=.14)
            for center,radii in [((0,0,3.0),(1.0,1.0,1.2)),
                                 ((-.65,0,2.6),(.7,.7,.85)),
                                 ((.60,.1,2.8),(.75,.85,.82))]:
                _ellipsoid(collection,"Foliage",center,radii,leaf)
        elif preset=="SHRUB":
            for i in range(11):
                angle=i*2.399
                _ellipsoid(collection,"ShrubLayer",(.40*math.cos(angle),.4*math.sin(angle),.45+(i%3)*.12),
                           (.42,.38,.45),leaf)
            for i in range(7):
                angle=i*2*math.pi/7
                _ellipsoid(collection,"Bloom",(.55*math.cos(angle),.55*math.sin(angle),.75),
                           (.075,.075,.075),bright)
        elif preset=="ROCK":
            _ellipsoid(collection,"ShapedRock",(0,0,.65),(1.35,.85,.8),stone,noisy=True)
        elif preset=="GRASS":
            for i in range(24):
                angle=i*2.399;radius=.1+.85*math.sqrt((i+1)/24)
                _lathe(collection,"GrassBlade",(radius*math.cos(angle),radius*math.sin(angle),.25),
                       .024,.45,leaf,rings=2,segments=6,top_radius=.001)
        elif preset=="BENCH":
            _box(collection,"BenchSeat",(0,0,.65),(2,.7,.14),wood,.04)
            _box(collection,"BackSupport",(0,.32,1.13),(2,.12,.85),wood,.03)
            for x in (-.80,.80):
                _box(collection,"BenchLeg",(x,0,.33),(.13,.56,.62),dark,.02)
        elif preset=="LAMP":
            _lathe(collection,"LampPole",(0,0,1.75),.08,3.5,dark,top_radius=.06)
            _ellipsoid(collection,"LampGlobe",(0,0,3.63),(.27,.27,.3),bright)
            light=bpy.data.lights.new("NativeLamp","POINT")
            light.energy=500
            ob=bpy.data.objects.new("ActualPointLight",light)
            collection.objects.link(ob);ob.location=(0,0,3.55)
        elif preset=="WATER":
            _box(collection,"WaterSurface",(0,0,0),(5,5,.06),water,.01)
            # Editable reflective surface; not an unsupported realtime fluid sim.
        elif preset=="TERRAIN":
            verts=[];faces=[];n=24
            for y in range(n+1):
                for x in range(n+1):
                    px=(x/n-.5)*8;py=(y/n-.5)*8
                    z=.22*math.sin(px*1.15)*math.cos(py*.9)+.06*math.sin(px*4+py)
                    verts.append((px,py,z))
            for y in range(n):
                for x in range(n):
                    a=y*(n+1)+x
                    faces.append((a,a+1,a+n+2,a+n+1))
            _mesh(collection,"EditableTerrain",verts,faces,earth,smooth=True)
        elif preset in ("HUMANOID","QUADRUPED"):
            _rig(collection,"Human" if preset=="HUMANOID" else "Quadruped",stone,dark)
        elif preset=="STUDIO":
            camera=bpy.data.cameras.new("RS_Camera")
            ob=bpy.data.objects.new("AssetCamera",camera)
            collection.objects.link(ob);ob.location=(5,-7,4)
            direction=__import__("mathutils").Vector((0,0,1))-ob.location
            ob.rotation_euler=direction.to_track_quat("-Z","Y").to_euler()
            scene.camera=ob
            for idx,(loc,energy) in enumerate([((-3,-4,6),900),((4,2,5),550)]):
                lamp=bpy.data.lights.new("RS_AreaLight","AREA")
                lamp.energy=energy;lamp.shape="DISK";lamp.size=4.0
                obj=bpy.data.objects.new("AreaLight"+str(idx),lamp)
                collection.objects.link(obj);obj.location=loc
                obj.rotation_euler=(-obj.location).to_track_quat("-Z","Y").to_euler()
        return {"preset":preset,"collection":collection.name,
                "objects":len(collection.objects),"editable":True,
                "external_assets_downloaded":0,"source":"built-in procedural",
                "rig_deformation_verified":False}
    except Exception:
        bpy.data.collections.remove(collection,do_unlink=True)
        raise

class RENDERSTUDIO_OT_free_asset(bpy.types.Operator):
    bl_idname="renderstudio.add_free_asset"
    bl_label="Add Free Procedural Asset"
    bl_options={"REGISTER","UNDO"}
    bl_description="Generate editable native Blender geometry, not a static low-res picture"
    preset: bpy.props.EnumProperty(items=[(key,title,title) for key,title in PRESETS])
    def execute(self, context):
        try:
            result=create_asset(context.scene,self.preset)
            self.report({"INFO"}, "Added "+result["collection"])
            return {"FINISHED"}
        except Exception as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

class RENDERSTUDIO_MT_free_assets(bpy.types.Menu):
    bl_idname="RENDERSTUDIO_MT_free_assets"
    bl_label="Render Studio / Free Assets"
    def draw(self, context):
        layout=self.layout
        for preset,label in PRESETS:
            item=layout.operator("renderstudio.add_free_asset",text=label)
            item.preset=preset

def _add_menu(self, context):
    self.layout.separator()
    self.layout.menu("RENDERSTUDIO_MT_free_assets",text="Render Studio Free Assets")

def install():
    global _INSTALLED
    if _INSTALLED or getattr(bpy.app,"background",False):
        return
    bpy.utils.register_class(RENDERSTUDIO_OT_free_asset)
    bpy.utils.register_class(RENDERSTUDIO_MT_free_assets)
    bpy.types.VIEW3D_MT_add.append(_add_menu)
    _INSTALLED=True
