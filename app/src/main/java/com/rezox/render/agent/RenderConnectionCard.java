package com.rezox.render.agent;

import java.util.Locale;
import java.util.UUID;

/** Public identity only. Never include the VideoStudio private credential. */
public final class RenderConnectionCard {
    public static final String APP="Render Studio";
    public static final String PACKAGE="com.rezox.render";
    public static final String VIDEOSTUDIO_PACKAGE="com.rezoxnemesis.videostudio";
    public static final long MIN_VIDEOSTUDIO_BUILD=354;
    public static final long PRODUCTION_CARRIER_BUILD=355;
    public static final String TRANSPORT="VideoStudio MCP v3 -> native Android Binder";
    public static final String ACTION_PREFIX="render.";
    private RenderConnectionCard(){}
    public static boolean validPublicId(String value){
        if(value==null||!value.matches("[a-f0-9-]{36}"))return false;
        try{return UUID.fromString(value).toString().equals(value);}catch(IllegalArgumentException e){return false;}
    }
    public static String renderDeviceLabel(String publicId){
        if(!validPublicId(publicId))throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        return "Render Android "+publicId;
    }
    public static String shareText(String publicId,boolean enabled,boolean videoInstalled){
        return shareText(publicId,enabled,videoInstalled,PACKAGE);
    }
    public static String shareText(String publicId,boolean enabled,boolean videoInstalled,String installedPackage){
        if(!validPublicId(publicId))throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        if(!PACKAGE.equals(installedPackage)&&!(PACKAGE+".preview").equals(installedPackage))throw new IllegalArgumentException("INVALID_RENDER_PACKAGE");
        String state=enabled&&videoInstalled?"Enabled on Android; awaiting a real native command result":enabled?"Enabled but compatible VideoStudio app not detected":"Stopped on this Android device";
        return "CONNECT / CONTROL TARGET: RENDER STUDIO (NATIVE BLENDER)\n"
            +"Application: "+installedPackage+"\nPublic Render app ID: "+publicId+"\n"
            +"Transport: "+TRANSPORT+"\nLocal state: "+state+"\n\n"
            +"Use the EXISTING VideoStudio MCP. First call device_status/app_status with the current owner-provided private credential; do not use this public Render ID as deviceId or reuse a stale credential from another installation. "
            +"Then queue_video_edit(projectId=active-native, action=autonomous_request), parameters.nativeAction=render.engine.status, parameters.nativeParameters={target_package:'"+installedPackage+"'}. "
            +"Poll get_video_command_result for that exact command ID. Require target_app=Render Studio, target_package="+installedPackage+", and render_public_id="+publicId+". "
            +"Next call render.production.execute with nativeParameters={target_package:'"+installedPackage+"',operation:'capabilities',payload:{}}. "
            +"All later production operations require target_id:'"+publicId+"' and the same target_package. Read capabilities and editor readiness before choosing tools. "
            +"If production.execute is unavailable, the VideoStudio carrier needs the tested 3.5.5 production update; this is not an offline-device error. "
            +"Create, inspect, checkpoint, render, capture and export only supported operations. Poll native results; do not blindly replay uncertain mutations. "
            +"Render preview and original data are separate. No new MCP or relay, no cloud Blender execution, no Gallery browsing. "
            +"Only Android-native completion evidence proves a command ran.";
    }
    public static String localStatus(String publicId,boolean enabled,long videoBuild,long lastResultMillis){
        if(!validPublicId(publicId))throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        if(!enabled)return "STOPPED / VideoStudio cannot control Render. Public ID: "+publicId;
        if(videoBuild<MIN_VIDEOSTUDIO_BUILD)return "NOT READY / Install or update VideoStudio Native Agent v3.5.4+ (build 354).";
        if(lastResultMillis<=0)return "READY ON PHONE / Waiting for first confirmed Render command from VideoStudio MCP.";
        return "NATIVE COMMAND CONFIRMED / Last Render result at "+new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss",Locale.ROOT).format(new java.util.Date(lastResultMillis))+".";
    }
}
