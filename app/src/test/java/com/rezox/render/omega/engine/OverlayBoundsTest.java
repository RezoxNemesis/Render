package com.rezox.render.omega.engine;

import org.junit.Test;
import static org.junit.Assert.*;

public class OverlayBoundsTest {
    @Test public void portraitAndLandscapeHandleRemainReachable(){
        assertEquals(8,OverlayBounds.clampTop(-250,720,200,8));
        assertEquals(512,OverlayBounds.clampTop(10000,720,200,8));
        assertEquals(100,OverlayBounds.clampTop(100,720,200,8));
        assertEquals(8,OverlayBounds.clampTop(800,80,110,8));
        assertEquals(300,OverlayBounds.scrollHeight(300,1000,100));
        assertEquals(115,OverlayBounds.scrollHeight(800,115,80));
    }
    @Test public void tapAndDragDisambiguationDoesNotReinterpretBlenderTouches(){
        assertTrue(OverlayBounds.isTap(12,12,16,14,8));
        assertFalse(OverlayBounds.isTap(12,12,12,45,8));
        try{OverlayBounds.isTap(0,0,Float.NaN,0,8);fail();}
        catch(IllegalArgumentException expected){}
        try{OverlayBounds.scrollHeight(-1,100,80);fail();}
        catch(IllegalArgumentException expected){}
    }
}
