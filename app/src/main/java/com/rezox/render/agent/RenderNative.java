package com.rezox.render.agent;

/** Calls the same original native implementation used by Render's current UI. */
public final class RenderNative {
    static { System.loadLibrary("render_bridge"); }
    private RenderNative() {}
    public static native String engineStatus();
    public static native String inspectProject(String localPath);
    public static native String gpuInfo();
}
