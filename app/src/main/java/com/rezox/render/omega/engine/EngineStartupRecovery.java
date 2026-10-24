package com.rezox.render.omega.engine;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.UUID;

/** A restored task must not repeatedly launch a native engine that just crashed. */
public final class EngineStartupRecovery {
    public static final String EXTRA_REQUEST="render.explicit_editor_request";
    private static final String PREF="render_editor_launch";
    private static volatile boolean nativeStartInProcess;
    public static boolean launchInFlight(){return nativeStartInProcess;}
    public static void preparationFailed(){nativeStartInProcess=false;}
    private EngineStartupRecovery(){}
    private static SharedPreferences prefs(Context context){
        return context.getApplicationContext().getSharedPreferences(PREF,Context.MODE_PRIVATE);
    }
    /** One fresh request is issued by an actual owner or authenticated editor.open command. */
    public static synchronized String request(Context context){
        String id=UUID.randomUUID().toString();
        if(!prefs(context).edit().putString("authorized_editor_request",id).commit())
            throw new IllegalStateException("EDITOR_RECOVERY_STATE_NOT_WRITABLE");
        return id;
    }
    public static synchronized boolean allowAutomaticStart(Context context,String request){
        SharedPreferences state=prefs(context);
        if(request!=null&&request.equals(state.getString("authorized_editor_request",null))){
            if(!state.edit().remove("authorized_editor_request").commit())
                throw new IllegalStateException("EDITOR_RECOVERY_STATE_NOT_WRITABLE");
            return true;
        }
        return !state.getBoolean("native_launch_pending",false);
    }
    public static synchronized void markPending(Context context){
        nativeStartInProcess=true;
        if(!prefs(context).edit().putBoolean("native_launch_pending",true).commit())
            throw new IllegalStateException("EDITOR_RECOVERY_STATE_NOT_WRITABLE");
    }
    /** Called only after the native editor has produced a fresh bpy heartbeat. */
    public static synchronized void markReady(Context context){
        prefs(context).edit().putBoolean("native_launch_pending",false).apply();
    }
}
