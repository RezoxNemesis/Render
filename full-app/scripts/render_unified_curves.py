# SPDX-License-Identifier: GPL-2.0-or-later
"""Direct, revision-safe Graph Editor F-Curve inspection and adjustment.

This edits Blender F-Curves, not a screenshot or a rendered animation preset.
It never evaluates executable text. Current pinned Android Blender uses 4.0
Action.fcurves; layered-action support is capability-checked, not faked.
"""
import hashlib
import json
import math
import bpy

def _check(p,required=(),allowed=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_CURVE_ARGUMENTS_INVALID")

def _numeric(x,low=-1e9,high=1e9):
    if type(x) not in (int,float) or not math.isfinite(x) or not low<=x<=high:
        raise ValueError("STUDIO_CURVE_NUMBER_INVALID")
    return float(x)

def _get_action(name):
    if not isinstance(name,str) or not 1<=len(name)<=128:
        raise ValueError("STUDIO_ACTION_NAME_INVALID")
    action=bpy.data.actions.get(name)
    if action is None:raise ValueError("STUDIO_ACTION_NOT_FOUND")
    return action

def _action_curves(action):
    try:
        return list(action.fcurves)
    except (AttributeError,RuntimeError,TypeError):
        raise ValueError("STUDIO_ACTION_CURVES_NOT_AVAILABLE_ON_THIS_BLENDER")

def _snapshot(curve):
    return {
        "data_path":curve.data_path,
        "array_index":curve.array_index,
        "points":[{
            "frame":float(k.co.x),"value":float(k.co.y),
            "interpolation":k.interpolation,
            "left":list(k.handle_left),"right":list(k.handle_right),
            "left_type":k.handle_left_type,
            "right_type":k.handle_right_type,
        } for k in curve.keyframe_points]
    }

def revision(curve):
    raw=json.dumps(_snapshot(curve),sort_keys=True,separators=(",",":"),
                   allow_nan=False).encode("utf8")
    return hashlib.sha256(raw).hexdigest()

def inspect(p):
    _check(p,(),("action","limit"))
    limit=p.get("limit",24)
    if type(limit) is not int or not 1<=limit<=64:raise ValueError("STUDIO_CURVE_PAGE_INVALID")
    if "action" not in p:
        actions=sorted(bpy.data.actions,key=lambda a:a.name)
        return {"actions":[{"name":a.name,"users":a.users,
                            "fcurves_supported":hasattr(a,"fcurves")}
                           for a in actions[:limit]],
                "total_actions":len(actions),"mutable_only_with_revision_token":True}
    action=_get_action(p["action"])
    curves=_action_curves(action)
    return {"action":action.name,"action_users":action.users,
            "curves":[dict(_snapshot(c),revision_sha256=revision(c))
                      for c in curves[:limit]],
            "total_curves":len(curves),
            "pagination_available":False if len(curves)<=limit else True,
            "native_curve_data":True,"graph_editor_pointer_taps":False}

def adjust(p):
    fields=("action","data_path","array_index","key_frame",
            "expected_sha256","new_frame","new_value",
            "interpolation","handle_type","handle_left","handle_right",
            "allow_shared_action")
    _check(p,("action","data_path","array_index","key_frame","expected_sha256"),fields)
    if set(p)==set(("action","data_path","array_index","key_frame","expected_sha256")):
        raise ValueError("STUDIO_CURVE_NO_CHANGES")
    action=_get_action(p["action"])
    if action.users>1 and p.get("allow_shared_action") is not True:
        raise ValueError("STUDIO_ACTION_SHARED_EXPLICIT_APPROVAL_REQUIRED")
    if "allow_shared_action" in p and type(p["allow_shared_action"]) is not bool:
        raise ValueError("STUDIO_CURVE_SHARED_FLAG_INVALID")
    path=p["data_path"];idx=p["array_index"]
    if type(path) is not str or not 1<=len(path)<=256 or type(idx) is not int or not 0<=idx<=15:
        raise ValueError("STUDIO_CURVE_ID_INVALID")
    curve=next((c for c in _action_curves(action)
                if c.data_path==path and c.array_index==idx),None)
    if curve is None:raise ValueError("STUDIO_CURVE_NOT_FOUND")
    old=revision(curve)
    if p["expected_sha256"]!=old:
        raise ValueError("STUDIO_CURVE_REVISION_CONFLICT")
    frame=_numeric(p["key_frame"],0,100000)
    points=list(curve.keyframe_points)
    matches=[(i,k) for i,k in enumerate(points) if abs(k.co.x-frame)<.0001]
    if len(matches)!=1:raise ValueError("STUDIO_CURVE_KEYFRAME_MISMATCH")
    kidx,key=matches[0]
    new_frame=_numeric(p.get("new_frame",frame),0,100000)
    value=_numeric(p.get("new_value",key.co.y))
    prev=points[kidx-1].co.x if kidx>0 else -1
    next_frame=points[kidx+1].co.x if kidx+1<len(points) else 100001
    if not prev+.0001<new_frame<next_frame-.0001:
        raise ValueError("STUDIO_CURVE_KEY_CROSSING_BLOCKED")
    interpolation=p.get("interpolation",key.interpolation)
    if interpolation not in ("BEZIER","LINEAR","CONSTANT"):
        raise ValueError("STUDIO_CURVE_INTERPOLATION_UNSUPPORTED")
    handle_type=p.get("handle_type")
    if handle_type is not None and handle_type not in (
            "AUTO","AUTO_CLAMPED","FREE","ALIGNED","VECTOR"):
        raise ValueError("STUDIO_CURVE_HANDLE_TYPE_UNSUPPORTED")
    for field in ("handle_left","handle_right"):
        if field in p:
            v=p[field]
            if not isinstance(v,list) or len(v)!=2:raise ValueError("STUDIO_CURVE_HANDLE_INVALID")
            x,y=(_numeric(v[0],-100000,100000),_numeric(v[1]))
            if field=="handle_left" and x>new_frame or field=="handle_right" and x<new_frame:
                raise ValueError("STUDIO_CURVE_HANDLE_CROSSES_KEY")
    # All checks complete. Keep actual animation curve data intact on failure.
    key.co=(new_frame,value)
    key.interpolation=interpolation
    if handle_type is not None:
        key.handle_left_type=handle_type
        key.handle_right_type=handle_type
    for field in ("handle_left","handle_right"):
        if field in p:
            if field=="handle_left":key.handle_left_type="FREE"
            else:key.handle_right_type="FREE"
            setattr(key,field,p[field])
    curve.update()
    if hasattr(action,"update_tag"):action.update_tag()
    actual=revision(curve)
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type in ("GRAPH_EDITOR","NLA_EDITOR","DOPESHEET_EDITOR"):
                    area.tag_redraw()
    except (RuntimeError,AttributeError):pass
    return {"action":action.name,"data_path":path,"array_index":idx,
            "keyframe_before":frame,"keyframe_after":float(key.co.x),
            "value_after":float(key.co.y),
            "interpolation_after":key.interpolation,
            "prior_revision":old,"new_revision":actual,
            "actual_blender_fcurve_updated":True,
            "renderer_or_geometry_changed":False,
            "remote_python_evaluated":False}

def execute(op,p):
    if op=="studio.curve.inspect":return inspect(p)
    if op=="studio.curve.adjust":return adjust(p)
    raise ValueError("STUDIO_CURVE_OPERATION_UNAVAILABLE")

def capabilities():
    scalar={"type":"number"}
    text={"type":"string"}
    ref={"type":"string","pattern":"^[a-f0-9]{64}$"}
    return [
        {"operation":"studio.curve.inspect","workspace":"animation",
         "input_schema":{"type":"object","additionalProperties":False,
                         "properties":{"action":text,"limit":{"type":"integer","minimum":1,"maximum":64}},
                         "required":[]},
         "actual_blender_fcurve":True,"native_bpy_required":True},
        {"operation":"studio.curve.adjust","workspace":"animation",
         "input_schema":{"type":"object","additionalProperties":False,
             "properties":{"action":text,"data_path":text,"array_index":{"type":"integer"},
                 "key_frame":scalar,"expected_sha256":ref,
                 "new_frame":scalar,"new_value":scalar,
                 "interpolation":{"enum":["BEZIER","LINEAR","CONSTANT"]},
                 "handle_type":{"enum":["AUTO","AUTO_CLAMPED","FREE","ALIGNED","VECTOR"]},
                 "handle_left":{"type":"array","minItems":2,"maxItems":2},
                 "handle_right":{"type":"array","minItems":2,"maxItems":2},
                 "allow_shared_action":{"type":"boolean"}},
             "required":["action","data_path","array_index","key_frame","expected_sha256"]},
         "requires_revision_proof":True,"checkpoint_before_change":True,
         "native_bpy_required":True}
    ]
