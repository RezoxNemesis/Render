# SPDX-License-Identifier: GPL-2.0-or-later
"""Native render preparation and revision-checked action retiming.

These tools prepare the existing render.plan/render.step/render.encode pipeline.
They do not introduce a second renderer, start jobs, or change saved job snapshots.
"""
import hashlib
import json
import math
from pathlib import Path
import struct

import bpy
import render_animation_finish_contract as C
import render_execution_settings as Settings


def _problem(code, message):
    return {"code": code, "message": message}


def _scene_images(scene):
    """Walk current-scene shader/compositor groups, images and camera backgrounds."""
    images, trees, seen = {}, [], set()
    if getattr(scene, "node_tree", None):
        trees.append(scene.node_tree)
    # Blender 5 moves compositor data onto a node group.
    if getattr(scene, "compositing_node_group", None):
        trees.append(scene.compositing_node_group)
    if scene.world is not None and scene.world.node_tree is not None:
        trees.append(scene.world.node_tree)
    if len(scene.objects) > 20_000:
        raise ValueError("FINISH_INSPECTION_BUDGET_EXCEEDED")
    for ob in scene.objects:
        if ob.hide_render:
            continue
        if ob.type == "EMPTY" and isinstance(ob.data, bpy.types.Image):
            images[ob.data.as_pointer()] = ob.data
        for slot in ob.material_slots:
            if slot.material is not None and slot.material.node_tree is not None:
                trees.append(slot.material.node_tree)
        for modifier in ob.modifiers:
            group = getattr(modifier, "node_group", None)
            if group is not None:
                trees.append(group)
        if ob.type == "CAMERA":
            for background in ob.data.background_images:
                if background.image is not None:
                    images[background.image.as_pointer()] = background.image
    nodes_seen = 0
    while trees:
        tree = trees.pop()
        if tree.as_pointer() in seen:
            continue
        seen.add(tree.as_pointer())
        for node in tree.nodes:
            nodes_seen += 1
            if nodes_seen > 20_000:
                raise ValueError("FINISH_INSPECTION_BUDGET_EXCEEDED")
            image = getattr(node, "image", None)
            if image is not None:
                images[image.as_pointer()] = image
            group = getattr(node, "node_tree", None)
            if group is not None:
                trees.append(group)
    if len(images) > 2048:
        raise ValueError("FINISH_INSPECTION_BUDGET_EXCEEDED")
    return sorted(images.values(), key=lambda image: image.name)


def inspect(scene):
    settings = Settings.inspect(scene)
    render = scene.render
    blockers, warnings, assets = [], [], []
    profile = getattr(scene, "render_studio_profile", "final")
    effective = dict(settings)
    try:
        if profile not in ("preview", "final"):
            raise ValueError("FINISH_PROFILE_INVALID")
        overrides = Settings.profiles(scene, {})["profiles"][profile]
        Settings.validate(overrides)
        effective.update(overrides)
        effective["samples"] = overrides.get("samples", Settings.sample_value(scene, effective["engine"]))
    except (ValueError, TypeError, KeyError):
        blockers.append(_problem("RENDER_PROFILE_INVALID", "Repair the selected preview/final profile before queuing a render."))
    camera = scene.camera
    if camera is None or camera.type != "CAMERA" or camera.name not in scene.objects:
        blockers.append(_problem("CAMERA_REQUIRED", "Set a camera in this scene before rendering."))
    start, end, step = scene.frame_start, scene.frame_end, scene.frame_step
    if end < start or start < 1 or end > 100000 or step < 1:
        blockers.append(_problem("FRAME_RANGE_INVALID", "Use an ordered frame range between 1 and 100000."))
    if step != 1:
        blockers.append(_problem("FRAME_STEP_UNSUPPORTED", "Set frame step to 1 for the existing continuous video queue."))
    frames = max(0, (end - start) // max(1, step) + 1)
    width = effective["width"] * effective["percentage"] // 100
    height = effective["height"] * effective["percentage"] // 100
    if not (16 <= width <= 8192 and 16 <= height <= 8192) or width % 2 or height % 2:
        blockers.append(_problem("VIDEO_DIMENSIONS_INVALID", "Video export requires even dimensions from 16 to 8192 pixels."))
    fps_base = effective["fps_base"]
    valid_fps_base = math.isfinite(fps_base) and 0 < fps_base <= 100
    effective_fps = effective["fps"] / fps_base if valid_fps_base else 0
    if not 1 <= effective["fps"] <= 120 or not valid_fps_base or not 1 <= effective_fps <= 120:
        blockers.append(_problem("VIDEO_FPS_UNSUPPORTED", "Android video export requires fps / fps base between 1 and 120, with fps base above 0 and at most 100."))
    if (settings["samples"] is None or effective["samples"] is None
            or Settings._samples(scene, effective["engine"])[0] is None):
        blockers.append(_problem("SAMPLE_CONTROL_UNAVAILABLE", "This engine does not expose a supported sample control to the render queue."))
    if render.engine not in C.ENGINES[1:4] or effective["engine"] not in C.ENGINES[1:4]:
        blockers.append(_problem("ENGINE_UNSUPPORTED", "The simple Android queue requires Cycles or EEVEE; Workbench remains available in Blender's native render menu."))
    image_settings = render.image_settings
    if image_settings.file_format in ("OPEN_EXR", "OPEN_EXR_MULTILAYER", "HDR") or image_settings.color_depth == "32":
        blockers.append(_problem("HDR_OUTPUT_REQUIRES_NATIVE_MENU", "Use Blender's native render menu for HDR output, or choose an 8/16-bit image format for the Android video queue."))
    unpacked = [image.name for image in bpy.data.images if image.source == "FILE" and image.packed_file is None]
    if unpacked:
        blockers.append(_problem("PACK_EXTERNAL_IMAGES", "The durable job snapshot requires all external FILE images packed into the project (including unused images)."))
    if render.use_border:
        warnings.append(_problem("RENDER_BORDER_ENABLED", "The current render border is enabled; inspect the crop before export."))
    if scene.get("production_frozen_job"):
        blockers.append(_problem("FROZEN_JOB_SCENE", "This is an immutable render snapshot; prepare the original scene instead."))
    try:
        images = _scene_images(scene)
    except ValueError:
        images = []
        blockers.append(_problem("ASSET_INSPECTION_LIMIT", "Asset inspection exceeded the bounded scene budget."))
    for image in images:
        packed = image.packed_file is not None or bool(getattr(image, "packed_files", ()))
        entry = {"name": image.name, "source": image.source, "packed": packed}
        if image.source in ("FILE", "MOVIE", "SEQUENCE", "TILED") and not packed:
            filename = image.filepath
            # UDIM/sequence coverage is explicit; never claim every frame was checked.
            if image.source == "TILED":
                filename = filename.replace("<UDIM>", str(image.tiles[0].number) if image.tiles else "1001")
            try:
                exists = bool(filename) and Path(bpy.path.abspath(filename, library=image.library)).is_file()
            except (OSError, ValueError):
                exists = False
            entry["base_file_exists"] = exists
            if not exists:
                blockers.append(_problem("MISSING_IMAGE", "External image is missing: " + image.name))
            if image.source in ("TILED", "SEQUENCE", "MOVIE"):
                warnings.append(_problem("ASSET_SEQUENCE_NOT_DECODED", "Only the base file was checked for " + image.name + "; all tiles/frames and decoding remain unverified."))
        assets.append(entry)
    if frames > 2400 or width * height * frames > 10_000_000_000:
        warnings.append(_problem("LARGE_RENDER", "Render a short preview first; total pixels do not predict phone memory, heat or render time."))
    fps = effective["fps"] / effective["fps_base"] if effective["fps_base"] else 0
    return {"ready": not blockers, "blockers": blockers, "warnings": warnings,
            "settings": settings, "effective_settings": effective, "selected_profile": profile,
            "unpacked_external_images": unpacked[:64], "unpacked_external_image_count": len(unpacked),
            "camera": camera.name if camera is not None else None,
            "range": {"start": start, "end": end, "step": step, "frames": frames,
                      "duration_seconds": (end - start + 1) / fps if fps > 0 and end >= start else 0},
            "cost": {"pixels_per_frame": width * height, "total_pixel_frames": width * height * frames,
                     "uncompressed_rgba_bytes": width * height * frames * 4,
                     "estimate_is_render_time_or_memory_guarantee": False},
            "assets": assets, "asset_scan_scope": "current scene material/compositor/geometry-node images and camera backgrounds; simulations and external caches are not validated",
            "next_operation": "render.plan", "render_started": False,
            "existing_render_snapshots_changed": False}


def _preset(scene, p):
    if scene.get("production_frozen_job"):
        raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
    if scene.library is not None or scene.override_library is not None:
        raise ValueError("FINISH_LOCAL_SCENE_REQUIRED")
    preset = C.PRESETS[p["preset"]]
    before = inspect(scene)
    engine = scene.render.engine if p["engine"] == "keep" else p["engine"]
    start, end = p.get("start", scene.frame_start), p.get("end", scene.frame_end)
    if not 1 <= start <= end <= 100000:
        raise ValueError("FINISH_FRAME_RANGE_INVALID")
    # Workbench's actual AA choices top out at 32. This is disclosed, not a
    # hidden replacement of a Cycles/EEVEE render with a preview renderer.
    samples = min(preset["samples"], 32) if engine == "BLENDER_WORKBENCH" else preset["samples"]
    requested = {"engine": engine, "width": p.get("width", preset["width"]),
                 "height": p.get("height", preset["height"]), "percentage": 100,
                 "samples": samples}
    if "fps" in p:
        requested.update(fps=p["fps"], fps_base=1.)
    # Capture settings directly, including engine-dependent sample controls, so
    # failure after configure() can restore everything without revalidation.
    render = scene.render
    restore = [(render, field, getattr(render, field)) for field in
               ("engine", "resolution_x", "resolution_y", "resolution_percentage", "fps", "fps_base")]
    for candidate in C.ENGINES[1:]:
        owner, field = Settings._samples(scene, candidate)
        if owner is not None and (owner, field) not in [(o, f) for o, f, _ in restore]:
            restore.append((owner, field, getattr(owner, field)))
    restore.extend((scene, field, getattr(scene, field)) for field in ("frame_start", "frame_end", "frame_step"))
    profile = getattr(scene, "render_studio_profile", "final")
    if profile not in ("preview", "final"):
        raise ValueError("FINISH_PROFILE_INVALID")
    prior_profiles = scene.get("render_studio_profiles_v1")
    try:
        Settings.configure(scene, requested)
        # Set an encompassing range first: Blender clamps start/end against one another.
        scene.frame_start = min(scene.frame_start, start)
        scene.frame_end = max(scene.frame_end, end)
        scene.frame_start, scene.frame_end = start, end
        scene.frame_step = 1
        if scene.frame_start != start or scene.frame_end != end:
            raise ValueError("FINISH_NATIVE_TIMING_CLAMPED")
        # queue_manual_render uses the selected saved profile. Keep that profile
        # in agreement with the explicit preset so an older override cannot
        # silently change resolution, samples or timing in the actual job.
        profile_settings = dict(requested, fps=scene.render.fps, fps_base=scene.render.fps_base)
        Settings.profiles(scene, {"profile": profile, "settings": profile_settings}, True)
        after = inspect(scene)
        return {"preset": p["preset"], "before": before["settings"], "after": after["settings"],
                "preflight": after, "requested_samples": samples,
                "timing_fields_changed": [key for key in ("fps", "start", "end") if key in p] + ["frame_step"],
                "engine_changed": engine != before["settings"]["engine"],
                "updated_profile": profile,
                "render_started": False, "existing_render_snapshots_changed": False}
    except Exception:
        # Restore limits in an order which cannot clamp the original range.
        scene.frame_start = 1
        scene.frame_end = 100000
        for owner, field, value in restore:
            setattr(owner, field, value)
        if prior_profiles is None:
            if "render_studio_profiles_v1" in scene:
                del scene["render_studio_profiles_v1"]
        else:
            scene["render_studio_profiles_v1"] = prior_profiles
        raise


def _get_action(name):
    action = bpy.data.actions.get(name)
    if action is None:
        raise ValueError("FINISH_ACTION_NOT_FOUND")
    return action


def _curves(action):
    result, seen = [], set()
    # Read the layered form first. The legacy compatibility collection may
    # contain only the first channelbag on Blender versions that expose both.
    for layer_index, layer in enumerate(getattr(action, "layers", ())):
        for strip_index, strip in enumerate(layer.strips):
            for bag in getattr(strip, "channelbags", ()):
                for curve in bag.fcurves:
                    pointer = curve.as_pointer()
                    if pointer not in seen:
                        seen.add(pointer)
                        result.append(((layer_index, strip_index, bag.slot_handle, curve.data_path, curve.array_index), curve))
    try:
        legacy = action.fcurves
    except (AttributeError, RuntimeError):
        legacy = ()
    for curve in legacy:
        if curve.as_pointer() not in seen:
            result.append(((-1, -1, -1, curve.data_path, curve.array_index), curve))
    if len(result) > C.MAX_CURVES or sum(len(curve.keyframe_points) for _, curve in result) > C.MAX_KEYS:
        raise ValueError("FINISH_ACTION_BUDGET_EXCEEDED")
    return sorted(result, key=lambda pair: pair[0])


def _snapshot(action, curves):
    result = []
    for identity, curve in curves:
        result.append({"identity": identity, "lock": curve.lock, "mute": curve.mute,
                       "extrapolation": curve.extrapolation,
                       "modifiers": [{key: getattr(mod, key) for key in
                                      ("type", "mute", "use_restricted_range", "frame_start", "frame_end",
                                       "mode_before", "mode_after", "cycles_before", "cycles_after")
                                      if hasattr(mod, key)} for mod in curve.modifiers],
                       "points": [{"co": list(k.co), "left": list(k.handle_left), "right": list(k.handle_right),
                                   "left_type": k.handle_left_type, "right_type": k.handle_right_type,
                                   "interpolation": k.interpolation, "easing": k.easing,
                                   "amplitude": k.amplitude, "back": k.back, "period": k.period}
                                  for k in curve.keyframe_points]})
    return {"name": action.name, "use_frame_range": getattr(action, "use_frame_range", False),
            "curves": result}


def _revision(snapshot):
    try:
        value = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except ValueError as error:
        raise ValueError("FINISH_NONFINITE_ACTION") from error
    return hashlib.sha256(value).hexdigest()


def _action_owners(action):
    users = bpy.data.user_map(subset={action}).get(action, set())
    if len(users) > 128:
        raise ValueError("FINISH_ACTION_USERS_BUDGET_EXCEEDED")
    return users


def _nla_users(action):
    users = _action_owners(action)
    count = 0
    for owner in users:
        animation = getattr(owner, "animation_data", None)
        if animation is None:
            continue
        pending = [strip for track in animation.nla_tracks for strip in track.strips]
        while pending:
            count += 1
            if count > 4096:
                raise ValueError("FINISH_NLA_BUDGET_EXCEEDED")
            strip = pending.pop()
            if getattr(strip, "action", None) == action:
                return True
            pending.extend(getattr(strip, "strips", ()))
    return False


def _blockers(action, curves):
    result = []
    if action.library is not None or action.override_library is not None:
        result.append("LINKED_ACTION")
    if getattr(action, "use_frame_range", False):
        result.append("ACTION_CUSTOM_FRAME_RANGE")
    if (action.get("render_motion_lab") is not None
            or any(owner.get("render_motion_lab") is not None for owner in _action_owners(action))):
        result.append("MOTION_LAB_GROUP_RETIME_REQUIRED")
    if not curves or not any(len(curve.keyframe_points) for _, curve in curves):
        result.append("ACTION_HAS_NO_KEYS")
    if any(curve.lock for _, curve in curves):
        result.append("LOCKED_CHANNEL")
    if any(len(curve.sampled_points) for _, curve in curves):
        result.append("SAMPLED_CHANNEL")
    if any(mod.type != "CYCLES" or mod.use_restricted_range for _, curve in curves for mod in curve.modifiers):
        result.append("TIME_DEPENDENT_MODIFIER")
    if _nla_users(action):
        result.append("ACTION_USED_IN_NLA")
    return result


def _keyframes_inspect(p):
    action = _get_action(p["action"])
    curves = _curves(action)
    snapshot = _snapshot(action, curves)
    frames = [k.co.x for _, curve in curves for k in curve.keyframe_points]
    return {"action": action.name, "revision_sha256": _revision(snapshot),
            "curves": len(curves), "keys": len(frames),
            "frame_range": [min(frames), max(frames)] if frames else [],
            "action_users": action.users, "shared_action_approval_required": action.users - int(action.use_fake_user) > 1,
            "retime_blockers": _blockers(action, curves), "all_action_slots": True,
            "retime_notes": "Motion Lab rig actions, IK controls and declared contact windows must keep coordinated timing; create the clip with the desired frame range. Other blocked channels need native Blender editing.",
            "retime_formula": "pivot + (old_frame - pivot) * scale + offset"}


def _set_keys(curves, snapshot, transform):
    for (_, curve), saved in zip(curves, snapshot["curves"]):
        for key, old in zip(curve.keyframe_points, saved["points"]):
            key.handle_left_type = "FREE"
            key.handle_right_type = "FREE"
            key.co = (transform(old["co"][0]), old["co"][1])
            key.handle_left = (transform(old["left"][0]), old["left"][1])
            key.handle_right = (transform(old["right"][0]), old["right"][1])
            key.handle_left_type = old["left_type"]
            key.handle_right_type = old["right_type"]
        curve.update()


def _retime(p):
    action = _get_action(p["action"])
    curves = _curves(action)
    snapshot = _snapshot(action, curves)
    prior = _revision(snapshot)
    if prior != p["expected_sha256"]:
        raise ValueError("FINISH_ACTION_REVISION_CONFLICT")
    if action.users - int(action.use_fake_user) > 1 and not p["allow_shared_action"]:
        raise ValueError("FINISH_SHARED_ACTION_APPROVAL_REQUIRED")
    blockers = _blockers(action, curves)
    if blockers:
        if "MOTION_LAB_GROUP_RETIME_REQUIRED" in blockers:
            raise ValueError("FINISH_MOTION_LAB_GROUP_RETIME_REQUIRED")
        raise ValueError("FINISH_RETIME_BLOCKED:" + ",".join(blockers))
    transform = lambda frame: p["pivot"] + (frame - p["pivot"]) * p["scale"] + p["offset"]
    for saved in snapshot["curves"]:
        transformed = []
        for key in saved["points"]:
            frame = transform(key["co"][0])
            if not math.isfinite(frame) or not 0 <= frame <= 100000:
                raise ValueError("FINISH_RETIME_FRAME_OUT_OF_RANGE")
            transformed.append(struct.unpack("f", struct.pack("f", frame))[0])
            for side in ("left", "right"):
                if not -2_000_000 <= transform(key[side][0]) <= 2_000_000:
                    raise ValueError("FINISH_RETIME_HANDLE_OUT_OF_RANGE")
        if any(b - a <= .0001 for a, b in zip(transformed, transformed[1:])):
            raise ValueError("FINISH_RETIME_KEY_COLLISION")
    before_range = _keyframes_inspect({"action": action.name})["frame_range"]
    try:
        _set_keys(curves, snapshot, transform)
        action.update_tag()
        result = _keyframes_inspect({"action": action.name})
    except Exception:
        _set_keys(curves, snapshot, lambda frame: frame)
        action.update_tag()
        raise
    return {"action": action.name, "prior_revision": prior, "new_revision": result["revision_sha256"],
            "frame_range_before": before_range, "frame_range_after": result["frame_range"],
            "curves": result["curves"], "keys": result["keys"], "all_action_slots": True,
            "bezier_handle_times_transformed": True, "scene_timing_changed": False,
            "shared_action_approved": p["allow_shared_action"]}


def execute(operation, payload, root, scene):
    p = C.validate(operation, payload)
    if scene != bpy.context.scene:
        raise ValueError("FINISH_ACTIVE_SCENE_REQUIRED")
    if operation == "studio.finish.inspect":
        return inspect(scene)
    if operation == "studio.keyframes.inspect":
        return _keyframes_inspect(p)
    if scene.get("production_frozen_job"):
        raise ValueError("RENDER_SNAPSHOT_IMMUTABLE")
    if operation == "studio.finish.preset":
        return _preset(scene, p)
    if operation == "studio.keyframes.retime":
        return _retime(p)
    raise ValueError("FINISH_OPERATION_UNAVAILABLE")


dispatch = execute
capabilities = C.capabilities
