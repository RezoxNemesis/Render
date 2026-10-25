package com.rezox.render.agent;

import android.content.Context;
import android.os.Process;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** Freshness alone cannot distinguish a live engine from the previous process. */
public final class NativeHeartbeat {
    private NativeHeartbeat() {}
    public static boolean ready(Context context) {
        if(context==null)return false;
        File file=new File(context.getFilesDir(),"render_bpy_jobs/ready");
        long age=System.currentTimeMillis()-file.lastModified();
        return age>=0&&age<15000&&observedCurrentProcess(context);
    }
    /** Initialization evidence only: a busy Blender timer is not fresh readiness. */
    public static boolean observedCurrentProcess(Context context) {
        if(context==null)return false;
        File file=new File(context.getFilesDir(),"render_bpy_jobs/ready");
        if(!file.isFile()||file.length()<1||file.length()>32||Files.isSymbolicLink(file.toPath()))return false;
        try {
            if(!Integer.toString(Process.myPid()).equals(new String(Files.readAllBytes(file.toPath()),StandardCharsets.US_ASCII).trim()))return false;
            File state=new File(context.getFilesDir(),"render_bpy_jobs/ready-state.json");
            if(!state.isFile()||state.length()>1024||Files.isSymbolicLink(state.toPath()))return false;
            org.json.JSONObject receipt=new org.json.JSONObject(new String(Files.readAllBytes(state.toPath()),StandardCharsets.UTF_8));
            String launch=com.rezox.render.NativeEditorConfiguration.launchId();
            return !launch.isEmpty()&&launch.equals(receipt.optString("launch_id"))&&receipt.optInt("pid",-1)==Process.myPid();
        }catch(Exception ignored){return false;}
    }
}
