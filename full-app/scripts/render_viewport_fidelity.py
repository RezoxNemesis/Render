# SPDX-License-Identifier: GPL-2.0-or-later
"""Blender-native viewport fidelity and evidence-based "shattered" mesh checks.

Read-only diagnostics can run headless. Actual preview profiles require
VIEW_3D and change only its shading, overlay and clipping properties.
No mesh, material, camera, final render settings or texture bytes are changed.
"""
from collections import defaultdict
import math
import time

import bpy
from mathutils import Vector
import render_viewport_fidelity_contract as C

_SAVED_VIEWS={}
_SAVED_AA=None
_SAVED_SAMPLING={}

_SHADING=(
 "type","light","color_type","show_shadows","show_cavity",
 "cavity_type","curvature_ridge_factor","curvature_valley_factor",
 "show_specular_highlight","show_xray","show_xray_wireframe",
 "show_backface_culling","show_object_outline",
)
_OVERLAY=("show_wireframes","show_relationship_lines","show_extras")
_SPACE=("clip_start","clip_end","lens")

def _views():
    # Blender headless may expose a startup screen and 3D area even though
    # no actual GPU viewport/window is ever drawn. Never claim visual
    # success from that phantom context.
    if getattr(bpy.app,"background",False):
        return []
    window=bpy.context.window
    if window is None or not window.screen:return []
    return [a for a in window.screen.areas if a.type=="VIEW_3D"]

def _view(idx=0,required=True):
    areas=_views()
    if len(areas)<=idx:
        if required:raise ValueError("STUDIO_PREVIEW_NATIVE_3D_VIEW_UNAVAILABLE")
        return None
    return areas[idx]

def _values(obj,fields):
    result={}
    for f in fields:
        try:
            v=getattr(obj,f)
            if type(v) in (str,bool,int,float) and (
                    not isinstance(v,float) or math.isfinite(v)):
                result[f]=v
        except (AttributeError,RuntimeError,TypeError):pass
    return result

def _state(area):
    space=area.spaces.active
    return {"shading":_values(space.shading,_SHADING),
            "overlay":_values(space.overlay,_OVERLAY),
            "view":_values(space,_SPACE)}

def _rev(area):
    return C.digest(_state(area))

def _set(owner,name,value,changes):
    if not hasattr(owner,name):
        return False
    try:
        prior=getattr(owner,name)
        if prior==value:return True
        setattr(owner,name,value)
        after=getattr(owner,name)
        if (isinstance(value,float) and abs(float(after)-value)>1e-4) or (
                not isinstance(value,float) and after!=value):
            raise ValueError("STUDIO_PREVIEW_SETTING_CLAMPED")
        changes.append(name)
        return True
    except (TypeError,AttributeError,RuntimeError) as exc:
        raise ValueError("STUDIO_PREVIEW_SETTING_UNAVAILABLE") from exc

def _restore(area,snapshot):
    space=area.spaces.active
    changed=[]
    for owner,props in ((space.shading,snapshot["shading"]),
                        (space.overlay,snapshot["overlay"]),
                        (space,snapshot["view"])):
        for field,value in props.items():
            _set(owner,field,value,changed)
    area.tag_redraw()
    return changed

def _aabb(ob):
    try:
        coords=[ob.matrix_world@Vector(corner) for corner in ob.bound_box]
        if not all(math.isfinite(x) for coord in coords for x in coord):
            return None
        mins=Vector(tuple(min(p[i] for p in coords) for i in range(3)))
        maxs=Vector(tuple(max(p[i] for p in coords) for i in range(3)))
        # Empty/non-mesh bounding box may contain all -1 values.
        if (maxs-mins).length<=1e-9:return None
        return coords,mins,maxs
    except (AttributeError,RuntimeError,ValueError,TypeError):return None

def _projected_bbox(area,ob):
    bounds=_aabb(ob)
    if bounds is None:return None
    region=next((r for r in area.regions if r.type=="WINDOW"),None)
    if region is None:return None
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    projected=[]
    for coord in bounds[0]:
        point=location_3d_to_region_2d(region,area.spaces.active.region_3d,coord)
        if point is not None and all(math.isfinite(float(v)) for v in point):
            projected.append([float(point.x),float(point.y)])
    if not projected:return None
    xmin=min(p[0] for p in projected);xmax=max(p[0] for p in projected)
    ymin=min(p[1] for p in projected);ymax=max(p[1] for p in projected)
    return {"pixels_x":round(xmax-xmin,2),"pixels_y":round(ymax-ymin,2),
            "viewport_pixels_x":int(region.width),
            "viewport_pixels_y":int(region.height),
            "screen_coverage_x":round((xmax-xmin)/max(1,region.width),4),
            "screen_coverage_y":round((ymax-ymin)/max(1,region.height),4),
            "measurement":"projected_world_bbox_not_rendered_surface_pixels"}

def _materials(ob):
    results=[]
    for slot in ob.material_slots[:16]:
        material=slot.material
        if material is None:continue
        issues=[]
        blend=getattr(material,"blend_method",None)
        if blend in ("BLEND","HASHED","DITHERED"):
            issues.append("TRANSPARENT_BLEND_MODE")
        method=getattr(material,"surface_render_method",None)
        if method=="BLENDED":
            issues.append("BLENDED_SURFACE")
        try:
            if float(material.diffuse_color[3])<.98:
                issues.append("MATERIAL_ALPHA_BELOW_ONE")
        except (AttributeError,TypeError):pass
        imgs=[]
        if material.use_nodes and material.node_tree:
            for node in material.node_tree.nodes:
                if node.type=="BSDF_PRINCIPLED":
                    alpha=node.inputs.get("Alpha")
                    if alpha is not None and not alpha.is_linked and (
                            type(alpha.default_value) in (int,float) and
                            alpha.default_value<.98):
                        issues.append("PRINCIPLED_ALPHA_BELOW_ONE")
                if node.type=="TEX_IMAGE" and node.image is not None:
                    image=node.image
                    size=tuple(int(x) for x in image.size[:2])
                    imgs.append({"image":image.name[:80],"pixels":size,
                                 "loaded":bool(image.has_data),
                                 "low_resolution":min(size)<512,
                                 "missing_or_empty":min(size)<1})
                    if len(imgs)>=8:break
        results.append({"material":material.name[:80],
                        "blend_method":blend,
                        "surface_render_method":method,
                        "issues":sorted(set(issues)),"textures":imgs})
    return results

def _overlap_candidates(scene,target,limit):
    """Evidence of near identical mesh surfaces; no destructive mesh cleanup."""
    if target.type!="MESH":return []
    matching=[]
    base=_aabb(target)
    if base is None:return matching
    for other in scene.objects:
        if other==target or other.type!="MESH":continue
        if len(matching)>=12:break
        if limit<=0:break
        limit-=1
        identical_matrices=all(
            abs(a-b)<1e-5 for row_a,row_b in zip(
                target.matrix_world,other.matrix_world)
            for a,b in zip(row_a,row_b))
        if not identical_matrices:continue
        if target.data==other.data:
            matching.append({"object":other.name[:80],
                             "evidence":"same_mesh_data_and_transform",
                             "confidence":"high",
                             "geometry_deleted":False})
            continue
        if (len(target.data.vertices)!=len(other.data.vertices)
                or len(target.data.polygons)!=len(other.data.polygons)):
            continue
        checked=min(32,len(target.data.vertices))
        if checked==0:continue
        if all((target.data.vertices[i].co-
                other.data.vertices[i].co).length<1e-5
               for i in range(checked)):
            matching.append({"object":other.name[:80],
                             "evidence":"identical_transform_and_first_32_vertices",
                             "confidence":"possible",
                             "geometry_deleted":False})
    return matching

def inspect(scene,p):
    C.validate("studio.preview.inspect",p)
    idx=p.get("viewport_index",0)
    area=_view(idx,required=False)
    if area is None:
        return {"native_viewport_available":False,
                "viewport_index":idx,
                "available_viewports":len(_views()),
                "engine":scene.render.engine,
                "render_quality_modified":False,
                "native_draw_unverified":True,
                "reason":"BLENDER_3D_WINDOW_NOT_RUNNING"}
    state=_state(area)
    return {"native_viewport_available":True,
            "viewport_index":idx,
            "available_viewports":len(_views()),
            "area_pixels":{"width":area.width,"height":area.height},
            "state":state,
            "revision_sha256":C.digest(state),
            "engine":scene.render.engine,
            "profile_original_snapshot_available":area.as_pointer() in _SAVED_VIEWS,
            "native_viewport_state_read_from_bpy":True,
            "final_render_quality_modified":False}

def diagnose(scene,p):
    C.validate("studio.preview.diagnose",p)
    idx=p.get("viewport_index",0)
    area=_view(idx,required=False)
    name=p.get("object")
    if name is None:
        active=bpy.context.view_layer.objects.active
        if active and active.name in scene.objects:name=active.name
    if name is None or name not in scene.objects:
        return {"object_found":False,
                "reason":"SELECT_OR_SUPPLY_ACTUAL_SCENE_OBJECT",
                "native_viewport_available":area is not None,
                "diagnosed_without_geometry_mutation":True}
    ob=scene.objects[name]
    issues=[]
    scale=[float(v) for v in ob.scale]
    non_uniform=(
        max(abs(x) for x in scale)>0 and
        max(abs(x) for x in scale)-min(abs(x) for x in scale)>0.015*
            max(abs(x) for x in scale))
    if non_uniform:issues.append("NON_UNIFORM_OBJECT_SCALE")
    if ob.matrix_world.determinant()<0:issues.append("NEGATIVE_TRANSFORM_DETERMINANT")
    alpha=_materials(ob) if ob.type=="MESH" else []
    if any(row["issues"] for row in alpha):
        issues.append("TRANSPARENT_OR_MIXED_ALPHA_MATERIAL")
    small_textures=[img["image"] for row in alpha for img in row["textures"]
                    if img["low_resolution"] or img["missing_or_empty"]][:12]
    if small_textures:issues.append("SMALL_OR_MISSING_TEXTURE_IMAGES")
    duplicates=_overlap_candidates(scene,ob,p.get("max_candidates",512))
    if duplicates:issues.append("NEAR_COINCIDENT_MESHES_POSSIBLE_Z_FIGHTING")
    meshdata={}
    if ob.type=="MESH":
        mesh=ob.data
        faces=len(mesh.polygons)
        smooth=sum(bool(p.use_smooth) for p in mesh.polygons) if faces<=200000 else None
        meshdata={"vertices":len(mesh.vertices),"polygons":faces,
                  "smooth_polygons":smooth,
                  "smooth_fraction":round(smooth/faces,3) if smooth is not None and faces else None,
                  "mesh_users":mesh.users,
                  "modifiers":[m.type for m in ob.modifiers][:12],
                  "dense_geometry_full_scan_omitted":faces>200000}
        if faces>0 and smooth==0:issues.append("FLAT_SHADED_FACES_VISIBLE")
    area_info=None
    projected=_projected_bbox(area,ob) if area is not None else None
    if area is not None:
        space=area.spaces.active
        ratio=float(space.clip_end)/max(1e-12,float(space.clip_start))
        if ratio>100000:
            issues.append("VERY_LARGE_VIEWPORT_DEPTH_RANGE")
        if getattr(space.shading,"show_xray",False):
            issues.append("XRAY_TRANSPARENCY_ENABLED")
        if getattr(space.overlay,"show_wireframes",False):
            issues.append("WIREFRAME_OVERLAY_ENABLED")
        if projected and max(projected["pixels_x"],projected["pixels_y"])<145:
            issues.append("MODEL_TOO_SMALL_ON_SCREEN_FOR_FACE_DETAIL")
        area_info={"viewport_index":idx,
                   "depth_clip_ratio":round(ratio,1),
                   "shading_type":space.shading.type,
                   "show_xray":bool(getattr(space.shading,"show_xray",False)),
                   "show_wireframes":bool(getattr(space.overlay,"show_wireframes",False))}
    return {"object_found":True,"object":ob.name,"object_type":ob.type,
            "issues":sorted(set(issues)),
            "issue_count":len(set(issues)),
            "object_scale":scale,"materials":alpha,
            "small_or_missing_texture_names":small_textures,
            "overlap_candidates":duplicates,"mesh":meshdata,
            "screen_projection":projected,"viewport":area_info,
            "diagnosis_limit":"Evidence-based flags: does not prove GPU-driver tearing, z-fighting, hidden duplicates or model likeness",
            "reported_pixel_quality_not_increased_by_inspection":True,
            "geometry_modified":False,"material_modified":False,
            "final_render_settings_modified":False}

def _apply_changes(space,profile,changes):
    shading=space.shading;overlay=space.overlay
    if profile=="MATERIAL_REVIEW":
        _set(shading,"type","MATERIAL",changes)
    else:
        _set(shading,"type","SOLID",changes)
        _set(shading,"light","STUDIO",changes)
        _set(shading,"color_type","MATERIAL",changes)
    _set(shading,"show_xray",False,changes)
    _set(overlay,"show_wireframes",profile=="SURFACE_DEBUG",changes)
    if hasattr(shading,"show_xray_wireframe"):
        _set(shading,"show_xray_wireframe",False,changes)
    if hasattr(shading,"show_backface_culling"):
        _set(shading,"show_backface_culling",False,changes)
    if profile!="MATERIAL_REVIEW":
        detail=profile in ("DETAIL_INSPECT","SURFACE_DEBUG")
        _set(shading,"show_cavity",detail,changes)
        _set(shading,"show_shadows",profile not in ("LOW_NOISE","SURFACE_DEBUG"),changes)
        if detail and hasattr(shading,"cavity_type"):
            _set(shading,"cavity_type","BOTH",changes)
        if profile=="DETAIL_INSPECT":
            if hasattr(shading,"curvature_ridge_factor"):
                _set(shading,"curvature_ridge_factor",1.25,changes)
            if hasattr(shading,"curvature_valley_factor"):
                _set(shading,"curvature_valley_factor",1.0,changes)

def _target_precision(space,scene,name,changes):
    obj=scene.objects.get(name)
    if obj is None:raise ValueError("STUDIO_PREVIEW_TARGET_NOT_IN_SCENE")
    bounds=_aabb(obj)
    if bounds is None:raise ValueError("STUDIO_PREVIEW_BOUNDS_INVALID")
    diagonal=max(.001,(bounds[2]-bounds[1]).length)
    # Applies ONLY to this view, not Blender cameras or actual world scale.
    near=max(.001,diagonal/1800)
    far=max(10.0,diagonal*45)
    near=max(near,far/50000.0)
    far=min(far,1000000.0)
    if far<=near*20:
        raise ValueError("STUDIO_PREVIEW_CLIP_SPAN_INVALID")
    _set(space,"clip_end",far,changes)
    _set(space,"clip_start",near,changes)
    return {"focus_object":name,"clip_near":float(space.clip_start),
            "clip_far":float(space.clip_end),
            "other_scene_objects_may_be_clipped":True,
            "native_camera_clip_unchanged":True}

def apply(scene,p):
    C.validate("studio.preview.profile.apply",p)
    area=_view(p.get("viewport_index",0))
    before=_state(area)
    prior=C.digest(before)
    if p.get("expected_sha256") and p["expected_sha256"]!=prior:
        raise ValueError("STUDIO_PREVIEW_REVISION_CONFLICT")
    key=area.as_pointer()
    original=_SAVED_VIEWS.get(key)
    changes=[]
    target=None
    try:
        _apply_changes(area.spaces.active,p["profile"],changes)
        if p.get("precision_target_clipping"):
            target=_target_precision(area.spaces.active,scene,p["object"],changes)
        area.tag_redraw()
        post=_state(area)
    except Exception:
        try:_restore(area,before)
        except Exception:pass
        raise
    if original is None:_SAVED_VIEWS[key]=before
    return {"profile":p["profile"],"changed_native_fields":changes,
            "native_preview_changed":bool(changes),
            "revision_before_sha256":prior,
            "revision_after_sha256":C.digest(post),
            "saved_original_in_memory":True,
            "restore_requires_same_blender_window":True,
            "viewport_index":p.get("viewport_index",0),
            "target_precision":target,
            "native_engine":scene.render.engine,
            "geometry_modified":False,"materials_modified":False,
            "final_render_samples_modified":False,
            "user_film_resolution_modified":False,
            "GPU_driver_shattering_fixed_claimed":False}

def restore(scene,p):
    C.validate("studio.preview.profile.restore",p)
    area=_view(p.get("viewport_index",0))
    key=area.as_pointer()
    original=_SAVED_VIEWS.get(key)
    if original is None:raise ValueError("STUDIO_PREVIEW_NO_SAVED_ORIGINAL")
    sha=_rev(area)
    if p.get("expected_sha256") and p["expected_sha256"]!=sha:
        raise ValueError("STUDIO_PREVIEW_REVISION_CONFLICT")
    changes=_restore(area,original)
    _SAVED_VIEWS.pop(key,None)
    return {"restored_actual_blender_view":True,
            "revision_before_sha256":sha,"revision_after_sha256":_rev(area),
            "native_fields_restored":changes,
            "geometry_modified":False,
            "final_render_samples_modified":False}

def _aa_info():
    prefs=bpy.context.preferences
    system=getattr(prefs,"system",None)
    if system is None or not hasattr(system,"viewport_aa"):
        return {"available":False,"reason":"NATIVE_VIEWPORT_AA_PROPERTY_MISSING"}
    items=[]
    try:
        prop=system.bl_rna.properties["viewport_aa"]
        items=[item.identifier for item in prop.enum_items]
    except (KeyError,TypeError,AttributeError):pass
    return {"available":True,"native_current":system.viewport_aa,
            "native_supported_values":items,
            "global_all_viewports_preference":True,
            "auto_highest_setting_not_chosen_silently":True}

def aa_inspect(p):
    C.validate("studio.preview.aa.inspect",p)
    result=_aa_info()
    result["original_preference_snapshot_available"]=_SAVED_AA is not None
    result["must_opt_in_to_edit_global_preference"]=True
    return result

def aa_configure(p):
    global _SAVED_AA
    C.validate("studio.preview.aa.configure",p)
    info=_aa_info()
    if not info["available"]:
        raise ValueError("STUDIO_PREVIEW_GLOBAL_AA_UNSUPPORTED_BY_BLENDER")
    system=bpy.context.preferences.system
    current=system.viewport_aa
    values=info["native_supported_values"]
    if p.get("restore",False):
        if _SAVED_AA is None:raise ValueError("STUDIO_PREVIEW_NO_SAVED_AA")
        requested=_SAVED_AA
    else:
        requested=p["level"]
        if requested=="BEST_SUPPORTED":
            requested=next((x for x in ("16","8","FXAA","5") if x in values),None)
            if requested is None:
                raise ValueError("STUDIO_PREVIEW_NO_ADMITTED_AA_PRESET")
        if requested not in values:
            raise ValueError("STUDIO_PREVIEW_AA_LEVEL_UNSUPPORTED")
    if _SAVED_AA is None and not p.get("restore",False):_SAVED_AA=current
    system.viewport_aa=requested
    if system.viewport_aa!=requested:
        raise ValueError("STUDIO_PREVIEW_AA_NOT_APPLIED")
    if p.get("restore",False):_SAVED_AA=None
    for area in _views():area.tag_redraw()
    return {"actual_native_aa_previous":current,
            "actual_native_aa":system.viewport_aa,
            "original_setting_restored":bool(p.get("restore")),
            "affects_all_blender_viewports":True,
            "final_render_samples_modified":False,
            "GPU_driver_compatibility_not_verified_on_Android":True}

def _sampling_owner(scene):
    engine=scene.render.engine
    if engine=="CYCLES":
        settings=getattr(scene,"cycles",None)
        if settings is not None and hasattr(settings,"preview_samples"):
            return settings,"preview_samples","CYCLES_VIEWPORT"
    if engine in ("BLENDER_EEVEE","BLENDER_EEVEE_NEXT"):
        settings=getattr(scene,"eevee",None)
        if settings is not None and hasattr(settings,"taa_samples"):
            return settings,"taa_samples","EEVEE_VIEWPORT_TAA"
    return None,None,"UNSUPPORTED_NATIVE_ENGINE"

def sampling_inspect(scene,p):
    C.validate("studio.preview.sampling.inspect",p)
    owner,field,mode=_sampling_owner(scene)
    if owner is None:
        return {"native_preview_sample_setting_available":False,
                "mode":mode,"render_engine":scene.render.engine,
                "reason":"NATIVE_VIEWPORT_SAMPLE_PROPERTY_NOT_EXPOSED",
                "render_output_sample_setting_changed":False}
    current=getattr(owner,field)
    return {"native_preview_sample_setting_available":True,
            "mode":mode,"render_engine":scene.render.engine,
            "setting":field,
            "native_samples":int(current),
            "original_same_process_restore_available":scene.as_pointer() in _SAVED_SAMPLING,
            "explicit_high_gpu_load_opt_in_required_above":32,
            "final_render_sample_setting_unchanged":True}

def sampling_configure(scene,p):
    C.validate("studio.preview.sampling.configure",p)
    owner,field,mode=_sampling_owner(scene)
    if owner is None:
        raise ValueError("STUDIO_PREVIEW_SAMPLING_NOT_SUPPORTED_BY_CURRENT_ENGINE")
    key=scene.as_pointer()
    old=_SAVED_SAMPLING.get(key)
    if p.get("restore",False):
        if old is None:
            raise ValueError("STUDIO_PREVIEW_NO_SAVED_SAMPLING_PROFILE")
        if old[0]!=mode or old[1]!=field:
            raise ValueError("STUDIO_PREVIEW_SAMPLING_ENGINE_CHANGED")
        value=old[2]
    else:value=p["samples"]
    prior=int(getattr(owner,field))
    # A change to Cycles.preview_samples does not change Cycles.samples;
    # Eevee.taa_samples does not change Eevee.taa_render_samples.
    native_final=(getattr(scene.cycles,"samples",None)
                  if mode=="CYCLES_VIEWPORT" else
                  getattr(getattr(scene,"eevee",None),"taa_render_samples",None))
    try:
        setattr(owner,field,int(value))
        actual=int(getattr(owner,field))
        if actual!=int(value):
            raise ValueError("STUDIO_PREVIEW_NATIVE_SAMPLES_CLAMPED")
        post_final=(getattr(scene.cycles,"samples",None)
                    if mode=="CYCLES_VIEWPORT" else
                    getattr(getattr(scene,"eevee",None),"taa_render_samples",None))
        if post_final!=native_final:
            raise ValueError("STUDIO_PREVIEW_FINAL_SAMPLES_CHANGED")
    except Exception:
        try:setattr(owner,field,prior)
        except Exception:pass
        raise
    if p.get("restore",False):
        _SAVED_SAMPLING.pop(key,None)
    elif old is None:
        _SAVED_SAMPLING[key]=(mode,field,prior)
    for area in _views():area.tag_redraw()
    return {"mode":mode,"render_engine":scene.render.engine,
            "sample_control":field,"samples_before":prior,"samples_after":actual,
            "original_restored":bool(p.get("restore",False)),
            "high_gpu_load_explicitly_approved":bool(p.get("allow_high_gpu_load",False)),
            "scene_viewport_setting_modified":prior!=actual,
            "final_render_samples_modified":False,
            "actual_device_gpu_speed_not_verified":True}

def capabilities(p):
    C.validate("studio.preview.capabilities",p)
    gpu={"backend":"unknown","probe_success":False}
    try:
        import gpu as blender_gpu
        platform=getattr(blender_gpu,"platform",None)
        if platform and hasattr(platform,"backend_type_get"):
            gpu={"backend":str(platform.backend_type_get()),
                 "probe_success":True}
    except (ImportError,RuntimeError,AttributeError,SystemError):pass
    return {"operations":C.capabilities(),
            "profiles":list(C.PROFILES),"blender_version":bpy.app.version_string,
            "gpu":gpu,"running_view3d_areas":len(_views()),
            "native_global_aa_available":_aa_info()["available"],
            "native_viewport_sampling":sampling_inspect(bpy.context.scene,{}),
            "core_engine_replaced":False,
            "commercial_DCC_capability_parity_claimed":False,
            "texture_or_mesh_reconstruction_available":False,
            "original_render_settings_preserved":True}

def execute(op,p,root,scene):
    if op=="studio.preview.capabilities":return capabilities(p)
    if op=="studio.preview.inspect":return inspect(scene,p)
    if op=="studio.preview.diagnose":return diagnose(scene,p)
    if op=="studio.preview.profile.apply":return apply(scene,p)
    if op=="studio.preview.profile.restore":return restore(scene,p)
    if op=="studio.preview.aa.inspect":return aa_inspect(p)
    if op=="studio.preview.aa.configure":return aa_configure(p)
    if op=="studio.preview.sampling.inspect":return sampling_inspect(scene,p)
    if op=="studio.preview.sampling.configure":return sampling_configure(scene,p)
    raise ValueError("STUDIO_PREVIEW_OPERATION_UNAVAILABLE")
