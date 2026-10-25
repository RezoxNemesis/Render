package com.rezox.render.agent;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;

/** Work admission/pacing only. Cannot lower native scene or output quality. */
public final class RenderScheduling {
    private RenderScheduling(){}
    private static SharedPreferences prefs(Context c){return c.getApplicationContext()
        .getSharedPreferences("render_scheduling_v1",Context.MODE_PRIVATE);}
    static long reserve(Context c){return (c==null?256:prefs(c).getInt("memory_reserve_mib",256))*1024L*1024;}
    static long gap(Context c){return c==null?0:prefs(c).getInt("minimum_frame_gap_ms",0);}
    static ProductionThermalPolicy.Decision evaluate(Context c,JSONObject reading,boolean cancelled){
        long memory=reading.optLong("available_memory_bytes",-1);
        if(memory>=0)memory=Math.max(0,memory-Math.max(0,reserve(c)-256L*1024*1024));
        return ProductionThermalPolicy.evaluate(reading.optInt("thermal_status",-1),
            reading.optBoolean("low_memory",false),memory,cancelled);
    }
    public static JSONObject execute(Context c,JSONObject p,boolean configure)throws Exception{
        ProductionBridge.fields(p,configure?"memory_reserve_mib,minimum_frame_gap_ms":"");
        SharedPreferences values=prefs(c);
        int reserve=(int)ProductionBridge.integer(p,"memory_reserve_mib",256,4096,values.getInt("memory_reserve_mib",256));
        int gap=(int)ProductionBridge.integer(p,"minimum_frame_gap_ms",0,60000,values.getInt("minimum_frame_gap_ms",0));
        if(configure&&!values.edit().putInt("memory_reserve_mib",reserve).putInt("minimum_frame_gap_ms",gap).commit())
            throw new IllegalStateException("SCHEDULING_SETTINGS_NOT_WRITABLE");
        return new JSONObject().put("memory_reserve_mib",reserve).put("minimum_frame_gap_ms",gap)
            .put("thermal_protection_enabled",true).put("quality_settings_changed",false)
            .put("takes_effect","next frame admission; never interrupts a committed native frame");
    }
    public static void showControls(Activity activity){
        String[] labels={"256 MiB reserve (default)","512 MiB reserve","1024 MiB reserve","Add 1.5s between frames","Remove extra frame gap"};
        new AlertDialog.Builder(activity).setTitle("Render scheduling")
            .setItems(labels,(dialog,index)->{
                try{
                    JSONObject p=new JSONObject();
                    if(index<3)p.put("memory_reserve_mib",new int[]{256,512,1024}[index]);
                    else p.put("minimum_frame_gap_ms",index==3?1500:0);
                    execute(activity,p,true);
                }catch(Exception error){android.widget.Toast.makeText(activity,error.getMessage(),android.widget.Toast.LENGTH_LONG).show();}
            }).setNegativeButton("Close",null).show();
    }
}
