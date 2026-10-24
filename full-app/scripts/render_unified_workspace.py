# SPDX-License-Identifier: GPL-2.0-or-later
"""Human-visible, real Blender workspaces and inspectable agent execution.

Native bpy (not simulated taps). The Android app owns the same production.execute
target and controls all I/O. All scene writes run on the Blender timer/main thread.
"""
from collections import deque
import json
import math
import os
from pathlib import Path
import time

import bpy
from mathutils import Quaternion, Vector

import render_unified_contract as C
import render_unified_queue as Q

INSTALLED=False
TIMER_INSTALLED=False
_ACTIVITY=deque(maxlen=64)
_LAST_TIMER_ERROR=""
SECTIONS=tuple((row[0],row[1],"Native Blender: "+row[3]) for row in C.WORKSPACES)

def _root():
    spool=os.environ.get("RENDER_AGENT_SPOOL","")
    if not spool:raise RuntimeError("STUDIO_PRIVATE_SPOOL_UNAVAILABLE")
    base=Path(spool).resolve().parent/"Production"
    base.mkdir(parents=True,mode=0o700,exist_ok=True)
    return base

def _check(p,allowed,required=()):
    if not isinstance(p,dict) or set(p)-set(allowed) or not set(required)<=set(p):
        raise ValueError("STUDIO_OPERATION_ARGUMENTS_INVALID")

def _finite(v,low,high):
    if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
        raise ValueError("STUDIO_NAVIGATION_NUMBER_INVALID")
    return float(v)

def _section(scene):
    value=scene.get("render_studio_active_section","agent")
    return value if value in {w[0] for w in C.WORKSPACES} else "agent"

def _areas():
    window=bpy.context.window
    if not window or not window.screen:return []
    return [area for area in window.screen.areas if area.type=="VIEW_3D"]

def _activate(scene,p):
    _check(p,("workspace","show_sidebar"),("workspace",))
    section=p["workspace"]
    if not isinstance(section,str) or section not in {w[0] for w in C.WORKSPACES}:
        raise ValueError("STUDIO_WORKSPACE_UNAVAILABLE")
    if type(p.get("show_sidebar",False)) is not bool:
        raise ValueError("STUDIO_SIDEBAR_OPTION_INVALID")
    scene["render_studio_active_section"]=section
    if hasattr(scene,"render_studio_section"):
        scene.render_studio_section=section
    areas=_areas()
    if p.get("show_sidebar",False):
        if not areas:raise ValueError("STUDIO_NATIVE_VIEWPORT_NOT_OPEN")
        for area in areas:
            if hasattr(area.spaces.active,"show_region_ui"):
                area.spaces.active.show_region_ui=True
            area.tag_redraw()
    return {"workspace":section,"native_viewports":len(areas),
            "sidebar_requested":p.get("show_sidebar",False),
            "actual_scene_workspace_changed":True,
            "native_blender_engine_unchanged":True,
            "simulated_pointer_clicks":False}

def _orbit(scene,p):
    _check(p,("yaw_degrees","pitch_degrees","zoom","object"),
           ("yaw_degrees","pitch_degrees"))
    yaw=_finite(p["yaw_degrees"],-60,60)
    pitch=_finite(p["pitch_degrees"],-60,60)
    zoom=_finite(p.get("zoom",1),.3,3.0)
    obj=None
    if "object" in p:
        name=p["object"]
        if type(name) is not str or name not in scene.objects:
            raise ValueError("STUDIO_VIEW_TARGET_NOT_FOUND")
        obj=scene.objects[name]
    areas=_areas()
    if not areas:raise ValueError("STUDIO_NATIVE_VIEWPORT_NOT_OPEN")
    reports=[]
    for area in areas:
        space=area.spaces.active
        region=space.region_3d
        if region is None:continue
        current=region.view_rotation.copy()
        z=Quaternion((0,0,1),math.radians(yaw))
        local=Quaternion((1,0,0),math.radians(pitch))
        region.view_rotation=(z@current@local).normalized()
        region.view_distance=max(.01,min(100000,region.view_distance*zoom))
        region.view_perspective="PERSP"
        if obj is not None:
            if obj.type in ("MESH","CURVE","FONT","SURFACE"):
                points=[obj.matrix_world@Vector(c) for c in obj.bound_box]
                region.view_location=sum(points,Vector())/len(points)
            else:region.view_location=obj.matrix_world.translation
        area.tag_redraw()
        reports.append({"view_rotation":list(region.view_rotation),
                        "distance":float(region.view_distance),
                        "focus":list(region.view_location)})
    if not reports:raise ValueError("STUDIO_VIEW_REGION_NOT_READY")
    return {"viewports_changed":len(reports),"actual_blender_viewports":reports,
            "camera_and_object_geometry_unchanged":True,
            "simulated_touch_events":False,"native_view_rotation_applied":True}

_EDITORS={
 "VIEW_3D":("VIEW_3D",None),
 "GRAPH_EDITOR":("GRAPH_EDITOR",None),
 "NLA_EDITOR":("NLA_EDITOR",None),
 "DOPESHEET_EDITOR":("DOPESHEET_EDITOR",None),
 "SHADER_EDITOR":("NODE_EDITOR","ShaderNodeTree"),
 "GEOMETRY_NODES":("NODE_EDITOR","GeometryNodeTree"),
 "COMPOSITOR":("NODE_EDITOR","CompositorNodeTree"),
 "IMAGE_EDITOR":("IMAGE_EDITOR",None),
 "TEXT_EDITOR":("TEXT_EDITOR",None),
}
def _editor(p):
    _check(p,("editor",),("editor",))
    editor=p["editor"]
    if editor not in _EDITORS:raise ValueError("STUDIO_EDITOR_UNAVAILABLE")
    window=bpy.context.window
    if not window or not window.screen:raise ValueError("STUDIO_EDITOR_WINDOW_NOT_AVAILABLE")
    # Only the owner's live, local Blender screen is changed. No Gallery.
    area=bpy.context.area if bpy.context.area and bpy.context.area in window.screen.areas else None
    if area is None:
        area=next((x for x in window.screen.areas if x.type=="VIEW_3D"),None)
    if area is None:raise ValueError("STUDIO_EDITOR_AREA_NOT_AVAILABLE")
    area.type=_EDITORS[editor][0]
    desired=_EDITORS[editor][1]
    if desired is not None:
        try:area.ui_type=desired
        except (TypeError,ValueError,AttributeError):
            raise ValueError("STUDIO_NODE_EDITOR_NOT_SUPPORTED")
    actual=area.type
    area.tag_redraw()
    return {"requested_editor":editor,"native_area":actual,
            "native_editor_changed":actual==_EDITORS[editor][0],
            "dragged_ui":False,"pointer_taps_fabricated":False}

def _activity_path():
    folder=Q._directory(_root())
    p=folder/"activity.json"
    if p.is_symlink():raise ValueError("STUDIO_ACTIVITY_SYMLINK")
    return p

def _history():
    try:
        path=_activity_path()
        if path.is_file() and path.stat().st_size<20000:
            entries=json.loads(path.read_text(encoding="utf8"))
            if isinstance(entries,list):
                return [x for x in entries if isinstance(x,dict)][-64:]
    except (OSError,ValueError,RuntimeError):pass
    return list(_ACTIVITY)

def _record(method,value):
    """Called only from the authenticated Blender command executor."""
    if not isinstance(value,dict):return
    action=value.get("args",{}).get("operation",value.get("action")) if method=="command_started" else None
    if method=="command_started":
        if not isinstance(action,str):return
        _ACTIVITY.append({"event":"started","operation":action[:96],
                          "at_epoch_ms":int(time.time()*1000)})
    elif method=="command_finished":
        operation=next((a["operation"] for a in reversed(_ACTIVITY) if a["event"]=="started"),None)
        if operation is None:return
        result=value.get("result") if isinstance(value.get("result"),dict) else {}
        ob=result.get("object") if isinstance(result,dict) else None
        if not isinstance(ob,str) or len(ob)>64:ob=None
        _ACTIVITY.append({"event":str(value.get("state","needs_review"))[:32],
                          "operation":operation,"object":ob,
                          "at_epoch_ms":int(time.time()*1000)})
    else:return
    try:
        history=_history()
        # Activity records only state, operation and verified object; never
        # owner prompt, auth token, asset contents or device filesystem paths.
        tail=list(_ACTIVITY)[-1]
        if not history or history[-1]!=tail:
            history=(history+[tail])[-64:]
        Q._save(_activity_path(),history)
    except (ValueError,OSError,RuntimeError):pass

def observe_native(method,value):
    if method in ("command_started","command_finished"):_record(method,value)

def _execute_step(op,payload,plan_id):
    # Native Blender mutations run on this timer ONLY. Make a real .blend
    # checkpoint before a consequential step unless the existing operation
    # already checkpoints itself. No replay of an interrupted write.
    if op in C.MUTATING and op not in (
            "studio.workspace.activate","studio.view.orbit",
            "body.blockout","reference.workspace.open",
            "reference.fit.landmarks","reference.fit.multiview",
            "animation.clip.create","project.checkpoint","studio.curve.adjust"):
        import render_artist_ops
        render_artist_ops.checkpoint(bpy.context.scene,_root(),"studio.plan."+op)
    import render_production
    return render_production.execute(
        {"operation":op,"payload":payload},
        os.environ["RENDER_AGENT_SPOOL"],plan_id)

def _step_start(pid,index,operation):
    try:
        import render_native_hud
        render_native_hud.command_started({"action":"blender.production.execute",
                                          "args":{"operation":operation}})
    except (ImportError,AttributeError,RuntimeError):pass
    observe_native("command_started",{"args":{"operation":operation}})

def _step_end(pid,index,operation,state,result):
    packet={"state":"succeeded" if state=="succeeded" else "failed",
            "result":result if isinstance(result,dict) else {}}
    try:
        import render_native_hud
        render_native_hud.command_finished(packet)
    except (ImportError,AttributeError,RuntimeError):pass
    observe_native("command_finished",packet)

def _tick():
    global _LAST_TIMER_ERROR
    try:
        render_busy=False
        try:render_busy=bool(bpy.app.is_job_running("RENDER"))
        except (AttributeError,TypeError,RuntimeError):pass
        Q.tick(_root(),_execute_step,on_start=_step_start,
               on_finish=_step_end,render_busy=render_busy)
        _LAST_TIMER_ERROR=""
    except (OSError,ValueError,RuntimeError) as exc:
        # Do not auto-clear corrupt queues or silently retry unreceipted edits.
        _LAST_TIMER_ERROR=type(exc).__name__
    try:
        for area in _areas():area.tag_redraw()
    except (AttributeError,RuntimeError):pass
    return .6

def install_timer():
    global TIMER_INSTALLED
    if TIMER_INSTALLED:return
    if not os.environ.get("RENDER_AGENT_SPOOL"):return
    Q.recover(_root()) # Crash barriers require explicit inspection.
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick,first_interval=.8,persistent=True)
    TIMER_INSTALLED=True

def _tool_search(p):
    _check(p,("query","workspace","limit"),("query",))
    q=p["query"]
    if not isinstance(q,str) or not 1<=len(q)<=64:
        raise ValueError("STUDIO_TOOL_QUERY_INVALID")
    work=p.get("workspace",None)
    if work is not None and work not in {x[0] for x in C.WORKSPACES}:
        raise ValueError("STUDIO_WORKSPACE_UNAVAILABLE")
    limit=p.get("limit",15)
    if type(limit) is not int or not 1<=limit<=30:
        raise ValueError("STUDIO_TOOL_LIMIT_INVALID")
    import render_production_contract
    native=set(render_production_contract.OPERATIONS)
    try:
        import render_artist_ops
        artist=render_artist_ops.SCHEMAS
    except ImportError:artist={}
    try:
        import render_reference_motion_contract
        ref={entry["operation"]:entry.get("input_schema")
             for entry in render_reference_motion_contract.capabilities()}
    except ImportError:ref={}
    try:
        import render_unified_curves
        ref.update({entry["operation"]:entry["input_schema"]
                    for entry in render_unified_curves.capabilities()})
    except ImportError:pass
    result=[]
    for op in sorted(native | set(C.PROGRAM_OPS)):
        group=C.PROGRAM_OPS.get(op)
        if group is None:
            if op.startswith(("reference.","file.","asset.","media.")):group="assets"
            elif op.startswith(("animation.","rig.","shape.")):group="animation"
            elif op.startswith(("render.","camera.","world.")):group="cinema"
            elif op.startswith(("material.",)):group="materials"
            elif op.startswith(("mesh.","sculpt.")):group="sculpt"
            else:group="agent"
        if work is not None and work!=group:continue
        haystack=op.lower()+" "+group+" "+(" ".join(C.WORKSPACE_HINTS.get(group,()))).lower()
        if q.lower() not in haystack:continue
        result.append({"operation":op,"workspace":group,
            "route":"production.execute","known_in_native_registry":op in native,
            "batch_supported":op in C.PROGRAM_OPS,
            "input_schema":ref.get(op,{"fields":artist.get(op,[])})})
        if len(result)>=limit:break
    return {"query":q,"matches":result,
            "source":"current Blender runtime, not memory",
            "arbitrary_remote_python_enabled":False}

def execute(op,p,root,scene):
    if op=="studio.capabilities":
        _check(p,("workspace",))
        result=C.catalog(active=_section(scene))
        requested=p.get("workspace")
        if requested is not None:
            if requested not in {row[0] for row in C.WORKSPACES}:
                raise ValueError("STUDIO_WORKSPACE_UNAVAILABLE")
            result["workspaces"]=[x for x in result["workspaces"] if x["id"]==requested]
        result.update(blender_version=bpy.app.version_string,
                      app_ui_installed=INSTALLED,background_bpy=bpy.app.background,
                      work_plan_timer_installed=TIMER_INSTALLED,
                      current_native_scene=scene.name,
                      api_supported_ops=[
                          "studio.capabilities","studio.tool.search",
                          "studio.workspace.activate","studio.workspace.inspect",
                          "studio.view.orbit","studio.editor.open",
                          "studio.curve.inspect","studio.curve.adjust",
                          "studio.plan.submit","studio.plan.status","studio.plan.list",
                          "studio.plan.pause","studio.plan.resume","studio.plan.cancel",
                          "studio.activity"])
        return result
    if op=="studio.tool.search":return _tool_search(p)
    if op in ("studio.curve.inspect","studio.curve.adjust"):
        import render_unified_curves
        return render_unified_curves.execute(op,p)
    if op=="studio.workspace.activate":return _activate(scene,p)
    if op=="studio.view.orbit":return _orbit(scene,p)
    if op=="studio.editor.open":return _editor(p)
    if op=="studio.workspace.inspect":
        _check(p,())
        return {"active_workspace":_section(scene),
                "native_viewports":len(_areas()),
                "active_object":getattr(bpy.context.active_object,"name",None),
                "mode":bpy.context.mode,
                "current_frame":scene.frame_current,
                "queue":Q.list_jobs(root),
                "ui_installed":INSTALLED,
                "background_scene_edits_concurrent":False}
    if op=="studio.activity":
        _check(p,("limit",))
        limit=p.get("limit",24)
        if type(limit) is not int or not 1<=limit<=64:raise ValueError("STUDIO_ACTIVITY_LIMIT_INVALID")
        return {"events":_history()[-limit:],
                "last_native_error_type":_LAST_TIMER_ERROR or None,
                "live_pointer_is_real_input":False}
    if op=="studio.plan.submit":
        _check(p,("plan_id","name","steps"),("steps",))
        install_timer()
        return Q.submit(root,p)
    if op=="studio.plan.list":
        _check(p,())
        return Q.list_jobs(root)
    if op in ("studio.plan.status","studio.plan.pause","studio.plan.resume","studio.plan.cancel"):
        _check(p,("plan_id",),("plan_id",))
        job=p["plan_id"]
        if op=="studio.plan.status":return Q.get(root,job)
        if op=="studio.plan.pause":return Q.pause(root,job)
        if op=="studio.plan.resume":return Q.resume(root,job)
        return Q.cancel(root,job)
    raise ValueError("STUDIO_OPERATION_UNAVAILABLE")

class RENDERSTUDIO_OT_open_native_editor(bpy.types.Operator):
    bl_idname="renderstudio.open_native_editor"
    bl_label="Open Blender Editor"
    bl_description="Switch to an actual built-in Blender editor (not a remote screenshot)"
    target:bpy.props.EnumProperty(items=[(x,x.replace("_"," ").title(),"") for x in _EDITORS])
    def execute(self,context):
        try:
            result=_editor({"editor":self.target})
            self.report({"INFO"},"Native Blender: "+result["native_area"])
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"},str(exc));return {"CANCELLED"}

class RENDERSTUDIO_OT_native_mode(bpy.types.Operator):
    bl_idname="renderstudio.native_work_mode"
    bl_label="Native Blender Work Mode"
    mode:bpy.props.EnumProperty(items=[("OBJECT","Object mode",""),("SCULPT","Sculpt",""),
            ("POSE","Pose",""),("WEIGHT_PAINT","Weight paint",""),
            ("TEXTURE_PAINT","Texture paint","")])
    def execute(self,context):
        if not context.active_object:
            self.report({"ERROR"},"Select the actual Blender object first")
            return {"CANCELLED"}
        try:
            bpy.ops.object.mode_set(mode=self.mode)
            self.report({"INFO"},"Blender mode: "+context.mode)
            return {"FINISHED"}
        except (RuntimeError,ValueError) as exc:
            self.report({"ERROR"},str(exc));return {"CANCELLED"}

class RENDERSTUDIO_OT_plan_pause(bpy.types.Operator):
    bl_idname="renderstudio.pause_native_plan"
    bl_label="Pause Next Step"
    def execute(self,context):
        try:
            Q.pause(_root(),context.scene.render_studio_plan_id)
            return {"FINISHED"}
        except (ValueError,OSError) as exc:
            self.report({"ERROR"},str(exc));return {"CANCELLED"}

class RENDERSTUDIO_OT_plan_resume(bpy.types.Operator):
    bl_idname="renderstudio.resume_native_plan"
    bl_label="Resume Queued Steps"
    def execute(self,context):
        try:
            Q.resume(_root(),context.scene.render_studio_plan_id)
            return {"FINISHED"}
        except (ValueError,OSError) as exc:
            self.report({"ERROR"},str(exc));return {"CANCELLED"}

def _button(layout,text,target,icon="NONE"):
    row=layout.row()
    action=row.operator("renderstudio.open_native_editor",text=text,icon=icon)
    action.target=target

class RENDERSTUDIO_PT_unified(bpy.types.Panel):
    bl_idname="RENDERSTUDIO_PT_unified_workspaces"
    bl_label="Render Studio / All-in-One"
    bl_space_type="VIEW_3D"
    bl_region_type="UI"
    bl_category="Render Studio"
    def draw(self,context):
        layout=self.layout
        scene=context.scene
        layout.prop(scene,"render_studio_section",text="Workspace")
        section=scene.render_studio_section
        layout.label(text=next(x[1] for x in C.WORKSPACES if x[0]==section))
        layout.label(text="Native Blender tools • original engine")
        col=layout.column(align=True)
        if section=="sculpt":
            a=col.operator("renderstudio.native_work_mode",text="Enter Sculpt Mode",icon="SCULPTMODE_HLT");a.mode="SCULPT"
            a=col.operator("renderstudio.native_work_mode",text="Return to Object",icon="OBJECT_DATA");a.mode="OBJECT"
            _button(col,"Inspect Geometry Nodes","GEOMETRY_NODES")
            col.label(text="Detailed brushes depend on bundled Blender")
        elif section=="characters":
            a=col.operator("renderstudio.native_work_mode",text="Pose Active Armature",icon="ARMATURE_DATA");a.mode="POSE"
            a=col.operator("renderstudio.native_work_mode",text="Weight Paint",icon="WPAINT_HLT");a.mode="WEIGHT_PAINT"
            col.label(text="Use landmark fitting and rig tools via agent")
        elif section=="animation":
            _button(col,"Keyframe / Dope Sheet","DOPESHEET_EDITOR","ACTION")
            _button(col,"Animation Graph Curves","GRAPH_EDITOR","GRAPH")
            _button(col,"Nonlinear Animation (NLA)","NLA_EDITOR","NLA")
            col.label(text="Bone + facial actions and motion audits")
        elif section=="cinema":
            _button(col,"3D Camera View","VIEW_3D","VIEW_CAMERA")
            _button(col,"Compositor","COMPOSITOR","NODE_COMPOSITING")
            col.operator("renderstudio.safe_render",text="Checkpointed Animation Render",icon="RENDER_ANIMATION")
            col.operator("renderstudio.resume_render",text="Resume Native Render",icon="PLAY")
            col.label(text="Cycles/Eevee scene settings remain yours")
        elif section=="simulation":
            _button(col,"Geometry Nodes","GEOMETRY_NODES","NODETREE")
            _button(col,"3D Physics View","VIEW_3D","PHYSICS")
            col.label(text="Native cloth/physics only when bundled")
        elif section=="materials":
            _button(col,"Shader Editor","SHADER_EDITOR","MATERIAL")
            _button(col,"UV & Image Editor","IMAGE_EDITOR","IMAGE_DATA")
            a=col.operator("renderstudio.native_work_mode",text="Texture Paint",icon="TPAINT_HLT");a.mode="TEXTURE_PAINT"
        elif section=="drawing":
            _button(col,"2D Dope Sheet","DOPESHEET_EDITOR","GREASEPENCIL")
            _button(col,"Drawing Viewport","VIEW_3D","OUTLINER_OB_GREASEPENCIL")
            col.label(text="Grease Pencil version support: inspect")
        elif section=="assets":
            _button(col,"Reference Image Editor","IMAGE_EDITOR","IMAGE_DATA")
            col.label(text="Authorized picker, no Gallery scraping")
            col.label(text="CC0 browser remains in Assets panel")
        else:
            col.label(text="ChatGPT actions execute in this Blender")
            col.label(text="No synthetic pointer clicks")
            try:
                state=Q.list_jobs(_root())
                col.label(text="Queued plans: "+str(state["pending"]))
                if state["needs_review"]:
                    col.label(text="Manual review: "+str(state["needs_review"]),icon="ERROR")
                if state["jobs"]:
                    head=state["jobs"][0]
                    col.label(text=head["name"][:35])
                    col.label(text=head["state"]+" / "+str(head["completed_steps"])+"/"+str(head["total_steps"]))
                    if hasattr(col,"progress"):
                        col.progress(factor=head["fraction"],type="BAR",text="Checkpointed steps")
            except (ValueError,OSError,RuntimeError):
                col.label(text="Native work queue unavailable",icon="ERROR")
            col.prop(scene,"render_studio_plan_id",text="Plan ID")
            col.operator("renderstudio.pause_native_plan",icon="PAUSE")
            col.operator("renderstudio.resume_native_plan",icon="PLAY")
            try:
                import render_native_hud
                recent=render_native_hud.snapshot()
                if recent.get("status"):
                    stage=recent["status"].get("stage","")
                    col.label(text="Live: "+str(stage)[:45])
            except (ImportError,AttributeError,RuntimeError):pass
        layout.separator()
        layout.label(text="Native edit tabs, not proprietary binaries")

_CLASSES=(RENDERSTUDIO_OT_open_native_editor,RENDERSTUDIO_OT_native_mode,
          RENDERSTUDIO_OT_plan_pause,RENDERSTUDIO_OT_plan_resume,
          RENDERSTUDIO_PT_unified)

def install_ui():
    global INSTALLED
    if INSTALLED or bpy.app.background:return
    if not hasattr(bpy.types.Scene,"render_studio_section"):
        bpy.types.Scene.render_studio_section=bpy.props.EnumProperty(
            name="Production Area",items=SECTIONS,default="agent",
            update=lambda self,context:self.__setitem__("render_studio_active_section",self.render_studio_section))
    if not hasattr(bpy.types.Scene,"render_studio_plan_id"):
        bpy.types.Scene.render_studio_plan_id=bpy.props.StringProperty(
            name="Native Plan ID",maxlen=32,default="")
    for klass in _CLASSES:
        bpy.utils.register_class(klass)
    INSTALLED=True
    install_timer()

def uninstall_ui():
    global INSTALLED
    if INSTALLED:
        for klass in reversed(_CLASSES):
            try:bpy.utils.unregister_class(klass)
            except RuntimeError:pass
    INSTALLED=False
