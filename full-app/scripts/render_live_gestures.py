# SPDX-License-Identifier: GPL-2.0-or-later
"""Measured sculpting and pose controls on actual editable Blender data.

Object-space mesh brush is a deterministic, bounded *vertex deformation*,
not Blender's interactive brush kernel, a screen-space illusion or a claim
of ZBrush parity. Native sculpt mode remains separately available.
"""
import hashlib
import math
import struct

import bpy
from mathutils import Vector

MAX_HOST_VERTICES=250000

def _fields(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_GESTURE_FIELDS_INVALID")

def _number(x,lower,upper):
    if type(x) not in (int,float) or not math.isfinite(x) or not lower<=x<=upper:
        raise ValueError("STUDIO_GESTURE_NUMBER_INVALID")
    return float(x)

def _vec(v,n=3,lower=-100000,upper=100000):
    if not isinstance(v,list) or len(v)!=n:
        raise ValueError("STUDIO_GESTURE_VECTOR_INVALID")
    return Vector([_number(x,lower,upper) for x in v])

def _name(x):
    if not isinstance(x,str) or not 1<=len(x)<=80 or any(
            c in x for c in ("/","\\","\n","\r","\0")):
        raise ValueError("STUDIO_GESTURE_NAME_INVALID")
    return x

def _obj(scene,name,kind):
    ob=scene.objects.get(_name(name))
    if ob is None or ob.type!=kind:
        raise ValueError("STUDIO_GESTURE_TARGET_MISSING")
    return ob

def _fingerprint(ob):
    mesh=ob.data
    if len(mesh.vertices)>MAX_HOST_VERTICES:
        raise ValueError("STUDIO_GESTURE_HIGH_DENSITY_USE_NATIVE_SCULPT")
    digest=hashlib.sha256()
    digest.update(str(len(mesh.vertices)).encode("ascii"))
    digest.update(str(len(mesh.polygons)).encode("ascii"))
    for v in mesh.vertices:
        digest.update(struct.pack("!fff",*tuple(v.co)))
    return digest.hexdigest()

def mesh_inspect(scene,p):
    _fields(p,("object",),("object",))
    ob=_obj(scene,p["object"],"MESH")
    n=len(ob.data.vertices)
    signature=_fingerprint(ob)
    bounds=[tuple(ob.bound_box[i]) for i in range(8)]
    return {"object":ob.name,"vertices":n,"polygons":len(ob.data.polygons),
            "mesh_revision_sha256":signature,"bounds_local":bounds,
            "object_mode":ob.mode,
            "shared_geometry_users":ob.data.users,
            "has_shape_keys":ob.data.shape_keys is not None,
            "max_typed_brush_vertices":MAX_HOST_VERTICES,
            "sculpt_mode_brush_replaced":False,"native_blender_mesh_inspected":True}

def _falloff(distance,radius,mode):
    t=distance/radius
    if t>=1:return 0
    if mode=="SMOOTHSTEP":return 1-3*t*t+2*t*t*t
    if mode=="SHARP":return (1-t)**2
    if mode=="FLAT":return 1-t
    raise ValueError("STUDIO_GESTURE_FALLOFF_INVALID")

def _neighbors(mesh):
    neighbors=[set() for _ in mesh.vertices]
    for edge in mesh.edges:
        a,b=edge.vertices
        neighbors[a].add(b);neighbors[b].add(a)
    return neighbors

def sculpt(scene,p):
    fields=("object","expected_vertices","expected_sha256","center",
            "radius","strength","direction","mode","falloff","mirror_x",
            "dry_run","max_affected")
    _fields(p,fields,("object","expected_vertices","expected_sha256",
                      "center","radius","strength","direction"))
    ob=_obj(scene,p["object"],"MESH")
    mesh=ob.data
    if ob.mode!="OBJECT":raise ValueError("STUDIO_TYPED_BRUSH_OBJECT_MODE_REQUIRED")
    if mesh.users>1:raise ValueError("STUDIO_SHARED_MESH_REQUIRES_COPY")
    if mesh.shape_keys is not None:
        raise ValueError("STUDIO_SCULPT_SHAPE_KEY_MODEL_REQUIRES_NATIVE_BRUSH")
    expected=p["expected_vertices"]
    if type(expected) is not int or expected!=len(mesh.vertices):
        raise ValueError("STUDIO_SCULPT_MESH_REVISION_CONFLICT")
    token=p["expected_sha256"]
    if type(token) is not str or len(token)!=64 or token!=_fingerprint(ob):
        raise ValueError("STUDIO_SCULPT_MESH_REVISION_CONFLICT")
    center=_vec(p["center"])
    direction=_vec(p["direction"],lower=-1e3,upper=1e3)
    if direction.length<1e-8:raise ValueError("STUDIO_SCULPT_DIRECTION_ZERO")
    direction.normalize()
    radius=_number(p["radius"],.0001,100)
    strength=_number(p["strength"],.000001,.75)
    mode=p.get("mode","PUSH")
    if mode not in ("PUSH","INFLATE","SMOOTH","PINCH"):
        raise ValueError("STUDIO_SCULPT_MODE_INVALID")
    falloff=p.get("falloff","SMOOTHSTEP")
    if falloff not in ("SMOOTHSTEP","SHARP","FLAT"):
        raise ValueError("STUDIO_GESTURE_FALLOFF_INVALID")
    mirror=p.get("mirror_x",False)
    dry=p.get("dry_run",False)
    if type(mirror) is not bool or type(dry) is not bool:
        raise ValueError("STUDIO_GESTURE_BOOLEAN_INVALID")
    maximum=p.get("max_affected",25000)
    if type(maximum) is not int or not 1<=maximum<=100000:
        raise ValueError("STUDIO_GESTURE_AFFECTED_LIMIT_INVALID")
    centers=[(center,direction)]
    if mirror and abs(center.x)>1e-8:
        centers.append((Vector((-center.x,center.y,center.z)),
                        Vector((-direction.x,direction.y,direction.z))))
    # Preflight every destination vertex before mutating shared scene data.
    mesh.update()
    mesh.calc_normals() if hasattr(mesh,"calc_normals") else None
    positions=[v.co.copy() for v in mesh.vertices]
    adjacency=_neighbors(mesh) if mode=="SMOOTH" else None
    changes=[]
    for vert in mesh.vertices:
        candidates=[]
        for c,d in centers:
            distance=(vert.co-c).length
            if distance>=radius:continue
            weight=_falloff(distance,radius,falloff)
            if weight<=0:continue
            if mode=="PUSH":vector=d
            elif mode=="INFLATE":vector=vert.normal
            elif mode=="PINCH":
                vector=c-vert.co
                if vector.length<1e-8:continue
                vector.normalize()
            else:
                ngh=adjacency[vert.index]
                if not ngh:continue
                target=sum((positions[n] for n in ngh),Vector())/len(ngh)
                vector=target-vert.co
                if vector.length<1e-8:continue
                vector.normalize()
            if vector.length<1e-8:continue
            candidates.append((weight,vector))
        if not candidates:continue
        weight,vector=max(candidates,key=lambda x:x[0])
        displacement=vector.normalized()*(strength*weight)
        if displacement.length>0:
            changes.append((vert.index,positions[vert.index]+displacement,
                            float(displacement.length)))
        if len(changes)>maximum:
            raise ValueError("STUDIO_SCULPT_VERTEX_BUDGET_EXCEEDED")
    if not changes:raise ValueError("STUDIO_SCULPT_NO_VERTICES_IN_RADIUS")
    if not dry:
        for index,new_position,_ in changes:
            mesh.vertices[index].co=new_position
        mesh.update()
    # Do not report an uncommitted dry run as a successful sculpt.
    return {"object":ob.name,"mode":mode,"falloff":falloff,
            "vertices_changed":0 if dry else len(changes),
            "vertices_predicted":len(changes),
            "maximum_local_displacement":max(q[2] for q in changes),
            "mirrored":mirror,"dry_run":dry,
            "mesh_revision_before":token,
            "mesh_revision_after":token if dry else _fingerprint(ob),
            "native_blender_vertex_coordinates_updated":not dry,
            "topology_changed":False,"materials_preserved":True,
            "actual_brush_kernel_in_sculpt_mode":False,
            "real_geometry_edit_not_screen_overlay":True}

def pose_inspect(scene,p):
    _fields(p,("rig","bones"),("rig",))
    rig=_obj(scene,p["rig"],"ARMATURE")
    names=p.get("bones",list(rig.pose.bones.keys())[:24])
    if not isinstance(names,list) or not 1<=len(names)<=32:
        raise ValueError("STUDIO_POSE_BONE_SELECTION_INVALID")
    results=[]
    for bone in names:
        pb=rig.pose.bones.get(_name(bone))
        if pb is None:raise ValueError("STUDIO_POSE_BONE_MISSING")
        results.append({"bone":pb.name,
                        "rotation_mode":pb.rotation_mode,
                        "rotation_euler":list(pb.rotation_euler),
                        "head_world":list(rig.matrix_world@pb.head),
                        "tail_world":list(rig.matrix_world@pb.tail)})
    return {"rig":rig.name,"bones":results,
            "frame":scene.frame_current,
            "active_action":rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else None,
            "native_pose_bones_evaluated":True}

def pose_key(scene,p):
    fields=("rig","bone","frame","rotation_euler","location",
            "preview_frame","allow_existing_action","dry_run")
    _fields(p,fields,("rig","bone","frame","rotation_euler"))
    rig=_obj(scene,p["rig"],"ARMATURE")
    bone=rig.pose.bones.get(_name(p["bone"]))
    if bone is None:raise ValueError("STUDIO_POSE_BONE_MISSING")
    f=p["frame"]
    if type(f) is not int or not 1<=f<=100000:
        raise ValueError("STUDIO_POSE_FRAME_INVALID")
    euler=_vec(p["rotation_euler"],lower=-100,upper=100)
    location=_vec(p["location"]) if "location" in p else None
    preview=p.get("preview_frame",True)
    allow=p.get("allow_existing_action",False)
    dry=p.get("dry_run",False)
    if type(preview) is not bool or type(allow) is not bool or type(dry) is not bool:
        raise ValueError("STUDIO_POSE_BOOLEAN_INVALID")
    if rig.animation_data and rig.animation_data.action and not allow:
        raise ValueError("STUDIO_POSE_EXISTING_ACTION_APPROVAL_REQUIRED")
    existing=rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else None
    if dry:
        return {"rig":rig.name,"bone":bone.name,"frame":f,
                "dry_run":True,"would_change_existing_action":existing is not None,
                "existing_action":existing,"native_pose_key_inserted":False}
    old=scene.frame_current
    try:
        scene.frame_set(f)
        bone.rotation_mode="XYZ"
        bone.rotation_euler=euler
        if not bone.keyframe_insert(data_path="rotation_euler",frame=f,group=bone.name):
            raise RuntimeError("STUDIO_POSE_KEYFRAME_INSERT_FAILED")
        if location is not None:
            bone.location=location
            if not bone.keyframe_insert(data_path="location",frame=f,group=bone.name):
                raise RuntimeError("STUDIO_POSE_KEYFRAME_INSERT_FAILED")
        bpy.context.view_layer.update()
    finally:
        if not preview:scene.frame_set(old)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in ("VIEW_3D","GRAPH_EDITOR","DOPESHEET_EDITOR"):
                area.tag_redraw()
    return {"rig":rig.name,"bone":bone.name,"frame":f,
            "action":rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else None,
            "native_pose_key_inserted":True,"evaluated_frame":scene.frame_current,
            "screen_updates_requested":True,
            "automatic_physics_and_ik_claimed":False,
            "real_bone_pose_data_changed":True}

def timeline(scene,p):
    _fields(p,("frame","rig","bone"),("frame",))
    f=p["frame"]
    if type(f) is not int or not 1<=f<=100000:
        raise ValueError("STUDIO_TIMELINE_FRAME_INVALID")
    pb=None;rig=None
    if "bone" in p and "rig" not in p:raise ValueError("STUDIO_TIMELINE_RIG_REQUIRED")
    if "rig" in p:
        rig=_obj(scene,p["rig"],"ARMATURE")
        if "bone" in p:
            pb=rig.pose.bones.get(_name(p["bone"]))
            if pb is None:raise ValueError("STUDIO_POSE_BONE_MISSING")
    scene.frame_set(f)
    bpy.context.view_layer.update()
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in ("VIEW_3D","GRAPH_EDITOR","DOPESHEET_EDITOR","NLA_EDITOR"):
                area.tag_redraw()
    data={"frame":scene.frame_current,"native_blender_frame_evaluated":True,
          "rendered_video_frame_created":False}
    if pb is not None:
        data.update(rig=rig.name,bone=pb.name,
                    head_world=list(rig.matrix_world@pb.head),
                    tail_world=list(rig.matrix_world@pb.tail))
    return data

def execute(op,p,root,scene):
    if op=="studio.sculpt.inspect":return mesh_inspect(scene,p)
    if op=="studio.sculpt.brush":return sculpt(scene,p)
    if op=="studio.pose.inspect":return pose_inspect(scene,p)
    if op=="studio.pose.key":return pose_key(scene,p)
    if op=="studio.timeline.scrub":return timeline(scene,p)
    raise ValueError("STUDIO_GESTURE_OPERATION_UNAVAILABLE")

def capabilities():
    operations=[
      {"operation":"studio.sculpt.inspect","workspace":"sculpt","read_only":True,
       "fields":["object"],"required":["object"],
       "supports_real_bpy_geometry":True},
      {"operation":"studio.sculpt.brush","workspace":"sculpt","read_only":False,
       "required":["object","expected_vertices","expected_sha256",
                   "center","radius","strength","direction"],
       "fields":["object","expected_vertices","expected_sha256","center","radius",
                 "strength","direction","mode","falloff","mirror_x","dry_run","max_affected"],
       "requires_mesh_revision":True,"checkpoint_before_change":True,
       "actual_sculpt_mode_brush":False},
      {"operation":"studio.pose.inspect","workspace":"characters","read_only":True,
       "required":["rig"],"fields":["rig","bones"]},
      {"operation":"studio.pose.key","workspace":"animation","read_only":False,
       "required":["rig","bone","frame","rotation_euler"],
       "fields":["rig","bone","frame","rotation_euler","location",
                 "preview_frame","allow_existing_action","dry_run"],
       "checkpoint_before_change":True},
      {"operation":"studio.timeline.scrub","workspace":"animation","read_only":False,
       "required":["frame"],"fields":["frame","rig","bone"]}
    ]
    vector={"type":"array","minItems":3,"maxItems":3,
            "items":{"type":"number"}}
    title={"type":"string","minLength":1,"maxLength":80}
    specs={
      "object":title,"rig":title,"bone":title,
      "expected_sha256":{"type":"string",
        "description":"Exact 64-digit hash from studio.sculpt.inspect; chained plans can use $prev_mesh_sha256"},
      "expected_vertices":{"type":"integer","minimum":1,"maximum":MAX_HOST_VERTICES},
      "center":vector,"direction":vector,
      "radius":{"type":"number","minimum":.0001,"maximum":100},
      "strength":{"type":"number","minimum":.000001,"maximum":.75},
      "mode":{"enum":["PUSH","INFLATE","SMOOTH","PINCH"]},
      "falloff":{"enum":["SMOOTHSTEP","SHARP","FLAT"]},
      "mirror_x":{"type":"boolean"},"dry_run":{"type":"boolean"},
      "max_affected":{"type":"integer","minimum":1,"maximum":100000},
      "bones":{"type":"array","minItems":1,"maxItems":32,
               "items":title},
      "frame":{"type":"integer","minimum":1,"maximum":100000},
      "rotation_euler":vector,"location":vector,
      "preview_frame":{"type":"boolean"},
      "allow_existing_action":{"type":"boolean"},
    }
    for entry in operations:
        entry["input_schema"]={
            "type":"object","properties":{k:specs[k] for k in entry["fields"]},
            "required":entry["required"],"additionalProperties":False}
    return operations
