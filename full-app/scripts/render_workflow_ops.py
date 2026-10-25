# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender DCC artist primitives tied to external tutorial benchmarks.

Native Blender object edits, never fake pointer moves, remote Python, neural
3D reconstruction or third-party commercial binaries. Each mutation is
checkpointed by the original render_production dispatch before execution.
"""
import hashlib
import json
import math
import random
import bpy
import bmesh
from mathutils import Vector
import render_workflow_contract as C

def _obj(scene,name,kind=None):
    ob=scene.objects.get(C.name(name))
    if ob is None or kind is not None and ob.type!=kind:
        raise ValueError("STUDIO_DCC_OBJECT_NOT_FOUND")
    return ob

def _new(name):
    C.name(name)
    if name in bpy.data.objects or name in bpy.data.collections:
        raise ValueError("STUDIO_DCC_NAME_EXISTS")
    return name

def _context_object(ob):
    prior=bpy.context.view_layer.objects.active
    previously=list(bpy.context.selected_objects)
    if bpy.context.object and bpy.context.object.mode!="OBJECT":
        raise ValueError("STUDIO_DCC_OBJECT_MODE_REQUIRED")
    for item in previously:item.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active=ob
    return prior,previously

def _restore_context(prior,selection):
    try:
        for ob in list(bpy.context.selected_objects):ob.select_set(False)
        for ob in selection:
            if ob.name in bpy.context.view_layer.objects:ob.select_set(True)
        if prior and prior.name in bpy.context.view_layer.objects:
            bpy.context.view_layer.objects.active=prior
    except (ReferenceError,RuntimeError,AttributeError):pass

def catalog(p):
    C.validate("studio.benchmark.catalog",p)
    group=p.get("discipline")
    items=[{
         "filename":name,"category":category,"observed_workflow":description,
         "engineering_acceptance":criteria,
         "source":"owner-supplied external desktop video technical analysis",
         "direct_original_video_bytes_bundled":False,
         "render_studio_produced_this_video":False}
        for name,category,description,criteria in C.BENCHMARKS
        if group is None or category==group]
    return {"contract":C.VERSION,"benchmarks":items,
            "total_benchmarks":len(C.BENCHMARKS),
            "actual_video_reconstruction_completed":False,
            "all_vendor_software_parity_claimed":False,
            "measurement_requires_actual_scene_and_visual_review":True}

def audit(scene,p):
    C.validate("studio.benchmark.audit",p)
    chosen=scene.objects.get(p["object"]) if "object" in p else bpy.context.active_object
    objects=list(scene.objects)
    curves=sum(x.type=="CURVE" for x in objects)
    scene_meshes=[x for x in objects if x.type=="MESH"]
    rig=[x for x in objects if x.type=="ARMATURE"]
    shape_bones=sum(len(x.pose.bones) for x in rig)
    constraints=sum(len(pb.constraints) for x in rig for pb in x.pose.bones)
    actions=[x for x in bpy.data.actions if x.users>0]
    strips=sum(len(track.strips) for x in rig if x.animation_data
               for track in x.animation_data.nla_tracks)
    instanced=sum(bool(x.get("render_benchmark_scatter")) for x in objects)
    rigid=sum(x.rigid_body is not None for x in objects)
    comps=[]
    if scene.use_nodes and scene.node_tree is not None:
        comps=[x.name for x in scene.node_tree.nodes
               if x.get("render_benchmark_grade")]
    materials=[mat for mat in bpy.data.materials if
               mat.get("render_benchmark_surface")]
    bridge=[x for x in scene_meshes if x.get("render_benchmark_bridge")]
    notes=[
      "Counts and native nodes do not prove cinema-quality visuals",
      "Animation contact/footslide and timing must be tested on evaluated frames",
      "Specialized liquid simulation export/import not yet implemented",
      "Retopology/sculpt brush quality and physical GPU frame rate still require evidence",
    ]
    return {"scene":scene.name,"selected_object":chosen.name if chosen else None,
        "native_meshes":len(scene_meshes),"native_curves":curves,
        "native_armatures":len(rig),"rig_bones":shape_bones,
        "rig_constraints":constraints,"used_actions":len(actions),
        "nla_strips":strips,"linked_scatter_instances":instanced,
        "rigid_body_objects":rigid,"registered_pbr_surfaces":len(materials),
        "grade_nodes":comps[:32],"bridge_meshes":len(bridge),
        "implemented_domain_operations":sorted(C.OPS),
        "benchmark_visual_criteria_automatically_passed":False,
        "liquigen_fluid_interop_implemented":False,
        "onscreen_human_mouse_gesture_synthesized":False,
        "source_scene_mutated":False,
        "limitations":notes}

def bridge(scene,p):
    C.validate("studio.mesh.bridge_loops",p)
    ob=_obj(scene,p["object"],"MESH")
    mesh=ob.data
    if ob.mode!="OBJECT":raise ValueError("STUDIO_DCC_BRIDGE_OBJECT_MODE")
    if mesh.users>1 or mesh.shape_keys is not None:
        raise ValueError("STUDIO_DCC_BRIDGE_REQUIRES_SINGLE_USER_NO_SHAPES")
    if (len(mesh.vertices)!=p["expected_vertices"] or
        len(mesh.polygons)!=p["expected_polygons"]):
        raise ValueError("STUDIO_DCC_BRIDGE_MESH_REVISION_CONFLICT")
    first,second=p["loops"]
    # Check that both loops follow REAL singly-owned boundary edges.
    incidence={}
    for face in mesh.polygons:
        seq=list(face.vertices)
        for i,a in enumerate(seq):
            b=seq[(i+1)%len(seq)]
            edge=(min(a,b),max(a,b))
            incidence[edge]=incidence.get(edge,0)+1
    for ring in (first,second):
        for i,a in enumerate(ring):
            b=ring[(i+1)%len(ring)]
            edge=(min(a,b),max(a,b))
            if incidence.get(edge)!=1:
                raise ValueError("STUDIO_DCC_BRIDGE_NOT_A_BOUNDARY_LOOP")
    first_v=[Vector(mesh.vertices[i].co) for i in first]
    second_v=[Vector(mesh.vertices[i].co) for i in second]
    if min((a-b).length for a,b in zip(first_v,second_v))<1e-6:
        raise ValueError("STUDIO_DCC_BRIDGE_COLLAPSED_SPAN")
    if p.get("dry_run",False):
        return {"object":ob.name,"would_add_quads":len(first),
                "dry_run":True,"created_polygons":0,
                "native_mesh_unchanged":True}
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        prior_faces=len(bm.faces)
        added=[]
        for i in range(len(first)):
            j=(i+1)%len(first)
            v=[bm.verts[first[i]],bm.verts[first[j]],
               bm.verts[second[j]],bm.verts[second[i]]]
            try:face=bm.faces.new(v)
            except ValueError as exc:
                raise ValueError("STUDIO_DCC_BRIDGE_FACE_ALREADY_EXISTS") from exc
            added.append(face)
        bmesh.ops.recalc_face_normals(bm,faces=added)
        bm.to_mesh(mesh)
        mesh.update()
        if len(mesh.polygons)!=prior_faces+len(first):
            raise ValueError("STUDIO_DCC_BRIDGE_TOPOLOGY_NOT_COMMITTED")
    finally:bm.free()
    ob["render_benchmark_bridge"]=len(first)
    return {"object":ob.name,"created_polygons":len(first),
            "total_polygons":len(mesh.polygons),"vertices_added":0,
            "native_editable_bridge_faces_created":True,
            "original_materials_preserved":True,
            "manual_winding_validation_recommended":True}

def scatter(scene,p):
    C.validate("studio.procedural.scatter",p)
    source=_obj(scene,p["source"],"MESH")
    if source.mode!="OBJECT":raise ValueError("STUDIO_DCC_SCATTER_OBJECT_MODE")
    name=_new(p["name"])
    count=p["count"]
    rnd=random.Random(p.get("seed",0))
    lo,hi=p["min"],p["max"]
    transforms=[]
    for i in range(count):
        location=[rnd.uniform(a,b) for a,b in zip(lo,hi)]
        scale=rnd.uniform(p.get("scale_min",.7),p.get("scale_max",1.3))
        yaw=rnd.uniform(-math.pi,math.pi) if p.get("yaw_random",True) else 0.0
        transforms.append((location,scale,yaw))
    if p.get("dry_run",False):
        return {"source":source.name,"name":name,
                "predicted_linked_instances":count,"dry_run":True,
                "native_instances_created":0}
    collection=bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    made=[]
    try:
        for i,(location,scale,yaw) in enumerate(transforms):
            ob=source.copy()
            # Object.copy shares source.data, not duplicating expensive mesh
            # buffers; modifying one source geometry updates all instances.
            ob.name=f"{name}_{i+1:03d}"
            collection.objects.link(ob)
            ob.location=location
            ob.rotation_euler=(0,0,yaw)
            ob.scale=tuple(float(v)*scale for v in source.scale)
            ob["render_benchmark_scatter"]=name
            made.append(ob)
        collection["render_benchmark_instanced_from"]=source.name
        collection["render_benchmark_seed"]=p.get("seed",0)
        collection["render_benchmark_count"]=count
        if not all(ob.data==source.data for ob in made):
            raise ValueError("STUDIO_DCC_INSTANCE_GEOMETRY_NOT_LINKED")
        return {"collection":collection.name,"source":source.name,
                "linked_mesh_objects":count,"seed":p.get("seed",0),
                "native_instances_created":len(made),
                "source_mesh_users":source.data.users,
                "exact_transform_seeded":True,"geometry_cloned_per_instance":False,
                "LOD_budget_not_guaranteed":True}
    except Exception:
        bpy.data.collections.remove(collection,do_unlink=True)
        raise

_PRESET_COLORS={
 "SKIN":(.49,.29,.22),"LEAF":(.09,.25,.08),"CLOTH":(.2,.29,.36),
 "STONE":(.38,.37,.34),"METAL":(.26,.28,.32)
}

def material(scene,p):
    C.validate("studio.material.surface",p)
    ob=_obj(scene,p["object"],"MESH")
    name=_new(p["name"])
    if ob.data.materials and not p.get("replace_existing",False):
        raise ValueError("STUDIO_DCC_MATERIAL_REPLACE_REQUIRES_APPROVAL")
    if ob.data.users>1:
        raise ValueError("STUDIO_DCC_MATERIAL_SINGLE_USER_REQUIRED")
    if p.get("dry_run",False):
        return {"object":ob.name,"name":name,"dry_run":True}
    color=p.get("color",list(_PRESET_COLORS[p["preset"]]))
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    nodes=mat.node_tree.nodes
    links=mat.node_tree.links
    bsdf=next((node for node in nodes if node.type=="BSDF_PRINCIPLED"),None)
    if bsdf is None:
        bpy.data.materials.remove(mat)
        raise ValueError("STUDIO_DCC_PRINCIPLED_SHADER_UNAVAILABLE")
    bsdf.inputs["Base Color"].default_value=(*color,1)
    bsdf.inputs["Roughness"].default_value=p.get("roughness",.55)
    bsdf.inputs["Metallic"].default_value=.72 if p["preset"]=="METAL" else 0
    texture=nodes.new("ShaderNodeTexNoise")
    texture.name="RS_SubstanceLike_ProceduralDetail"
    texture.inputs["Scale"].default_value=p.get("detail_scale",24)
    bump=nodes.new("ShaderNodeBump")
    bump.name="RS_EditableSurfaceMicroBump"
    bump.inputs["Strength"].default_value=p.get("bump",.08)
    bump.inputs["Distance"].default_value=.0015
    links.new(texture.outputs["Fac"],bump.inputs["Height"])
    links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    texture.location=(-550,-175);bump.location=(-230,-170)
    bsdf.location=(130,50)
    mat.diffuse_color=(*color,1)
    mat["render_benchmark_surface"]=p["preset"]
    if ob.data.materials:
        ob.data.materials[0]=mat
    else:ob.data.materials.append(mat)
    return {"object":ob.name,"material":mat.name,"preset":p["preset"],
            "procedural_noise_connected_to_bump":True,
            "actual_shader_node_tree_created":True,
            "UV_texture_or_skin_scan_reconstructed":False,
            "complete_Substance3D_parity":False}

def motion_action(scene,p):
    C.validate("studio.motion.action.create",p)
    rig=_obj(scene,p["rig"],"ARMATURE")
    pb=rig.pose.bones.get(p["bone"])
    if pb is None:raise ValueError("STUDIO_DCC_POSE_BONE_NOT_FOUND")
    name=C.name(p["name"])
    if name in bpy.data.actions:raise ValueError("STUDIO_DCC_ACTION_ALREADY_EXISTS")
    rig.animation_data_create()
    existing=rig.animation_data.action
    if existing is not None and not p.get("allow_existing_action",False):
        raise ValueError("STUDIO_DCC_ACTION_EXISTING_APPROVAL_REQUIRED")
    if p.get("dry_run",False):
        return {"rig":rig.name,"bone":pb.name,"poses":len(p["keys"]),
                "dry_run":True,"native_action_created":False}
    prev=scene.frame_current
    prev_mode=pb.rotation_mode
    previous=pb.rotation_euler.copy()
    act=bpy.data.actions.new(name)
    committed=False
    try:
        rig.animation_data.action=act
        pb.rotation_mode="XYZ"
        for row in p["keys"]:
            scene.frame_set(row["frame"])
            pb.rotation_euler=row["rotation_euler"]
            if not pb.keyframe_insert(data_path="rotation_euler",
                                      frame=row["frame"],group=pb.name):
                raise RuntimeError("STUDIO_DCC_ACTION_KEY_NOT_INSERTED")
        curves=getattr(act,"fcurves",None)
        count=len(curves) if curves is not None else None
        if count==0:raise RuntimeError("STUDIO_DCC_ACTION_NO_NATIVE_CURVES")
        committed=True
        return {"action":act.name,"rig":rig.name,"bone":pb.name,
                "key_poses":len(p["keys"]),"native_action_created":True,
                "native_fcurves":count,"rotation_mode":"XYZ",
                "original_action_retained_in_data":existing is not None,
                "contact_foot_drift_not_verified":True}
    except Exception:
        rig.animation_data.action=existing
        if act.users==0:bpy.data.actions.remove(act)
        raise
    finally:
        # Euler F-Curves are ignored if rotation_mode reverts to QUATERNION.
        # Keep XYZ on a successful real keyed action; restore only on error.
        if not committed:
            pb.rotation_mode=prev_mode
            pb.rotation_euler=previous
        scene.frame_set(prev)

def motion_nla(scene,p):
    C.validate("studio.motion.nla.create",p)
    rig=_obj(scene,p["rig"],"ARMATURE")
    action=bpy.data.actions.get(p["action"])
    if action is None:raise ValueError("STUDIO_DCC_NLA_ACTION_NOT_FOUND")
    rig.animation_data_create()
    tracks=rig.animation_data.nla_tracks
    if any(t.name==p["name"] for t in tracks):
        raise ValueError("STUDIO_DCC_NLA_TRACK_ALREADY_EXISTS")
    if p.get("dry_run",False):
        return {"rig":rig.name,"action":action.name,"dry_run":True}
    track=tracks.new()
    track.name=p["name"]
    try:
        strip=track.strips.new(p["name"],p["frame_start"],action)
        if strip.action!=action:
            raise ValueError("STUDIO_DCC_NLA_STRIP_NOT_LINKED")
        return {"rig":rig.name,"action":action.name,"track":track.name,
                "strip":strip.name,"frame_start":int(strip.frame_start),
                "native_nla_track_created":True,
                "action_editable":True}
    except Exception:
        tracks.remove(track)
        raise

def compositor(scene,p):
    C.validate("studio.compositor.grade",p)
    if p.get("dry_run",False):
        return {"name":p["name"],"preview_only":True,"nodes_created":0}
    if scene.use_nodes and scene.node_tree is not None:
        existing=[n for n in scene.node_tree.nodes
                  if n.get("render_benchmark_grade")==p["name"]]
        if existing:raise ValueError("STUDIO_DCC_GRADE_NAME_ALREADY_EXISTS")
    scene.use_nodes=True
    tree=scene.node_tree
    if tree is None:raise ValueError("STUDIO_DCC_COMPOSITOR_NODES_NOT_AVAILABLE")
    nodes=tree.nodes;links=tree.links
    new_nodes=[]
    old_input=None
    try:
        brightness=nodes.new("CompositorNodeBrightContrast")
        brightness.name="RS_"+p["name"]+"_BrightContrast"
        brightness["render_benchmark_grade"]=p["name"]
        brightness.inputs["Bright"].default_value=p.get("brightness",0)
        brightness.inputs["Contrast"].default_value=p.get("contrast",0)
        saturation=nodes.new("CompositorNodeHueSat")
        saturation.name="RS_"+p["name"]+"_Color"
        saturation["render_benchmark_grade"]=p["name"]
        saturation.inputs["Hue"].default_value=p.get("hue",.5)
        saturation.inputs["Saturation"].default_value=p.get("saturation",1)
        new_nodes=[brightness,saturation]
        brightness.location=(0,-330);saturation.location=(245,-330)
        links.new(brightness.outputs[0],saturation.inputs["Image"])
        if p.get("activate",False):
            render_layers=next((n for n in nodes if n.type=="R_LAYERS"),None)
            composite=next((n for n in nodes if n.type=="COMPOSITE"),None)
            if render_layers is None or composite is None:
                raise ValueError("STUDIO_DCC_COMPOSITOR_REQUIRED_NODES_NOT_PRESENT")
            old_input=next((link.from_socket for link in composite.inputs[0].links),None)
            links.new(render_layers.outputs["Image"],brightness.inputs["Image"])
            links.new(saturation.outputs["Image"],composite.inputs["Image"])
        return {"node_names":[n.name for n in new_nodes],"new_nodes":len(new_nodes),
                "native_compositor_graph_linked":True,
                "activated_for_final_render":p.get("activate",False),
                "all_grade_parameters_editable":True,
                "raw_final_frames_comparison_rendered":False}
    except Exception:
        for node in new_nodes:
            if node.name in nodes:nodes.remove(node)
        if old_input is not None:
            c=next((n for n in nodes if n.type=="COMPOSITE"),None)
            if c is not None:links.new(old_input,c.inputs["Image"])
        raise

def compositor_inspect(scene,p):
    C.validate("studio.compositor.inspect",p)
    if not scene.use_nodes or scene.node_tree is None:
        return {"enabled":False,"native_grade_nodes":[]}
    tree=scene.node_tree
    names=[n.name for n in tree.nodes if n.get("render_benchmark_grade")]
    c=next((n for n in tree.nodes if n.type=="COMPOSITE"),None)
    return {"enabled":True,"native_grade_nodes":names[:40],
            "composite_has_input":bool(c and c.inputs[0].is_linked),
            "nodes_actual_blender_datablocks":True}

def rigidbody(scene,p):
    C.validate("studio.sim.rigidbody",p)
    ob=_obj(scene,p["object"],"MESH")
    if ob.rigid_body is not None:
        raise ValueError("STUDIO_DCC_RIGIDBODY_ALREADY_EXISTS")
    if p.get("dry_run",False):
        return {"object":ob.name,"dry_run":True,
                "native_rigidbody_created":False}
    prior,selected=_context_object(ob)
    try:
        bpy.ops.rigidbody.object_add()
        rb=ob.rigid_body
        if rb is None:raise RuntimeError("STUDIO_DCC_RIGIDBODY_NOT_CREATED")
        rb.type=p.get("type","ACTIVE")
        rb.mass=p.get("mass",1)
        rb.friction=p.get("friction",.5)
        rb.restitution=p.get("bounce",0)
        ob["render_benchmark_rigidbody"]=True
        return {"object":ob.name,"type":rb.type,
                "mass":float(rb.mass),"friction":float(rb.friction),
                "native_blender_rigidbody_created":True,
                "simulation_bake_verified":False,
                "liquid_solver_implemented":False}
    finally:_restore_context(prior,selected)

def drawing(scene,p):
    C.validate("studio.drawing.strokes",p)
    name=_new(p["name"])
    if p.get("dry_run",False):
        return {"name":name,"strokes":len(p["strokes"]),"dry_run":True}
    curve=bpy.data.curves.new(name+"_Editable2D","CURVE")
    curve.dimensions="3D"
    curve.bevel_depth=p.get("thickness",.006)
    curve.bevel_resolution=2
    try:
        for line in p["strokes"]:
            spline=curve.splines.new("POLY")
            spline.points.add(len(line)-1)
            for pt,(x,y) in zip(spline.points,line):
                pt.co=(x,0,y+p.get("z",0),1)
        ob=bpy.data.objects.new(name,curve)
        scene.collection.objects.link(ob)
        mat=bpy.data.materials.new(name+"_Ink")
        mat.diffuse_color=(*p.get("color",[.05,.04,.06]),1)
        curve.materials.append(mat)
        ob["render_benchmark_2d_strokes"]=len(p["strokes"])
        return {"object":ob.name,"editable_strokes":len(curve.splines),
                "native_blender_curve_object":True,
                "Grease_Pencil_v3_parity_claimed":False,
                "actual_2d_ink_geometry_created":True}
    except Exception:
        if curve.users==0:bpy.data.curves.remove(curve)
        raise

def execute(operation,p,root,scene):
    C.validate(operation,p)
    if operation=="studio.benchmark.catalog":return catalog(p)
    if operation=="studio.benchmark.audit":return audit(scene,p)
    if operation=="studio.mesh.bridge_loops":return bridge(scene,p)
    if operation=="studio.procedural.scatter":return scatter(scene,p)
    if operation=="studio.material.surface":return material(scene,p)
    if operation=="studio.motion.action.create":return motion_action(scene,p)
    if operation=="studio.motion.nla.create":return motion_nla(scene,p)
    if operation=="studio.compositor.grade":return compositor(scene,p)
    if operation=="studio.compositor.inspect":return compositor_inspect(scene,p)
    if operation=="studio.sim.rigidbody":return rigidbody(scene,p)
    if operation=="studio.drawing.strokes":return drawing(scene,p)
    raise ValueError("STUDIO_DCC_OPERATION_UNAVAILABLE")
