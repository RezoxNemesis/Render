package com.rezox.render.agent;

import org.junit.Test;
import static org.junit.Assert.*;

/** Pure JVM acceptance of admission gates before full Blender video import. */
public class NativeVideoReferencePolicyTest {
    @Test public void keepsOriginalMovieUnderThermalOrMemoryPressure(){
        long mb=1024L*1024L;
        NativeVideoReferencePolicy.requireAllowed("mp4",true,false,1200*mb,128*mb);
        for(long available:new long[]{0,128*mb,300*mb,319*mb}){
            try{
                NativeVideoReferencePolicy.requireAllowed("mp4",true,false,available,128*mb);
                fail("Accepted scarce video memory "+available);
            }catch(IllegalStateException expected){
                assertTrue(expected.getMessage().contains("ORIGINAL_RETAINED"));
            }
        }
        try{NativeVideoReferencePolicy.requireAllowed("mp4",false,false,1200*mb,128*mb);fail();}
        catch(IllegalStateException expected){assertTrue(expected.getMessage().contains("THERMAL"));}
        try{NativeVideoReferencePolicy.requireAllowed("mp4",true,true,1200*mb,128*mb);fail();}
        catch(IllegalStateException expected){assertTrue(expected.getMessage().contains("MEMORY"));}
        try{NativeVideoReferencePolicy.requireAllowed("pdf",true,false,1200*mb,128*mb);fail();}
        catch(IllegalArgumentException expected){assertEquals("NATIVE_TIMELINE_REFERENCE_MP4_REQUIRED",expected.getMessage());}
    }
    @Test public void samplePreviewMustFitMemoryAndBeFiniteSize(){
        long mb=1024L*1024L;
        NativeVideoReferencePolicy.requirePreviewFits(1920,1080,600*mb,128*mb);
        try{NativeVideoReferencePolicy.requirePreviewFits(16000,16000,500*mb,128*mb);fail();}
        catch(IllegalStateException expected){assertTrue(expected.getMessage().contains("ORIGINAL_RETAINED"));}
        for(int bad: new int[]{0,-1}){
            try{NativeVideoReferencePolicy.requirePreviewFits(bad,10,1000*mb,0);fail();}
            catch(IllegalArgumentException expected){assertEquals("INVALID_NATIVE_REFERENCE_DIMENSIONS",expected.getMessage());}
        }
    }
}
