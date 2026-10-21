package com.rezox.render.agent;

import org.junit.Test;
import static org.junit.Assert.*;

public class RenderConnectionCardTest {
    private static final String ID="c1378302-1f20-4c7c-884e-50317b20bd02";
    @Test public void identifiesRenderSeparatelyFromVideoStudio(){
        assertEquals("com.rezox.render",RenderConnectionCard.PACKAGE);
        assertEquals("com.rezoxnemesis.videostudio",RenderConnectionCard.VIDEOSTUDIO_PACKAGE);
        assertEquals("render.",RenderConnectionCard.ACTION_PREFIX);
        assertTrue(RenderConnectionCard.validPublicId(ID));
        assertFalse(RenderConnectionCard.validPublicId("../secret"));
        assertFalse(RenderConnectionCard.validPublicId(null));
    }
    @Test public void shareableCardNeverClaimsCloudPairingOrExposesOriginalOwnerKey(){
        String card=RenderConnectionCard.shareText(ID,true,true);
        assertTrue(card.contains("RENDER STUDIO"));
        assertTrue(card.contains("render.engine.status"));
        assertTrue(card.contains("VideoStudio MCP v3"));
        assertTrue(card.contains(ID));
        assertTrue(card.contains("queue_video_edit"));
        assertFalse(card.contains("app-mcp-v3/"));
        assertFalse(card.contains("Bearer "));
        assertFalse(card.contains("ownerKey"));
        assertTrue(card.contains("awaiting a real native command result"));
    }
    @Test public void enabledIsDifferentFromVerifiedOrDeployed(){
        assertTrue(RenderConnectionCard.localStatus(ID,true,353,0).contains("NOT READY"));
        assertTrue(RenderConnectionCard.localStatus(ID,true,354,0).contains("Waiting for first confirmed"));
        assertTrue(RenderConnectionCard.localStatus(ID,true,340,0).contains("NOT READY"));
        assertTrue(RenderConnectionCard.localStatus(ID,false,354,12345).contains("STOPPED"));
        assertTrue(RenderConnectionCard.localStatus(ID,true,354,12345).contains("NATIVE COMMAND CONFIRMED"));
    }
}
