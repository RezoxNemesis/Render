package com.rezox.render.agent;

import org.json.JSONObject;

/** The batch admission window and the time needed for one frame are distinct. */
public final class NativeCommandBudget {
    public static final long FRAME_TIMEOUT_MS = 6L * 60 * 60 * 1000;
    private NativeCommandBudget() {}

    public static boolean frame(String action, JSONObject args) {
        return "blender.production.execute".equals(action)
                && "render.step".equals(args.optString("operation"));
    }

    public static long timeout(String action, JSONObject args, long ordinaryTimeout) {
        return frame(action, args) ? FRAME_TIMEOUT_MS : ordinaryTimeout;
    }
}
