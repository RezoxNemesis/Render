package com.rezox.render.agent;

import java.util.UUID;

/** Public, non-credential setup card for the standalone Render Studio MCP. */
public final class RenderConnectionCard {
    public static final String APP="Render Studio";
    public static final String PACKAGE="com.rezox.render";
    public static final String ACTION_PREFIX="render.";
    public static final String TRANSPORT="Render Studio dedicated HTTPS MCP";
    private RenderConnectionCard(){}

    public static boolean validPublicId(String value){
        if(value==null||!value.matches("[a-f0-9-]{36}"))return false;
        try{return UUID.fromString(value).toString().equals(value);}
        catch(IllegalArgumentException e){return false;}
    }
    public static String renderDeviceLabel(String publicId){
        if(!validPublicId(publicId))throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        return "Render Android "+publicId;
    }
    public static String shareText(String publicId,boolean paired,boolean running){
        return shareText(publicId,paired,running,PACKAGE);
    }
    public static String shareText(String publicId,boolean paired,boolean running,String installedPackage){
        if(!validPublicId(publicId))throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        if(!PACKAGE.equals(installedPackage)&&!(PACKAGE+".preview").equals(installedPackage))
            throw new IllegalArgumentException("INVALID_RENDER_PACKAGE");
        String state=!paired?"Not paired; pair this device with a one-use enrollment code"
            :!running?"Paired on Android; agent session stopped"
            :"Paired and agent session requested; native command result not yet verified";
        return "CONNECT / CONTROL TARGET: RENDER STUDIO (NATIVE BLENDER)\n"
            +"Application: "+installedPackage+"\nPublic Render app ID: "+publicId+"\n"
            +"Transport: "+TRANSPORT+"\n"
            +"Dedicated MCP endpoint: "+RenderDirectMcp.MCP_ENDPOINT+"\n"
            +"Local state: "+state+"\n\n"
            +"Use the dedicated Render Studio MCP connector, not the VideoStudio MCP or Android Binder. "
            +"Authorize the ChatGPT Render Studio connection using the short-lived link code generated inside Render Studio. "
            +"With the Android agent session running, call render_status or render_capabilities before submitting work. "
            +"Use render_submit and poll render_job for each native command; use render_cancel when needed. "
            +"Inspect native editor readiness and the supported operations before attempting any mutation. "
            +"Only a completed Android-native receipt proves that a Blender action actually ran. "
            +"No cloud Blender execution, Gallery browsing or guessed rendered frames.";
    }
}
