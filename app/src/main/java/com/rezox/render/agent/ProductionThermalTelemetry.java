package com.rezox.render.agent;

import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.os.SystemClock;
import org.json.JSONObject;

/** Exposes the raw Android signal and independent battery telemetry for diagnosing
 * genuine throttling, without blindly overriding PowerManager decisions.
 */
public final class ProductionThermalTelemetry {
    private ProductionThermalTelemetry(){}
    public static JSONObject sample(Context context)throws Exception{
        PowerManager power=context.getSystemService(PowerManager.class);
        ActivityManager am=context.getSystemService(ActivityManager.class);
        ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();
        if(am!=null)am.getMemoryInfo(memory);
        int status=-1;
        double headroom=Double.NaN;
        if(power!=null){
            try{status=power.getCurrentThermalStatus();}catch(RuntimeException ignored){status=-1;}
            if(Build.VERSION.SDK_INT>=30){
                try{headroom=power.getThermalHeadroom(10);}catch(RuntimeException ignored){headroom=Double.NaN;}
            }
        }
        Intent sticky=null;
        try{sticky=context.registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));}catch(RuntimeException ignored){}
        double batteryC=Double.NaN;
        if(sticky!=null){
            int deciC=sticky.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1);
            if(deciC>=-200 && deciC<=1100)batteryC=deciC/10.0;
        }
        JSONObject data=new JSONObject().put("source","Android PowerManager")
            .put("thermal_status",status).put("thermal_label",ProductionThermalPolicy.label(status))
            .put("sample_uptime_ms",SystemClock.elapsedRealtime())
            .put("available_memory_bytes",memory.availMem)
            .put("total_memory_bytes",memory.totalMem)
            .put("low_memory",memory.lowMemory);
        if(!Double.isNaN(headroom)&&Double.isFinite(headroom)&&headroom>=0)
            data.put("thermal_headroom_10s",headroom);
        else data.put("thermal_headroom_10s",JSONObject.NULL);
        if(!Double.isNaN(batteryC))data.put("battery_temperature_celsius",batteryC);
        else data.put("battery_temperature_celsius",JSONObject.NULL);
        data.put("battery_temperature_is_cpu_temperature",false)
            .put("finger_touch_is_reliable_thermal_measurement",false)
            .put("thermal_status_does_not_lower_render_quality",true);
        return data;
    }
}