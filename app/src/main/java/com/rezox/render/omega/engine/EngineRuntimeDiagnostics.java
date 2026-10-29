package com.rezox.render.omega.engine;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.io.File;
import java.util.Arrays;

/** Read-only diagnosis from known private logs, never from an arbitrary caller path. */
public final class EngineRuntimeDiagnostics {
    private EngineRuntimeDiagnostics(){}
    public static JSONObject inspect(Context context)throws Exception {
        SharedPreferences state=context.getSharedPreferences("render_editor_launch",Context.MODE_PRIVATE);
        File current=new File(context.getFilesDir(),"blender-startup.log");
        File previous=new File(context.getFilesDir(),"blender-startup.previous.log");
        EngineStartupLog.Selection selected=EngineStartupLog.select(current,Arrays.asList(current,previous),
            state.getLong("launch_started_wall_ms",0));
        JSONObject result=new JSONObject().put("current_launch_log",selected.current)
            .put("failure_classified",false).put("runtime_compatibility_verified",false);
        if(selected.file!=null){
            try{
                String code=EngineStartupLog.failureCode(EngineStartupLog.readTail(selected.file,32000),selected.current);
                if(!code.isEmpty())result.put("failure_classified",true).put("failure_code",code)
                    .put("category","runtime_compatibility").put("message",EngineStartupLog.failureMessage(code))
                    .put("automatic_retry_safe",false);
            }catch(java.io.IOException unavailable){result.put("log_read_unavailable",true);}
        }
        return result;
    }
}
