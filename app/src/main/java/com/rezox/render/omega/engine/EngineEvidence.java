package com.rezox.render.omega.engine;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.FeatureInfo;
import android.content.pm.PackageManager;
import android.app.ActivityManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.SystemClock;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.concurrent.TimeUnit;

/**
 * Device-owner local engine evidence. An Android Activity launch is not proof
 * that Blender actually produced a Vulkan frame. No private filenames, tokens,
 * reference media or project data are recorded.
 */
public final class EngineEvidence {
    public static final String PREF = "omega_render_engine_events";
    private static final String KEY = "events";
    private static final int MAX_EVENTS = 24;
    private EngineEvidence(){}

    public enum Stage {
        LAUNCHER_ACTIVITY_CREATED, PREFLIGHT_ACCEPTED, LIBRARY_VALIDATED, RUNTIME_CACHE_REUSED,
        RUNTIME_ZIP_HASHED, RUNTIME_EXTRACTION_STARTED, RUNTIME_ACTIVATED,
        NATIVE_LIBRARY_LOADED, EDITOR_ACTIVITY_REQUESTED,
        NATIVE_CONTROLS_ATTACHED, CONTROLS_DETACHED, PREFLIGHT_FAILED
    }
    /** Thread safe, bounded and exclusively app-private; truthful events only. */
    public static synchronized void record(Context context, Stage stage){
        SharedPreferences prefs=context.getApplicationContext().getSharedPreferences(
                PREF,Context.MODE_PRIVATE);
        try{
            JSONArray events=new JSONArray(prefs.getString(KEY,"[]"));
            JSONArray next=new JSONArray();
            for(int i=Math.max(0,events.length()-(MAX_EVENTS-1));i<events.length();i++)
                next.put(events.getJSONObject(i));
            JSONObject value=new JSONObject()
                .put("stage",stage.name())
                .put("elapsed_ms",SystemClock.elapsedRealtime())
                .put("wall_ms",System.currentTimeMillis());
            next.put(value);
            prefs.edit().putString(KEY,next.toString()).putString("last_stage",stage.name())
                .putLong("last_wall_ms",System.currentTimeMillis()).commit();
        }catch(Exception ignored){
            // Loss of diagnostics must never prevent real Blender startup.
        }
    }
    public static synchronized JSONArray events(Context context){
        String text=context.getApplicationContext().getSharedPreferences(
            PREF,Context.MODE_PRIVATE).getString(KEY,"[]");
        try{return new JSONArray(text);}catch(Exception ignored){return new JSONArray();}
    }
    public static JSONObject snapshot(Context context){
        JSONObject output=new JSONObject();
        try{
            PackageManager packageManager=context.getPackageManager();
            JSONObject vulkan=new JSONObject().put("advertised",false);
            FeatureInfo[] features=packageManager.getSystemAvailableFeatures();
            if(features!=null)for(FeatureInfo feature:features){
                if(feature!=null&&PackageManager.FEATURE_VULKAN_HARDWARE_VERSION.equals(feature.name)){
                    int version=feature.version;
                    vulkan.put("advertised",true)
                        .put("major",(version>>22)&0x3ff)
                        .put("minor",(version>>12)&0x3ff)
                        .put("patch",version&0xfff);
                }
            }
            ActivityManager am=context.getSystemService(ActivityManager.class);
            ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();
            if(am!=null)am.getMemoryInfo(memory);
            JSONObject mem=new JSONObject()
                .put("available_bytes",am==null?JSONObject.NULL:memory.availMem)
                .put("low_memory",am!=null&&memory.lowMemory);
            PowerManager power=context.getSystemService(PowerManager.class);
            Object thermal=JSONObject.NULL;
            if(power!=null&&Build.VERSION.SDK_INT>=29){
                try{thermal=power.getCurrentThermalStatus();}
                catch(RuntimeException unsupported){/* Keep other evidence available. */}
            }
            return output.put("schema","RENDER-OMEGA-P01-1")
                .put("android_api",Build.VERSION.SDK_INT)
                .put("device_model",Build.MODEL==null?"unknown":Build.MODEL)
                .put("native_engine","Blender Android shared library (not independently attested by this query)")
                .put("vulkan",vulkan).put("memory",mem)
                .put("thermal_status",thermal)
                .put("gpu_driver_version",JSONObject.NULL)
                .put("native_vulkan_frame_observed",false)
                .put("activity_launch_is_frame_proof",false)
                .put("quality_reduced",false)
                .put("events",events(context));
        }catch(Exception problem){
            try{return output.put("diagnostics_incomplete",problem.getClass().getSimpleName())
                .put("native_vulkan_frame_observed",false)
                .put("quality_reduced",false);}catch(Exception ignored){return output;}
        }
    }
    public static String text(Context context){
        JSONObject s=snapshot(context);
        String last="no observed native startup event";
        JSONArray events=s.optJSONArray("events");
        if(events!=null&&events.length()>0)
            last=events.optJSONObject(events.length()-1).optString("stage",last);
        JSONObject vulkan=s.optJSONObject("vulkan");
        return "Last observed engine stage: "+last+
            "\nVulkan advertised by Android: "+(vulkan!=null&&vulkan.optBoolean("advertised",false))+
            "\nNative frame actually verified: NO (viewport screenshot/capture required)"+
            "\nGPU driver version: not available from this evidence";
    }
}
