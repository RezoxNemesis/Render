package com.rezox.render.agent;
import org.junit.Test;
import static org.junit.Assert.*;

/** A native command may keep the CPU awake only for a finite command window. */
public final class NativeWakeGuardTest {
    @Test public void renderIsBoundedAndOtherCallsShort(){
        assertEquals(1_830_000L,NativeWakeGuard.timeoutForAction("blender.scene.render_video"));
        assertEquals(510_000L,NativeWakeGuard.timeoutForAction("blender.scene.render_still"));
        assertEquals(150_000L,NativeWakeGuard.timeoutForAction("blender.scene.populate_lively"));
        assertEquals(50_000L,NativeWakeGuard.timeoutForAction("blender.scene.summary"));
        assertTrue(NativeWakeGuard.timeoutForAction("blender.scene.render_video")<31*60*1000L);
    }
}