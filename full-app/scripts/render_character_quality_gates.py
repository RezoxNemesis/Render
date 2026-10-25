# SPDX-License-Identifier: GPL-2.0-or-later
"""Evidence-led quality gates for native Blender character benchmark sessions.

Never confuse command completion, disconnected proxy volumes or an attached
2D reference sheet with a finished, likeness-matched animated 3D actor.
No GPU, web, fake screenshots, text-to-3D claim or silent geometry edits.
"""
import hashlib
import json
import math
import re

import bpy
from mathutils import Vector, Quaternion

_NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
_SHA=re.compile(r"^[a-f0-9]{64}$")
MAX_VERTICES=250000

def _validate(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_CHARACTER_QA_ARGUMENTS_INVALID")

def _name(value):
    if not isinstance(value,str) or not _NAME.fullmatch(value):
        raise ValueError("STUDIO_CHARACTER_QA_OBJECT_NAME_INVALID")
    return value

def _find(scene,name):
    ob=scene.objects.get(_name(name))
    if ob is None:raise ValueError("STUDIO_CHARACTER_QA_OBJECT_NOT_FOUND")
    return ob

def _components(mesh):
    count=len(mesh.vertices)
    if count>MAX_VERTICES:
        return {"count":None,"status":"SKIPPED_HIGH_POLYGON_CAP",
                "max_vertices_scanned":MAX_VERTICES}
    parent=list(range(count))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    for e in mesh.edges:
        a,b=e.vertices
        x,y=root(a),root(b)
        if x!=y:parent[x]=y
    total=len({root(i) for i in range(count)})
    return {"count":total,"status":"MEASURED_NATIVE_TOPOLOGY",
            "max_vertices_scanned":MAX_VERTICES}

def _ref_snapshot(obj):
    if obj.type!="EMPTY" or obj.empty_display_type!="IMAGE":
        raise ValueError("STUDIO_CHARACTER_QA_IMAGE_EMPTY_REQUIRED")
    im=obj.data
    if im is None or not hasattr(im,"size"):
        raise ValueError("STUDIO_CHARACTER_QA_REFERENCE_IMAGE_MISSING")
    normal=obj.matrix_world.to_3x3()@Vector((0,0,1))
    return {"object":obj.name,"image":im.name,"image_size":[int(v) for v in im.size[:2]],
            "rotation_quat":[round(float(v),7) for v in obj.rotation_euler.to_quaternion()],
            "normal_world":[round(float(v),7) for v in normal.normalized()],
            "horizontal_board":abs(float(normal.normalized().z))>.75,
            "has_packed_original":bool(im.packed_file)}

def _reference_revision(obj):
    a=_ref_snapshot(obj)
    raw=json.dumps(a,separators=(",",":"),sort_keys=True).encode("utf8")
    return hashlib.sha256(raw).hexdigest()

def _facial_controls(obj):
    if obj.type!="MESH" or obj.data.shape_keys is None:
        return {"shape_key_count":0,"candidate_facial_keys":[],
                "expressive_eyes_verified":False,"actual_expressions_proven":False}
    names=[k.name for k in obj.data.shape_keys.key_blocks if k.name!="Basis"]
    facial=[x for x in names if any(word in x.lower() for word in
        ("blink","eye","brow","lid","cheek","mouth","jaw","smile","frown"))]
    return {"shape_key_count":len(names),"candidate_facial_keys":facial[:24],
            "expressive_eyes_verified":False,"actual_expressions_proven":False}

def _textures(obj):
    rows=[];transparent=[]
    for slot in obj.material_slots[:24]:
        mat=slot.material
        if mat is None:continue
        row={"material":mat.name,"texture_sizes":[]}
        method=getattr(mat,"blend_method",None)
        if method in ("BLEND","HASHED","DITHERED"):
            transparent.append(mat.name)
        if mat.use_nodes and mat.node_tree is not None:
            for node in mat.node_tree.nodes:
                if node.type=="TEX_IMAGE" and node.image is not None:
                    row["texture_sizes"].append([int(x) for x in node.image.size[:2]])
                    if len(row["texture_sizes"])>=12:break
        rows.append(row)
    return {"materials":rows,"potential_dithered_materials":transparent}

def _viewport_height_fraction(obj):
    try:
        import render_viewport_fidelity as Preview
        areas=Preview._views()
        if not areas:return None
        sizes=Preview._projected_bbox(areas[0],obj)
        return sizes["screen_coverage_y"] if sizes else None
    except (ValueError,ImportError,AttributeError,RuntimeError,TypeError):
        return None

def audit(scene,p):
    _validate(p,("object","reference","related"),("object",))
    obj=_find(scene,p["object"])
    if obj.type!="MESH":
        raise ValueError("STUDIO_CHARACTER_QA_MESH_REQUIRED")
    refs=None
    if "reference" in p:
        ref=_find(scene,p["reference"])
        refs=_ref_snapshot(ref)
    selected=p.get("related",[])
    if not isinstance(selected,list) or len(selected)>48:
        raise ValueError("STUDIO_CHARACTER_QA_RELATED_LIMIT")
    related=[_find(scene,s) for s in selected]
    if len({x.name for x in related})!=len(related):
        raise ValueError("STUDIO_CHARACTER_QA_DUPLICATE_RELATED")
    shells=_components(obj.data)
    faces=_facial_controls(obj)
    tex=_textures(obj)
    armatures=[x.name for x in scene.objects if x.type=="ARMATURE"][:32]
    skinned=[m.object.name for m in obj.modifiers if m.type=="ARMATURE"
             and getattr(m,"object",None) is not None]
    on_screen=_viewport_height_fraction(obj)
    blockers=[]
    if bool(obj.get("render_sculpt_union_pending",False)):
        blockers.append("SCULPT_UNION_AND_RETOPOLOGY_PENDING")
    if shells["count"] is not None and shells["count"]>1:
        blockers.append("MULTIPLE_DISCONNECTED_ANATOMICAL_SHELLS")
    if not bool(obj.get("render_likeness_verified",False)):
        blockers.append("REFERENCE_LIKENESS_NOT_ARTIST_VERIFIED")
    if faces["shape_key_count"]==0:
        blockers.append("NO_FACIAL_SHAPE_KEYS")
    if not skinned:
        blockers.append("ACTOR_MESH_NOT_BOUND_TO_ARMATURE")
    if refs is None:
        blockers.append("NO_LINKED_REFERENCE_IN_QUALITY_AUDIT")
    else:
        if refs["horizontal_board"]:blockers.append("REFERENCE_SHEET_IS_HORIZONTAL")
        if min(refs["image_size"])<700:
            blockers.append("REFERENCE_TOO_SMALL_FOR_FACE_MATCHING")
    if on_screen is not None and on_screen<.28:
        blockers.append("CHARACTER_TOO_SMALL_IN_CURRENT_VIEW")
    if tex["potential_dithered_materials"]:
        blockers.append("ALPHA_DITHER_MAY_CAUSE_SURFACE_ARTIFACTS")
    # A user-rendered still and visual comparison, not the model itself, is
    # the final proof of attractive anatomy/identity/acting.
    blockers.append("FACE_AND_MOTION_RENDER_COMPARISON_PENDING")
    completed_geometry=len(obj.data.vertices)>0 and len(obj.data.polygons)>0
    return {
        "scene":scene.name,"object":obj.name,
        "working_stage":obj.get("render_work_stage","UNSPECIFIED"),
        "object_vertices":len(obj.data.vertices),
        "object_polygons":len(obj.data.polygons),
        "connected_anatomical_mesh_shells":shells,
        "sculpt_union_pending":bool(obj.get("render_sculpt_union_pending",False)),
        "reference":refs,"related_object_names":[x.name for x in related],
        "face":faces,"armature_objects_found":armatures,
        "actual_armature_bindings":skinned,
        "viewport_height_fraction":on_screen,
        "material_evidence":tex,"model_has_mesh_geometry":completed_geometry,
        "quality_gate":"BLOCKED" if blockers else "STRUCTURALLY_READY",
        "blockers":blockers,
        "completed_scene_commands_are_not_3d_likeness_proof":True,
        "source_image_is_not_a_3d_mesh":True,
        "rendered_eye_head_acting_approved":False,
        "geometry_changed":False,"render_started":False,
        "no_gallery_access":True}

def upright(scene,p):
    _validate(p,("reference","expected_sha256","dry_run","restore"),
              ("reference","expected_sha256"))
    obj=_find(scene,p["reference"])
    prior=_ref_snapshot(obj)
    if not isinstance(p["expected_sha256"],str) or not _SHA.fullmatch(p["expected_sha256"]):
        raise ValueError("STUDIO_CHARACTER_QA_REVISION_INVALID")
    before=_reference_revision(obj)
    if before!=p["expected_sha256"]:
        raise ValueError("STUDIO_CHARACTER_QA_STALE_REFERENCE")
    dry=p.get("dry_run",True);restore=p.get("restore",False)
    if type(dry) is not bool or type(restore) is not bool:
        raise ValueError("STUDIO_CHARACTER_QA_BOOLEAN_INVALID")
    # Blender image empties are locally in XY; rotate normal toward -Y so the
    # image sits upright in the XZ plane when using front viewport.
    saved=obj.get("render_qa_reference_original_euler")
    if restore:
        if saved is None or not hasattr(saved,"__len__") or len(saved)!=3:
            raise ValueError("STUDIO_CHARACTER_QA_NO_ORIGINAL_ROTATION")
        expected=[float(x) for x in saved]
    else:
        expected=[math.pi/2,0,0]
    if dry:
        return {"object":obj.name,"dry_run":True,
                "currently_horizontal":prior["horizontal_board"],
                "target_euler_radians":expected,
                "geometry_changed":False}
    original=list(obj.rotation_euler)
    try:
        if not restore and saved is None:
            obj["render_qa_reference_original_euler"]=original
        obj.rotation_euler=expected
        bpy.context.view_layer.update()
        for area in [a for win in bpy.context.window_manager.windows
                     for a in win.screen.areas if a.type=="VIEW_3D"]:
            area.tag_redraw()
        snap=_ref_snapshot(obj)
        if not restore and snap["horizontal_board"]:
            raise ValueError("STUDIO_CHARACTER_QA_REFERENCE_STILL_HORIZONTAL")
        if restore:
            obj.pop("render_qa_reference_original_euler",None)
        return {"object":obj.name,"actual_blender_reference_rotated":True,
                "previous_horizontal":prior["horizontal_board"],
                "new_horizontal":snap["horizontal_board"],
                "revision_before":before,"revision_after":_reference_revision(obj),
                "reference_image_bytes_unchanged":True,
                "body_geometry_unchanged":True,
                "original_restored":restore}
    except Exception:
        obj.rotation_euler=original
        raise

def execute(op,p,root,scene):
    if op=="studio.character.qa.inspect":return audit(scene,p)
    if op=="studio.character.qa.upright":return upright(scene,p)
    raise ValueError("STUDIO_CHARACTER_QA_OPERATION_UNAVAILABLE")

def capabilities():
    n={"type":"string","pattern":_NAME.pattern}
    h={"type":"string","pattern":_SHA.pattern}
    return [
      {"operation":"studio.character.qa.inspect","workspace":"characters",
       "read_only":True,"input_schema":{"type":"object",
           "required":["object"],"additionalProperties":False,
           "properties":{"object":n,"reference":n,
                         "related":{"type":"array","maxItems":48,"items":n}}}},
      {"operation":"studio.character.qa.upright","workspace":"assets",
       "read_only":False,"checkpoint_before_change":True,
       "input_schema":{"type":"object","required":["reference","expected_sha256"],
         "additionalProperties":False,"properties":{
             "reference":n,"expected_sha256":h,
             "dry_run":{"type":"boolean"},"restore":{"type":"boolean"}}}}
    ]
