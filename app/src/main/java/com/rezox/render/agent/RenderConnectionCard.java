package com.rezox.render.agent;

import java.util.Locale;
import java.util.UUID;

/**
 * Non-secret, stable Render identity for Android share sheets and ChatGPT
 * prompts. The original VideoStudio owner secret is NEVER copied or exposed.
 */
public final class RenderConnectionCard {
    public static final String APP = "Render Studio";
    public static final String PACKAGE = "com.rezox.render";
    public static final String VIDEOSTUDIO_PACKAGE = "com.rezoxnemesis.videostudio";
    public static final long MIN_VIDEOSTUDIO_BUILD = 350;
    public static final String TRANSPORT = "VideoStudio MCP v3 -> native Android Binder";
    public static final String ACTION_PREFIX = "render.";

    private RenderConnectionCard() {}

    public static boolean validPublicId(String value) {
        if (value == null || !value.matches("[a-f0-9-]{36}")) return false;
        try { return UUID.fromString(value).toString().equals(value); }
        catch (IllegalArgumentException e) { return false; }
    }

    public static String renderDeviceLabel(String publicId) {
        if (!validPublicId(publicId)) throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        return "Render Android " + publicId;
    }

    public static String shareText(String publicId, boolean locallyEnabled, boolean videoInstalled) {
        if (!validPublicId(publicId)) throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        String state = locallyEnabled && videoInstalled ?
            "Enabled on Android; awaiting a real native command result" :
            locallyEnabled ? "Enabled but compatible VideoStudio app not detected" :
            "Stopped on this Android device";
        return "CONNECT / CONTROL TARGET: RENDER STUDIO (NATIVE BLENDER)\n"
            + "Application: " + PACKAGE + "\n"
            + "Public Render app ID: " + publicId + "\n"
            + "Transport: " + TRANSPORT + "\n"
            + "Local state: " + state + "\n\n"
            + "This app is NOT VideoStudio. Use the EXISTING connected VideoStudio MCP "
            + "with its queue_video_edit tool (projectId: active-native, action: autonomous_request), "
            + "setting parameters.nativeAction to render.engine.status "
            + "and parameters.nativeParameters to {}. "
            + "Poll get_video_command_result for the returned command ID. "
            + "Any native result must identify target_app=Render Studio and match this public Render app ID. "
            + "Other allowed Render actions use the render. prefix. "
            + "The original VideoStudio projects and credentials are separate. "
            + "No new MCP or relay, and no cloud Blender execution. "
            + "Only Android-native completion evidence proves a command ran.";
    }

    public static String localStatus(String publicId, boolean enabled, long videoBuild, long lastResultMillis) {
        if (!validPublicId(publicId)) throw new IllegalArgumentException("INVALID_RENDER_PUBLIC_ID");
        if (!enabled) return "STOPPED / VideoStudio cannot control Render. Public ID: " + publicId;
        if (videoBuild < MIN_VIDEOSTUDIO_BUILD)
            return "NOT READY / Install or update VideoStudio Native Agent v3.5.0+ (build 350).";
        if (lastResultMillis <= 0)
            return "READY ON PHONE / Waiting for first confirmed Render command from VideoStudio MCP.";
        return "NATIVE COMMAND CONFIRMED / Last Render result at " +
            new java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.ROOT)
                .format(new java.util.Date(lastResultMillis)) + ".";
    }
}
