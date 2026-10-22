# SPDX-License-Identifier: GPL-2.0-or-later
"""Phase 08: bounded, deterministic, *native bpy* railway/temple world authoring.

Never alters render settings, reads private media, downloads models or executes a
client-supplied Blender operator. Importable without bpy; execute requires bpy.
Integration/registration is exclusively owned by OMEGA Phase 10.
"""
import hashlib
import json
import math
import random
import re

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.world.build_scene", "omega.world.audit")
_WORLD_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
_GENERATOR = "Render Studio Phase 08 first-party procedural geometry"
_LICENSE = "GPL-2.0-or-later"


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def validate(operation, payload):
    """Pure allowlist/schema validation, with no bpy import or scene side effects."""
    if operation not in OPERATION_NAMES:
        raise ValueError("UNSUPPORTED_OPERATION")
    if type(payload) is not dict:
        raise ValueError("INVALID_ARGUMENTS")
    allowed = ({"name", "seed", "trees", "grass", "layout"}
               if operation == OPERATION_NAMES[0] else {"name"})
    if set(payload) - allowed:
        raise ValueError("UNKNOWN_WORLD_ARGUMENT")
    name = payload.get("name", "RailwayTemple")
    if type(name) is not str or not _WORLD_ID.fullmatch(name):
        raise ValueError("INVALID_WORLD_NAME")
    if operation == OPERATION_NAMES[1]:
        return {"name": name}
    seed = payload.get("seed", 8)
    trees = payload.get("trees", 18)
    grass = payload.get("grass", 48)
    layout = payload.get("layout", "RAILWAY_TEMPLE")
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError("INVALID_SCATTER_SEED")
    if type(trees) is not int or not 0 <= trees <= 48:
        raise ValueError("INVALID_TREE_COUNT")
    if type(grass) is not int or not 0 <= grass <= 96:
        raise ValueError("INVALID_GRASS_COUNT")
    if layout != "RAILWAY_TEMPLE":
        raise ValueError("UNSUPPORTED_WORLD_LAYOUT")
    return {"name": name, "seed": seed, "trees": trees,
            "grass": grass, "layout": layout}


def _height(x, y):
    return (0.09 * math.sin(x * 0.38) * math.cos(y * 0.41)
            + 0.045 * math.sin(y * 0.83 + x * 0.27))


def _scatters(spec):
    """Stable deterministic XY placements; keep temple, track and steps clear."""
    rng = random.Random(spec["seed"])
    coords = []
    for kind, count in (("tree", spec["trees"]), ("grass", spec["grass"])):
        items = []
        attempts = 0
        while len(items) < count and attempts < 12000:
            attempts += 1
            x, y = rng.uniform(-13.4, 13.4), rng.uniform(-13.4, 13.4)
            if -7.9 < x < -3.4:  # no plants through the railway
                continue
            if -1.2 < x < 9.5 and -1.7 < y < 9.2:  # temple footprint
                continue
            if kind == "tree" and any((x-a)**2 + (y-b)**2 < 5.0 for a,b,_ in items):
                continue
            items.append((round(x, 5), round(y, 5), round(rng.uniform(.82, 1.23), 5)))
        if len(items) != count:
            raise ValueError("SCATTER_BUDGET_UNSATISFIABLE")
        coords.append((kind, items))
    return coords


def plan(payload):
    """Pure bounded cost/placement preview; a budget is NOT a memory guarantee."""
    p = validate(OPERATION_NAMES[0], payload)
    return {"spec": p, "fingerprint": _fingerprint(p),
            "scatter": _scatters(p), "maximum_objects": 130 + 2*p["trees"] + p["grass"],
            "estimated_vertices_upper": 11000 + 200*p["trees"] + 60*p["grass"]}


def _require_bpy():
    try:
        import bpy
        from mathutils import Vector
    except ImportError as exc:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE: bpy unavailable") from exc
    return bpy, Vector


def _context(context):
    if type(context) is not dict or context.get("scene") is None:
        raise ValueError("NATIVE_SCENE_REQUIRED")
    if context.get("cancellation_requested") is True:
        raise RuntimeError("CANCELLED")
    return context["scene"]


def _cancel(context):
    flag = context.get("cancellation_requested", False)
    if flag() if callable(flag) else flag:
        raise RuntimeError("CANCELLED")


def _box_data():
    return ([(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),
             (-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)],
            [(0,3,2,1),(4,5,6,7),(0,1,5,4),
             (1,2,6,5),(2,3,7,6),(3,0,4,7)])


def _shaft_data():
    vertices, faces = [], []
    segments = 20
    for z, radius in ((0,.34),(.08,.34),(.11,.25),(.88,.22),(.94,.31),(1,.36)):
        for i in range(segments):
            a = math.tau * i / segments
            vertices.append((radius*math.cos(a), radius*math.sin(a), z))
    for r in range(5):
        for i in range(segments):
            a=r*segments+i; b=r*segments+(i+1)%segments
            faces.append((a,b,b+segments,a+segments))
    faces.append(tuple(reversed(range(segments))))
    faces.append(tuple(5*segments+i for i in range(segments)))
    return vertices, faces


def _arch_data():
    vertices, faces = [], []
    for j in range(25):
        a = math.pi*j/24
        for r in (1.18,1.53):
            for y in (-.22,.22):
                vertices.append((r*math.cos(a),y,1.88+r*math.sin(a)))
    for j in range(24):
        a = j*4; b = a+4
        faces.extend(((a,b,b+1,a+1),(a+2,a+3,b+3,b+2),
                      (a,a+2,b+2,b),(a+1,b+1,b+3,a+3)))
    faces.extend(((0,1,3,2),(96,98,99,97)))
    return vertices, faces


def _canopy_data():
    # A low-poly connected ellipsoid. Native topology, not image billboards.
    vs = []; fs = []; segments = 12
    for j in range(1,9):
        lat=math.pi*j/9
        for i in range(segments):
            a=math.tau*i/segments
            vs.append((math.sin(lat)*math.cos(a),math.sin(lat)*math.sin(a),
                       math.cos(lat)))
    north=len(vs);vs.append((0,0,1))
    south=len(vs);vs.append((0,0,-1))
    for i in range(segments):
        nxt=(i+1)%segments
        fs.append((north,i,nxt))
        for j in range(7):
            a=j*segments+i; b=j*segments+nxt
            fs.append((a,a+segments,b+segments,b))
        fs.append((7*segments+i,south,7*segments+nxt))
    return vs,fs


def _grass_data():
    vs=[(-.05,0,0),(.05,0,0),(0,0,.65),
        (0,-.05,0),(0,.05,0),(0,0,.58),
        (-.04,-.04,0),(.04,.04,0),(0,0,.75)]
    return vs,[(0,1,2),(3,4,5),(6,7,8)]


def _terrain_data():
    n=40; v=[]; f=[]
    for j in range(n+1):
        for i in range(n+1):
            x=(i/n-.5)*30; y=(j/n-.5)*30
            v.append((x,y,_height(x,y)))
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i
            f.append((a,a+1,a+n+2,a+n+1))
    return v,f


def _roof_data():
    return ([(-.5,-.5,0),(.5,-.5,0),(0,-.5,.85),
             (-.5,.5,0),(.5,.5,0),(0,.5,.85)],
            [(0,1,2),(3,5,4),(0,3,4,1),(0,2,5,3),(2,1,4,5)])


def _audit_objects(collection):
    # Float quantization tolerates native Blender float32 save/reopen.
    parts=[]
    for ob in sorted(collection.objects, key=lambda o:o.name):
        mat=tuple(m.name for m in ob.data.materials) if ob.type=="MESH" else ()
        parts.append([ob.name,ob.type,ob.data.name,
                      [round(float(x),4) for x in ob.location],
                      [round(float(x),4) for x in ob.rotation_euler],
                      [round(float(x),4) for x in ob.scale],
                      len(ob.data.vertices) if ob.type=="MESH" else 0,
                      len(ob.data.polygons) if ob.type=="MESH" else 0,mat])
    return _fingerprint(parts)


def _collect(scene, name):
    return scene.collection.children.get("P08_"+name)


def audit(operation, payload, context):
    """Read-only native scene audit; verifies persisted native datablocks."""
    args=validate(OPERATION_NAMES[1],payload)
    if operation != OPERATION_NAMES[1]:
        raise ValueError("UNSUPPORTED_OPERATION")
    _require_bpy()
    scene=_context(context)
    group=_collect(scene,args["name"])
    if group is None:
        raise ValueError("WORLD_NOT_FOUND")
    objects=list(group.objects)
    meshes=[o for o in objects if o.type=="MESH"]
    digest=_audit_objects(group)
    unique_meshes={o.data.as_pointer():o.data for o in meshes}
    counts={"objects":len(objects), "meshes":len(meshes),
            "unique_mesh_datablocks":len(unique_meshes),
            "mesh_instances":len(meshes)-len(unique_meshes),
            "vertices_in_datablocks":sum(len(m.vertices) for m in unique_meshes.values()),
            "native_lights":sum(o.type=="LIGHT" for o in objects),
            "native_cameras":sum(o.type=="CAMERA" for o in objects)}
    ok=(group.get("p08_state")=="READY" and digest==group.get("p08_digest")
        and len(objects)==group.get("p08_object_count")
        and scene.camera in objects and scene.world is not None
        and group.get("p08_license")==_LICENSE)
    return {"operation":OPERATION_NAMES[1],"state":"succeeded",
            "scene":scene.name,"world":group.name,"complete":bool(ok),
            "source_revision":digest,"expected_revision":group.get("p08_digest"),
            "spec_fingerprint":group.get("p08_spec_hash"),"counts":counts,
            "camera":scene.camera.name if scene.camera else None,
            "world_shader":scene.world.name if scene.world else None,
            "provenance":group.get("p08_source"),"license":group.get("p08_license"),
            "external_assets_downloaded":0,"preview_proxy_count":0,
            "quality_reduced":False,"native_execution_verified":True,
            "visual_quality_verified":False}


def execute(operation, payload, context):
    if operation == OPERATION_NAMES[1]:
        return audit(operation,payload,context)
    args=validate(operation,payload)
    if operation != OPERATION_NAMES[0]:
        raise ValueError("UNSUPPORTED_OPERATION")
    bpy,Vector=_require_bpy()
    scene=_context(context)
    p=plan(args)
    if context.get("dry_run") is True:
        return {"operation":operation,"state":"planned","scene":scene.name,
                "native_execution_verified":False,"quality_reduced":False,
                "planned_objects_upper":p["maximum_objects"],
                "estimated_vertices_upper":p["estimated_vertices_upper"],
                "warnings":["A pure plan does not create any Blender objects"]}
    bytes_free=context.get("available_memory_bytes")
    estimate=16*1024*1024 + p["maximum_objects"]*8192 + p["estimated_vertices_upper"]*128
    if bytes_free is not None and (type(bytes_free) is not int or bytes_free < estimate):
        raise RuntimeError("OUT_OF_MEMORY_PAUSED")
    existing=_collect(scene,args["name"])
    if existing:
        if existing.get("p08_spec_hash") != p["fingerprint"]:
            raise ValueError("CHECKPOINT_CONFLICT")
        previous=audit(OPERATION_NAMES[1],{"name":args["name"]},context)
        if not previous["complete"]:
            raise ValueError("CHECKPOINT_CONFLICT")
        return {"operation":operation,"state":"succeeded","scene":scene.name,
                "source_revision":previous["source_revision"],"created":[],
                "already_complete":True,"artifact":{"kind":"none","sha256":None},
                "native_execution_verified":True,"visual_quality_verified":False,
                "quality_reduced":False,"warnings":[]}

    old_camera,old_world=scene.camera,scene.world
    group=None;made_objects=[];made_meshes=[];made_materials=[];made_lights=[];made_cameras=[]
    new_world=None
    stem="P08_"+args["name"]
    try:
        group=bpy.data.collections.new(stem)
        scene.collection.children.link(group)
        group["p08_state"]="BUILDING"
        group["p08_spec_hash"]=p["fingerprint"]
        group["p08_source"]=_GENERATOR
        group["p08_license"]=_LICENSE
        group["p08_external_assets"]=0
        group["p08_seed"]=args["seed"]
        materials={}
        def material(label, rgb, roughness):
            m=bpy.data.materials.new(stem+"_"+label)
            made_materials.append(m)
            m.diffuse_color=(*rgb,1.0)
            m.use_nodes=True
            bsdf=m.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value=(*rgb,1.0)
                bsdf.inputs["Roughness"].default_value=roughness
            m["p08_source"]=_GENERATOR;m["p08_license"]=_LICENSE
            materials[label]=m
        material("Soil",(.27,.30,.19),.91)
        material("Stone",(.57,.53,.44),.78)
        material("Rail",(.18,.21,.23),.31)
        material("Wood",(.27,.16,.09),.82)
        material("Leaf",(.15,.34,.13),.86)
        material("Grass",(.27,.42,.13),.91)
        templates={}
        for label,geom,material_label in (
            ("SoilMesh",_terrain_data(),"Soil"),
            ("StoneBox",_box_data(),"Stone"),
            ("RailBox",_box_data(),"Rail"),
            ("WoodBox",_box_data(),"Wood"),
            ("Shaft",_shaft_data(),"Stone"),
            ("Arch",_arch_data(),"Stone"),
            ("Roof",_roof_data(),"Stone"),
            ("Trunk",_shaft_data(),"Wood"),
            ("Crown",_canopy_data(),"Leaf"),
            ("GrassBlade",_grass_data(),"Grass")):
            mesh=bpy.data.meshes.new(stem+"_"+label)
            made_meshes.append(mesh)
            mesh.from_pydata(geom[0],[],geom[1]);mesh.update()
            mesh.materials.append(materials[material_label])
            templates[label]=mesh
        def place(label,template,location,scale=(1,1,1),wind=False):
            ob=bpy.data.objects.new(stem+"_"+label,templates[template])
            made_objects.append(ob);group.objects.link(ob)
            ob.location=location;ob.scale=scale
            ob["p08_role"]=template
            if wind:
                vg=ob.vertex_groups.new(name="P08_WindInfluence")
                vg.add(list(range(len(ob.data.vertices))),1.0,"REPLACE")
                ob["wind_ready"]=True
            return ob
        _cancel(context)
        place("Terrain","SoilMesh",(0,0,0))
        for i in range(2):
            place("Rail_%02d"%i,"RailBox",(-6.75+i*1.42,0,.39),(.14,25.6,.16))
        for j in range(26):
            _cancel(context)
            place("Sleeper_%02d"%j,"WoodBox",(-6.04,-12.5+j,.20),(2.1,.23,.16))
        place("TemplePlinth","StoneBox",(4,3.7,.49),(8.3,7.8,.98))
        for i in range(4):
            for j in range(2):
                x=1.2+i*1.85;y=.55+j*6.3
                place("Column_%d_%d"%(i,j),"Shaft",(x,y,.98),(1,1,3.0))
                place("ColumnFoot_%d_%d"%(i,j),"StoneBox",(x,y,1.08),(.86,.86,.22))
        for y,name in ((.55,"Front"),(6.85,"Back")):
            place(name+"Entablature","StoneBox",(3.975,y,4.10),(8.5,.68,.42))
        place("TempleRoof","Roof",(3.975,3.7,4.31),(9.0,8.35,1.6))
        place("TempleArch","Arch",(3.975,-.08,1.02),(1,1,.85))
        # Separate collections are not needed: prototypes share identical native
        # Mesh datablocks; material-slot inheritance stays intact.
        for kind,positions in p["scatter"]:
            for idx,(x,y,size) in enumerate(positions):
                _cancel(context)
                z=_height(x,y)
                if kind=="tree":
                    place("TreeTrunk_%03d"%idx,"Trunk",(x,y,z),(.76*size,.76*size,2.6*size))
                    place("TreeCrown_%03d"%idx,"Crown",(x,y,z+2.85*size),
                          (1.25*size,1.18*size,1.34*size),wind=True)
                else:
                    place("Grass_%03d"%idx,"GrassBlade",(x,y,z),(.62*size,.62*size,.7*size),wind=True)
        sun=bpy.data.lights.new(stem+"_SunData","SUN");made_lights.append(sun)
        sun.energy=1.5
        sunlight=bpy.data.objects.new(stem+"_Sun",sun)
        made_objects.append(sunlight);group.objects.link(sunlight)
        sunlight.rotation_euler=(math.radians(32),math.radians(-23),math.radians(-25))
        camera_data=bpy.data.cameras.new(stem+"_CameraData");made_cameras.append(camera_data)
        camera_data.lens=32
        camera=bpy.data.objects.new(stem+"_Camera",camera_data)
        made_objects.append(camera);group.objects.link(camera)
        camera.location=(-19.0,-25.0,15.5)
        camera.rotation_euler=(Vector((0,1.4,2.5))-camera.location).to_track_quat("-Z","Y").to_euler()
        scene.camera=camera
        new_world=bpy.data.worlds.new(stem+"_World")
        new_world.use_nodes=True
        background=new_world.node_tree.nodes.get("Background")
        if background:
            background.inputs["Color"].default_value=(.45,.62,.85,1)
            background.inputs["Strength"].default_value=.75
        scene.world=new_world
        group["p08_object_count"]=len(group.objects)
        group["p08_digest"]=_audit_objects(group)
        group["p08_state"]="READY"
        checked=audit(OPERATION_NAMES[1],{"name":args["name"]},context)
        if not checked["complete"] or checked["counts"]["mesh_instances"] <= 0:
            raise RuntimeError("NATIVE_WORLD_AUDIT_FAILED")
        return {"operation":operation,"state":"succeeded","scene":scene.name,
                "source_revision":checked["source_revision"],
                "created":[o.name for o in made_objects],"already_complete":False,
                "counts":checked["counts"],"camera":camera.name,"world_shader":new_world.name,
                "artifact":{"kind":"none","sha256":None},"native_execution_verified":True,
                "visual_quality_verified":False,"quality_reduced":False,
                "warnings":["Save .blend through the app-owned snapshot API; this operation does not write files"]}
    except Exception:
        scene.camera=old_camera;scene.world=old_world
        for ob in reversed(made_objects):
            bpy.data.objects.remove(ob,do_unlink=True)
        if group is not None:
            bpy.data.collections.remove(group,do_unlink=True)
        for datablock,store in ((new_world,bpy.data.worlds),):
            if datablock is not None and datablock.users==0:store.remove(datablock)
        for store,items in ((bpy.data.meshes,made_meshes),(bpy.data.lights,made_lights),
                            (bpy.data.cameras,made_cameras),(bpy.data.materials,made_materials)):
            for datablock in reversed(items):
                if datablock.users==0:store.remove(datablock)
        raise
