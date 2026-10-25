package com.rezox.render.agent;

import android.content.Context;
import android.os.SystemClock;
import org.json.JSONObject;

/**
 * One authenticated lightweight status call even when native Blender is busy
 * rendering a frame. No arbitrary file paths, auth credentials or owner media.
 * Distinguishes app heartbeat from an actually executing artist operation.
 */
public final class NativeAgentFastStatus {
    private NativeAgentFastStatus(){}

    private static boolean flag(JSONObject p,String key)throws Exception{
        if(!p.has(key))return false;
        Object value=p.get(key);
        if(!(value instanceof Boolean))
            throw new IllegalArgumentException("STUDIO_AGENT_FLAG_INVALID");
        return ((Boolean)value).booleanValue();
    }

    public static JSONObject read(Context context,JSONObject p)throws Exception{
        ProductionBridge.fields(p,"include_plans,include_thermal,include_render_queue");
        boolean plans=flag(p,"include_plans");
        boolean thermal=flag(p,"include_thermal");
        boolean queue=flag(p,"include_render_queue");
        long start=SystemClock.elapsedRealtimeNanos();
        boolean editor=NativeHeartbeat.ready(context);
        AgentWorkPresence.Snapshot work=AgentWorkPresence.snapshot(context);
        boolean running=work.isWorking();
        JSONObject result=new JSONObject()
            .put("source","Android native Render app, not ChatGPT model memory")
            .put("contract","render.studio.agent.fastlane.v1")
            .put("native_editor_heartbeat_ready",editor)
            .put("last_native_action",work.displayAction())
            .put("native_work_state",work.state)
            .put("native_work_stage",work.displayStage())
            .put("native_work_progress_percent",work.progress)
            .put("running_action_confirmed",running&&editor)
            .put("native_scene_editor_available",editor)
            .put("background_render_safely_paused_after_force_stop_guaranteed",false)
            .put("operator_command_or_script_executed",false);
        if(plans){
            // Sanitized, bounded owner-private receipts. Does not access bpy.
            result.put("plans",NativeStudioPlanStatus.list(context,new JSONObject()));
        }
        if(thermal){
            JSONObject raw=ProductionThermalTelemetry.sample(context);
            result.put("device_thermal",new JSONObject()
                .put("thermal_status",raw.optInt("thermal_status",-1))
                .put("low_memory",raw.optBoolean("low_memory",false))
                .put("available_memory_bytes",raw.optLong("available_memory_bytes",-1)));
        }
        if(queue)result.put("render_queue",RenderJobQueue.status(context));
        result.put("native_status_elapsed_ms",
            Math.max(0L,(SystemClock.elapsedRealtimeNanos()-start)/1000000L));
        return result;
    }
}
