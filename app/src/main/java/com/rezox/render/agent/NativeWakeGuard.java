package com.rezox.render.agent;

import android.content.Context;
import android.os.PowerManager;

/**
 * Bounded CPU wake lock for user-authorized native Blender work only.
 * This does NOT bypass Android app lifecycle, thermal limits or GPU restrictions.
 */
public final class NativeWakeGuard implements AutoCloseable {
    private static final long SAFETY_MARGIN_MS=30_000L;
    private final PowerManager.WakeLock lock;

    private NativeWakeGuard(PowerManager.WakeLock held){lock=held;}

    public static long timeoutForAction(String action){
        if("blender.scene.render_video".equals(action))return 1_800_000L+SAFETY_MARGIN_MS;
        if("blender.scene.render_still".equals(action))return 480_000L+SAFETY_MARGIN_MS;
        if("blender.project.save_copy".equals(action) ||
           "blender.scene.populate_lively".equals(action) ||
           "blender.scene.create_lively_project".equals(action) ||
           "blender.scene.batch_assembly".equals(action))
            return 120_000L+SAFETY_MARGIN_MS;
        return 20_000L+SAFETY_MARGIN_MS;
    }

    public static NativeWakeGuard acquire(Context context,String action){
        if(action==null || !action.startsWith("blender."))
            return new NativeWakeGuard(null);
        PowerManager pm=context.getSystemService(PowerManager.class);
        if(pm==null)return new NativeWakeGuard(null);
        PowerManager.WakeLock wl=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                "RenderStudio:NativeBlender");
        wl.setReferenceCounted(false);
        wl.acquire(timeoutForAction(action));
        return new NativeWakeGuard(wl);
    }

    @Override public void close(){
        if(lock!=null && lock.isHeld())lock.release();
    }
}
