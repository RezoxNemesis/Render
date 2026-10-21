package com.rezox.render.agent;

import org.junit.Test;
import static org.junit.Assert.*;

public class VideoStudioNativeBridgePolicyTest {
    @Test public void acceptsOnlyRealVideoStudioPackage() {
        assertTrue(VideoStudioNativeBridgeService.trustedCallerPackages(
            new String[]{"com.rezoxnemesis.videostudio"}));
        assertTrue(VideoStudioNativeBridgeService.trustedCallerPackages(
            new String[]{"com.other", "com.rezoxnemesis.videostudio"}));
        for(String[] packages : new String[][]{
                {}, {"com.fake.videostudio"}, {"com.rezox.render"},
                {"com.rezoxnemesis.videostudio.malicious"}})
            assertFalse(VideoStudioNativeBridgeService.trustedCallerPackages(packages));
        assertFalse(VideoStudioNativeBridgeService.trustedCallerPackages(null));
    }
}
