package com.rezox.render.agent;
import org.junit.Test;
import static org.junit.Assert.*;

/** Filename validation runs without Android filesystem access. */
public class RenderVideoExportTest {
    @Test public void acceptsOnlyBlenderGeneratedVideoNames() {
        assertTrue(RenderVideoExport.isRenderVideoName(
                "RenderVideo_0123456789abcdef0123456789abcdef0001-0192.mp4"));
        assertTrue(RenderVideoExport.isRenderVideoName(
                "RenderVideo_0123456789abcdef0123456789abcdef.mp4"));
        for(String forbidden:new String[]{
                "../video.mp4", "/storage/emulated/0/private.mp4",
                "movie.mp4", "RenderVideo_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mp4.exe",
                "RenderVideo_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\\unsafe.mp4",
                "RenderVideo_nothex.mp4"}) {
            assertFalse(forbidden,RenderVideoExport.isRenderVideoName(forbidden));
        }
    }
}
