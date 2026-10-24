# SPDX-License-Identifier: GPL-2.0-or-later
"""Genuine native bpy workspace panels, multi-view geometry audits and motion clips.

Controlled through the existing authenticated production.execute dispatcher.
Never searches Gallery or runs arbitrary operators; never calls the renderer or
claims a single photo supplies hidden geometry. UI split requires live Blender.
"""
import math
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import render_reference_motion_contract as C

OPS=frozenset(("reference.workspace.open","reference.workspace.inspect",
               "reference.compare.multiview","reference.fit.landmarks","reference.fit.multiview","animation.clip.create",
               "animation.clip.inspect","animation.motion.audit"))
READ_ONLY=frozenset(("reference.workspace.inspect","reference.compare.multiview",
                     "animation.clip.inspect","animation.motion.audit"))

def _scene_object(scene,name,kind=None):
    obj=scene.objects.get(C.name(name))
    if obj is None or (kind and obj.type!=kind):
        raise ValueError("NATIVE_OBJECT_NOT_FOUND_OR_WRONG_TYPE")
    return obj

def _window():
    window=bpy.context.window
    if window is None or window.screen is None:
        raise ValueError("NATIVE_BLENDER_WINDOW_REQUIRED")
    return window

def _tagged_reference_editor(window):
    for area in window.screen.areas:
        if area.type!="IMAGE_EDITOR":continue
        image=area.spaces.active.image
        if image and image.get("render_reference_workspace",False):
            return area
    return None

def _split_for_reference(window,factor):
    screen=window.screen
    views=sorted((area for area in screen.areas if area.type=="VIEW_3D"),
                 key=lambda area:area.width,reverse=True)
    if not views:raise ValueError("MODEL_VIEWPORT_REQUIRED")
    source=views[0]
    if source.width<550 or source.height<250:
        raise ValueError("VIEWPORT_TOO_SMALL_FOR_SPLIT_USE_CAMERA_MODE")
    region=next((r for r in source.regions if r.type=="WINDOW"),None)
    if region is None:raise ValueError("MODEL_VIEWPORT_REGION_UNAVAILABLE")
    before={area.as_pointer() for area in screen.areas}
    with bpy.context.temp_override(window=window,screen=screen,area=source,region=region):
        if not bpy.ops.screen.area_split.poll():
            raise ValueError("NATIVE_AREA_SPLIT_UNAVAILABLE")
        outcome=bpy.ops.screen.area_split(direction="VERTICAL",factor=factor)
    if "FINISHED" not in outcome:
        raise RuntimeError("NATIVE_AREA_SPLIT_FAILED")
    created=[area for area in screen.areas if area.as_pointer() not in before]
    if len(created)!=1 or source.type!="VIEW_3D":
        raise RuntimeError("NATIVE_SPLIT_REQUIRES_LIVE_VIEWPORT_INSPECTION")
    area=created[0]
    area.type="IMAGE_EDITOR"
    if area.type!="IMAGE_EDITOR":raise RuntimeError("REFERENCE_EDITOR_NOT_CREATED")
    return area

def _workspace_open(scene,root,p):
    data=C.workspace(p)
    from render_studio_ops import _asset
    source=_asset(Path(root),data["asset"])
    # Video fallback displays a user-sampled original frame when the native
    # video decoder cannot expose movie pixels in Blender's Image Editor.
    preview=_asset(Path(root),data["preview_asset"]) if "preview_asset" in data else source
    if "model" in data:_scene_object(scene,data["model"])
    mode=data["mode"]
    window=None; area=None
    if mode!="CAMERA":
        window=_window()
        if mode=="REUSE":
            area=_tagged_reference_editor(window)
            if area is None:raise ValueError("REFERENCE_EDITOR_NOT_OPEN")
        else:
            area=_tagged_reference_editor(window)
    elif scene.camera is None:
        raise ValueError("CAMERA_REQUIRED")

    try:image=bpy.data.images.load(str(preview),check_existing=True)
    except (RuntimeError,ValueError,OSError) as exc:
        raise ValueError("NATIVE_REFERENCE_DECODER_UNAVAILABLE_USE_SAMPLED_FRAME") from exc
    is_movie=source.suffix.lower()==".mp4"
    preview_movie=preview.suffix.lower()==".mp4"
    if preview_movie and image.source!="MOVIE":
        raise ValueError("NATIVE_MOVIE_PREVIEW_UNAVAILABLE_USE_REFERENCE_SAMPLE")
    if not preview_movie:
        if min(image.size[:2])<1:raise ValueError("REFERENCE_IMAGE_EMPTY")
        if image.packed_file is None:image.pack()
    image["render_reference_workspace"]=True
    image["render_reference_source"]=source.name
    image["render_reference_preview"]=preview.name
    # Do not change the selected object, scene camera, samples, lighting or fps.
    if mode=="CAMERA":
        backgrounds=scene.camera.data.background_images
        old=[bg for bg in backgrounds if bg.image and
             bg.image.get("render_reference_workspace",False)]
        if len(old)>0 and old[0].image==image:
            background=old[0]
        else:
            background=backgrounds.new();background.image=image
        scene.camera.data.show_background_images=True
        background.alpha=.75
        background.display_depth="BACK"
        if preview_movie:
            background.image_user.frame_start=1
            background.image_user.use_auto_refresh=True
        panel="CAMERA_BACKGROUND"
    else:
        if area is None:area=_split_for_reference(window,data["split_factor"])
        area.spaces.active.image=image
        if area.spaces.active.image!=image:
            raise RuntimeError("REFERENCE_EDITOR_IMAGE_NOT_ASSIGNED")
        if preview_movie:
            area.spaces.active.image_user.frame_start=1
            area.spaces.active.image_user.use_auto_refresh=True
        panel="IMAGE_EDITOR"
    if is_movie and "frame" in data:
        scene.frame_set(data["frame"])
    scene["render_compare_source"]=source.name
    scene["render_compare_model"]=data.get("model","")
    scene["render_compare_mode"]=mode
    scene["render_compare_image"]=image.name
    return {"asset":source.name,"mode":mode,"panel":panel,
            "model":data.get("model",None),"image_pixels":list(image.size[:2]),
            "source_kind":"VIDEO" if is_movie else "IMAGE",
            "native_blender_panel_assigned":True,"side_by_side":panel=="IMAGE_EDITOR",
            "original_media_kept":True,"packed_in_blend":not preview_movie,
            "video_original_retained_in_assets":is_movie,
            "video_scrubbing_native":preview_movie,
            "still_frame_sample_used":is_movie and not preview_movie,
            "comparison_preview_asset":preview.name,
            "not_in_final_camera_render":True,
            "scene_render_settings_unchanged":True,"exact_3d_likeness_claimed":False,
            "unseen_geometry_inferred":True}

def _workspace_inspect(scene):
    screens=[]
    window=bpy.context.window
    if window and window.screen:
        for area in window.screen.areas:
            if area.type in ("IMAGE_EDITOR","VIEW_3D"):
                im=area.spaces.active.image if area.type=="IMAGE_EDITOR" else None
                screens.append({"kind":area.type,"width":area.width,"height":area.height,
                    "asset":im.get("render_reference_source",None) if im and
                    im.get("render_reference_workspace",False) else None})
    asset=scene.get("render_compare_source","")
    return {"reference_asset":asset or None,
            "comparison_model":scene.get("render_compare_model","") or None,
            "mode":scene.get("render_compare_mode","") or None,
            "image":scene.get("render_compare_image","") or None,
            "actual_screen_areas":screens,"native_window_available":window is not None,
            "panel_visible":any(a["kind"]=="IMAGE_EDITOR" and a["asset"]==asset for a in screens),
            "active_frame":scene.frame_current,"identity_likeness_verified":False}

def _multi(scene,p):
    C.multiview(p)
    obj=_scene_object(scene,p["object"],"MESH")
    bpy.context.view_layer.update()
    reports=[];sq=[];mmax=0.0
    for view in p["views"]:
        cam=_scene_object(scene,view["camera"],"CAMERA")
        projected={}
        for label,index in view["model"].items():
            if index>=len(obj.data.vertices):raise ValueError("MODEL_LANDMARK_INDEX_OUT_OF_BOUNDS")
            world=obj.matrix_world @ obj.data.vertices[index].co
            uv=world_to_camera_view(scene,cam,world)
            if uv.z<=0 or not (0<=uv.x<=1 and 0<=uv.y<=1):
                raise ValueError("MODEL_POINT_OUTSIDE_REFERENCE_CAMERA")
            projected[label]=[float(uv.x),float(1-uv.y)]
        errors=[]
        for label,reference in view["reference"].items():
            xy=projected[label]
            value=math.dist(xy,reference)
            errors.append(value);sq.append(value*value)
        max_err=max(errors);mmax=max(mmax,max_err)
        reports.append({"camera":cam.name,"label":view.get("label",cam.name),
            "landmarks":len(errors),"rms_normalized_image_error":
            math.sqrt(sum(x*x for x in errors)/len(errors)),
            "max_normalized_image_error":max_err,
            "projected":projected})
    return {"object":obj.name,"views":reports,"total_points":len(sq),
            "overall_rms_normalized_image_error":math.sqrt(sum(sq)/len(sq)),
            "maximum_error":mmax,"metric":"camera-projected 2D landmark distance",
            "unseen_geometry_measured":False,"likeness_percent_available":False,
            "native_mesh_geometry_read":True}

def _fit_landmarks(scene,p):
    C.fit(p)
    obj=_scene_object(scene,p["object"],"MESH")
    cam=_scene_object(scene,p["camera"],"CAMERA")
    if len(obj.data.vertices)!=p["expected_vertices"]:
        raise ValueError("FIT_MESH_REVISION_CONFLICT")
    if obj.data.shape_keys is not None:
        raise ValueError("FIT_BASE_MESH_WITH_SHAPE_KEYS_UNSUPPORTED")
    if cam.data.type not in ("PERSP","ORTHO"):
        raise ValueError("FIT_CAMERA_TYPE_UNSUPPORTED")
    bpy.context.view_layer.update()
    rotation=cam.matrix_world.to_quaternion()
    right=rotation @ Vector((1,0,0))
    up=rotation @ Vector((0,1,0))
    cam_inv=cam.matrix_world.inverted_safe()
    ob_inv=obj.matrix_world.inverted_safe()
    strength=p.get("strength",.5)
    maximum=p.get("max_displacement",.15)
    before=[];after=[];changes=[]
    def image_xy(world):
        n=world_to_camera_view(scene,cam,world)
        if n.z<=0:
            raise ValueError("FIT_LANDMARK_BEHIND_CAMERA")
        return Vector((float(n.x),float(1.0-n.y)))
    for label,target in p["reference"].items():
        index=p["model"][label]
        world=obj.matrix_world @ obj.data.vertices[index].co
        current=image_xy(world)
        goal=Vector(target)
        offset=goal-current
        depth=abs((cam_inv @ world).z)
        epsilon=max(.0001,depth*.001)
        j_r=(image_xy(world+epsilon*right)-current)/epsilon
        j_u=(image_xy(world+epsilon*up)-current)/epsilon
        determinant=j_r.x*j_u.y-j_u.x*j_r.y
        if abs(determinant)<1e-10:
            raise ValueError("FIT_CAMERA_JACOBIAN_DEGENERATE")
        x=(offset.x*j_u.y-offset.y*j_u.x)/determinant
        y=(j_r.x*offset.y-j_r.y*offset.x)/determinant
        step=right*x+up*y
        if step.length>maximum:step=step.normalized()*maximum
        step*=strength
        updated=world+step
        projected=image_xy(updated)
        before.append(offset.length_squared)
        after.append((goal-projected).length_squared)
        changes.append((index,ob_inv@updated,step.length))
    old_rms=math.sqrt(sum(before)/len(before))
    predicted=math.sqrt(sum(after)/len(after))
    if predicted>old_rms+1e-9:
        raise ValueError("FIT_PROPOSED_STEP_WORSENS_PROJECTION")
    if not p.get("dry_run",False) and predicted<old_rms-1e-12:
        if obj.data.users>1:obj.data=obj.data.copy()
        for index,local,step_size in changes:obj.data.vertices[index].co=local
        obj.data.update()
        bpy.context.view_layer.update()
    return {"object":obj.name,"camera":cam.name,
        "landmarks":len(changes),"rms_before":old_rms,"rms_predicted_after":predicted,
        "maximum_vertex_world_displacement":max(x[2] for x in changes),
        "applied":not p.get("dry_run",False) and predicted<old_rms-1e-12,
        "preserved_camera_depth":True,"mesh_density_unchanged":True,
        "automatic_hidden_geometry_reconstruction":False,
        "reference_metric":"normalized 2D projection error; not perceptual likeness",
        "final_render_quality_unchanged":True}

def _linear_solve3(matrix,vector):
    """Bounded 3x3 partial-pivoting Gauss-Jordan; no NumPy dependency."""
    m=[[float(matrix[i][j]) for j in range(3)]+[float(vector[i])]
       for i in range(3)]
    for col in range(3):
        best=max(range(col,3),key=lambda row:abs(m[row][col]))
        if abs(m[best][col])<1e-12:
            raise ValueError("FIT_MULTIVIEW_ILL_CONDITIONED")
        m[col],m[best]=m[best],m[col]
        factor=m[col][col]
        m[col]=[v/factor for v in m[col]]
        for row in range(3):
            if row==col:continue
            factor=m[row][col]
            m[row]=[m[row][j]-factor*m[col][j] for j in range(4)]
    return Vector((m[0][3],m[1][3],m[2][3]))


def _fit_multiview(scene,p):
    """Numerically solve coupled world-space edits against all cameras.

    A reduction of camera-projected landmark RMS is a precise geometric
    measurement, not an identity, beauty or photorealism score. Does not
    create unseen body geometry or change renderer settings.
    """
    C.multiview_fit(p)
    obj=_scene_object(scene,p["object"],"MESH")
    if len(obj.data.vertices)!=p["expected_vertices"]:
        raise ValueError("FIT_MESH_REVISION_CONFLICT")
    if obj.data.shape_keys is not None:
        raise ValueError("FIT_BASE_MESH_WITH_SHAPE_KEYS_UNSUPPORTED")
    bpy.context.view_layer.update()
    cameras={}
    for view in p["views"]:
        camera=_scene_object(scene,view["camera"],"CAMERA")
        if camera.data.type not in ("PERSP","ORTHO"):
            raise ValueError("FIT_CAMERA_TYPE_UNSUPPORTED")
        cameras[view["camera"]]=camera
    directions=[cam.matrix_world.to_quaternion()@Vector((0,0,-1))
                for cam in cameras.values()]
    if max((a-b).length for a in directions for b in directions)<.2:
        raise ValueError("FIT_MULTIVIEW_CAMERA_BASELINE_INSUFFICIENT")
    observations={}
    old_squared=[]
    for view in p["views"]:
        camera=cameras[view["camera"]]
        for label,vertex in view["model"].items():
            old_world=obj.matrix_world @ obj.data.vertices[vertex].co
            target=Vector(view["reference"][label])
            def projection(world,camera=camera):
                ndc=world_to_camera_view(scene,camera,world)
                if ndc.z<=0:
                    raise ValueError("FIT_MULTIVIEW_POINT_BEHIND_CAMERA")
                return Vector((float(ndc.x),float(1.0-ndc.y)))
            before=projection(old_world)
            if not (0<=before.x<=1 and 0<=before.y<=1):
                raise ValueError("FIT_MULTIVIEW_POINT_OUTSIDE_FRAME")
            epsilon=max(.0001,.001*(camera.location-old_world).length)
            basis=(Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
            jac=[(projection(old_world+epsilon*axis)-before)/epsilon
                 for axis in basis]
            residual=target-before
            observations.setdefault(vertex,[]).append(
                {"camera":camera,"label":label,"goal":target,"jac":jac,
                 "residual":residual,"project":projection})
            old_squared.append(residual.length_squared)
    strength=p.get("strength",.65)
    maximum=p.get("max_displacement",.1)
    regularization=p.get("regularization",.005)
    predicted_squared=[];proposed=[]
    inv=obj.matrix_world.inverted_safe()
    for vertex,values in observations.items():
        world=obj.matrix_world @ obj.data.vertices[vertex].co
        matrix=[[0.0]*3 for _ in range(3)]
        right=[0.0]*3
        for value in values:
            jac=value["jac"]
            residual=value["residual"]
            for r,needed in enumerate((residual.x,residual.y)):
                gradient=[jac[c][r] for c in range(3)]
                for i in range(3):
                    right[i]+=gradient[i]*needed
                    for j in range(3):
                        matrix[i][j]+=gradient[i]*gradient[j]
        diag=(matrix[0][0]+matrix[1][1]+matrix[2][2])/3
        penalty=max(1e-9,diag*regularization)
        for i in range(3):matrix[i][i]+=penalty
        delta=_linear_solve3(matrix,right)
        if delta.length>maximum:delta=delta.normalized()*maximum
        delta*=strength
        future=world+delta
        for value in values:
            predicted=(value["goal"]-value["project"](future))
            predicted_squared.append(predicted.length_squared)
        proposed.append((vertex,inv@future,float(delta.length)))
    rms_before=math.sqrt(sum(old_squared)/len(old_squared))
    rms_predicted=math.sqrt(sum(predicted_squared)/len(predicted_squared))
    if rms_predicted>rms_before+1e-9:
        raise ValueError("FIT_MULTIVIEW_PROPOSED_STEP_WORSENS_ERROR")
    applied=(not p.get("dry_run",False) and rms_predicted<rms_before-1e-12)
    if applied:
        if obj.data.users>1:obj.data=obj.data.copy()
        for vertex,position,step in proposed:
            obj.data.vertices[vertex].co=position
        obj.data.update()
        bpy.context.view_layer.update()
    return {
        "object":obj.name,"views":len(p["views"]),"updated_vertices":len(proposed),
        "observations":len(old_squared),
        "rms_before":rms_before,"rms_predicted_after":rms_predicted,
        "maximum_vertex_world_displacement":max(step for _,_,step in proposed),
        "applied":applied,"dry_run":p.get("dry_run",False),
        "unmapped_vertices_unchanged":True,"topology_preserved":True,
        "metric":"joint camera-projected 2D landmark distance, not identity likeness",
        "photorealism_verified":False,"phone_hardware_tested":False}

def _action_curves(action,slot):
    result=[]
    try:result=list(action.fcurves)
    except (AttributeError,RuntimeError,TypeError):pass
    if result:return result
    for layer in getattr(action,"layers",[]):
        for strip in getattr(layer,"strips",[]):
            if not hasattr(strip,"channelbag") or slot is None:continue
            try:bag=strip.channelbag(slot,ensure=False)
            except (TypeError,RuntimeError,AttributeError):continue
            if bag:result.extend(list(bag.fcurves))
    return result

def _key_bone(posebone,b):
    rotation="rotation_quaternion" if "rotation_quaternion" in b else "rotation_euler"
    if "rotation_quaternion" in b:posebone.rotation_mode="QUATERNION"
    elif "rotation_euler" in b:posebone.rotation_mode="XYZ"
    for path in ("location","rotation_euler","rotation_quaternion","scale"):
        if path not in b:continue
        setattr(posebone,path,b[path])
        if not posebone.keyframe_insert(data_path=path,frame=posebone.id_data.get("render_motion_frame",1),
                                        group=posebone.name):
            raise RuntimeError("POSE_KEYFRAME_INSERT_FAILED")

def _set_interpolation(owner,interpolation):
    ad=owner.animation_data
    if ad is None or ad.action is None:raise RuntimeError("MOTION_ACTION_NOT_CREATED")
    action=ad.action
    curves=_action_curves(action,getattr(ad,"action_slot",None))
    if not curves:raise RuntimeError("ACTION_CURVES_NOT_DISCOVERABLE")
    total=0
    for curve in curves:
        for key in curve.keyframe_points:
            key.interpolation=interpolation
            if key.interpolation!=interpolation:
                raise RuntimeError("NATIVE_INTERPOLATION_NOT_APPLIED")
            total+=1
        curve.update()
    return action,total

def _nla(owner,name,action,start,track_name):
    ad=owner.animation_data
    slot=getattr(ad,"action_slot",None)
    track=ad.nla_tracks.new();track.name=track_name
    strip=track.strips.new(name,start,action)
    if hasattr(strip,"action_slot") and slot is not None:strip.action_slot=slot
    strip.blend_type="REPLACE"
    ad.action=None
    return {"track":track.name,"strip":strip.name,"start_frame":strip.frame_start,
            "end_frame":strip.frame_end}

def _clip_create(scene,p):
    C.clip(p)
    rig=_scene_object(scene,p["rig"],"ARMATURE")
    if p["name"] in bpy.data.actions:raise ValueError("MOTION_ACTION_NAME_EXISTS")
    if rig.animation_data and rig.animation_data.action is not None:
        raise ValueError("RIG_HAS_ACTIVE_ACTION_STASH_BEFORE_NEW_CLIP")
    objects={}
    for pose in p["poses"]:
        for item in pose.get("bones",[]):
            if item["bone"] not in rig.pose.bones:
                raise ValueError("MOTION_POSE_BONE_NOT_FOUND")
        for s in pose.get("shapes",[]):
            obj=_scene_object(scene,s["object"],"MESH")
            keys=obj.data.shape_keys
            if not keys or not keys.key_blocks.get(s["key"]):
                raise ValueError("MOTION_SHAPE_KEY_MISSING")
            if keys.animation_data and keys.animation_data.action is not None:
                raise ValueError("SHAPE_KEY_HAS_ACTIVE_ACTION_STASH_FIRST")
            objects[s["object"]]=keys
    initial=scene.frame_current
    rig.animation_data_create()
    keyed_bones=0;keyed_shapes=0
    try:
        for pose in p["poses"]:
            frame=pose["frame"]
            scene.frame_set(frame)
            for item in pose.get("bones",[]):
                bone=rig.pose.bones[item["bone"]]
                if "rotation_quaternion" in item:bone.rotation_mode="QUATERNION"
                elif "rotation_euler" in item:bone.rotation_mode="XYZ"
                for prop in ("location","rotation_euler","rotation_quaternion","scale"):
                    if prop in item:
                        setattr(bone,prop,item[prop])
                        if not bone.keyframe_insert(data_path=prop,frame=frame,group=bone.name):
                            raise RuntimeError("NATIVE_BONE_KEY_INSERT_FAILED")
                        keyed_bones+=1
            for shape in pose.get("shapes",[]):
                keys=objects[shape["object"]]
                block=keys.key_blocks[shape["key"]]
                block.value=shape["value"]
                if not block.keyframe_insert(data_path="value",frame=frame):
                    raise RuntimeError("NATIVE_SHAPE_KEY_INSERT_FAILED")
                keyed_shapes+=1
        action,bone_points=_set_interpolation(rig,p.get("interpolation","BEZIER"))
        action.name=p["name"]
        shape_actions=[]
        for obj_name,keys in objects.items():
            existing,points=_set_interpolation(keys,p.get("interpolation","BEZIER"))
            existing.name=p["name"]+"_Face_"+obj_name
            shape_actions.append({"object":obj_name,"action":existing.name,
                                  "keyframe_points":points})
        nla_tracks=[]
        if p.get("nla",False):
            first=p["poses"][0]["frame"]
            nla_tracks.append(_nla(rig,p["name"],action,first,p.get("track",p["name"])))
            for obj_name,keys in objects.items():
                an=keys.animation_data.action
                nla_tracks.append(_nla(keys,an.name,an,first,p.get("track",p["name"])))
        return {"rig":rig.name,"clip_action":action.name,
            "pose_frames":[pose["frame"] for pose in p["poses"]],
            "bone_channels_keyed":keyed_bones,"shape_channels_keyed":keyed_shapes,
            "bone_keyframe_points":bone_points,"facial_actions":shape_actions,
            "interpolation":p.get("interpolation","BEZIER"),"nla_strips":nla_tracks,
            "real_blender_keyframes_inserted":True,
            "motion_smoothness_visually_verified":False,"native_render_created":False}
    finally:
        scene.frame_set(initial)

def _clip_inspect(scene,p):
    C.fields(p,("rig",))
    names=[p["rig"]] if "rig" in p else [o.name for o in scene.objects if o.type=="ARMATURE"][:24]
    result=[]
    for name in names:
        rig=_scene_object(scene,name,"ARMATURE")
        ad=rig.animation_data
        active=ad.action if ad else None
        tracks=[]
        for track in (ad.nla_tracks if ad else []):
            tracks.append({"track":track.name,"mute":track.mute,
                           "strips":[{"name":s.name,"action":s.action.name if s.action else None,
                                      "start":float(s.frame_start),"end":float(s.frame_end)}
                                     for s in track.strips][:64]})
        actions=[]
        if active:
            actions.append({"name":active.name,"keyframe_points":sum(len(c.keyframe_points)
                  for c in _action_curves(active,getattr(ad,"action_slot",None)))})
        result.append({"rig":rig.name,"active_actions":actions,"nla_tracks":tracks,
                       "pose_bones":len(rig.pose.bones)})
    return {"rigs":result,"scene_frame":scene.frame_current,
            "graph_editor_opened":False,"samples_rendered":False}

def _motion_audit(scene,p):
    C.audit(p)
    rig=_scene_object(scene,p["rig"],"ARMATURE")
    for name in p["bones"]:
        if name not in rig.pose.bones:raise ValueError("MOTION_POSE_BONE_NOT_FOUND")
    frame_before=scene.frame_current
    tracks={name:[] for name in p["bones"]}
    try:
        for frame in p["frames"]:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            for name in p["bones"]:
                position=rig.matrix_world @ rig.pose.bones[name].head
                tracks[name].append([float(x) for x in position])
    finally:scene.frame_set(frame_before)
    return {"rig":rig.name,"sampled_frames":p["frames"],
        "trajectories":[{"bone":name,"positions_world":coordinates,
            "total_path_distance":sum(math.dist(a,b) for a,b in
                                      zip(coordinates,coordinates[1:])),
            "maximum_step_distance":max(math.dist(a,b) for a,b in
                                        zip(coordinates,coordinates[1:]))}
             for name,coordinates in tracks.items()],
        "frame_restored":scene.frame_current==frame_before,
        "native_pose_evaluated":True,"renders_verified":False,
        "actual_path_data_not_fake_visual_trails":True}

def execute(op,p,root,scene):
    if op not in OPS:raise ValueError("REFERENCE_MOTION_OPERATION_UNAVAILABLE")
    if op=="reference.workspace.open":return _workspace_open(scene,root,p)
    if op=="reference.workspace.inspect":
        C.fields(p,());return _workspace_inspect(scene)
    if op=="reference.compare.multiview":return _multi(scene,p)
    if op=="reference.fit.landmarks":return _fit_landmarks(scene,p)
    if op=="reference.fit.multiview":return _fit_multiview(scene,p)
    if op=="animation.clip.create":return _clip_create(scene,p)
    if op=="animation.clip.inspect":return _clip_inspect(scene,p)
    if op=="animation.motion.audit":return _motion_audit(scene,p)
    raise ValueError("REFERENCE_MOTION_OPERATION_UNAVAILABLE")
