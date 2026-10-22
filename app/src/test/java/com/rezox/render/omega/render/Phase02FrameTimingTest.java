package com.rezox.render.omega.render;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import com.rezox.render.agent.ProductionVideoEncoder;
import org.junit.Test;

/** Pure JVM contract: exact Blender fps/fps_base timestamp calculation.
 * Actual H.264 MediaCodec/muxer fidelity still requires an Android device. */
public final class Phase02FrameTimingTest {
    @Test public void integerFpsRemains24() {
        assertEquals(0L, ProductionVideoEncoder.framePresentationTimeUs(0,24,1.0));
        assertEquals(41667L, ProductionVideoEncoder.framePresentationTimeUs(1,24,1.0));
        assertEquals(1000000L, ProductionVideoEncoder.framePresentationTimeUs(24,24,1.0));
    }

    @Test public void fractionalFpsIsNotSilentlyRounded() {
        assertEquals(41708L, ProductionVideoEncoder.framePresentationTimeUs(1,24,1.001));
        assertEquals(1001000L, ProductionVideoEncoder.framePresentationTimeUs(24,24,1.001));
        assertEquals(5005000L, ProductionVideoEncoder.framePresentationTimeUs(120,24,1.001));
        long previous = -1;
        for (int frame=0; frame<105; frame++) {
            long now = ProductionVideoEncoder.framePresentationTimeUs(frame,24,1.001);
            assertTrue(now > previous);
            previous=now;
        }
    }

    @Test public void invalidTimingIsRejected() {
        for (double base : new double[] {-1.0, 0.0, Double.NaN,
                                           Double.POSITIVE_INFINITY, 101.0}) {
            try {
                ProductionVideoEncoder.framePresentationTimeUs(1,24,base);
                throw new AssertionError("invalid timing accepted");
            } catch (IllegalArgumentException expected) {
                assertEquals("INVALID_FPS_TIMING",expected.getMessage());
            }
        }
    }
}
