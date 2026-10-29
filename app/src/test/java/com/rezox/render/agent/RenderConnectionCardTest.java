package com.rezox.render.agent;

import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class RenderConnectionCardTest {
    private static final String ID="c1378302-1f20-4c7c-884e-50317b20bd02";
    @Test public void identifiesIndependentRenderStudioTarget(){
        assertEquals("com.rezox.render",RenderConnectionCard.PACKAGE);
        assertEquals("render.",RenderConnectionCard.ACTION_PREFIX);
        assertTrue(RenderConnectionCard.validPublicId(ID));
        assertFalse(RenderConnectionCard.validPublicId("../secret"));
    }
    @Test public void sharedInstructionsNeverContainOwnerCredentialsOrBridgeCommands(){
        String card=RenderConnectionCard.shareText(ID,true,false);
        assertTrue(card.contains("RENDER STUDIO"));
        assertTrue(card.contains(RenderDirectMcp.MCP_ENDPOINT));
        assertTrue(card.contains("render_submit"));
        assertTrue(card.contains("render_job"));
        assertTrue(card.contains("render_status"));
        assertFalse(card.contains("queue_video_edit"));
        assertFalse(card.contains("Bearer "));
        assertFalse(card.contains("ownerKey"));
        assertTrue(card.contains("agent session stopped"));
    }
    @Test public void pairingAndActualExecutionAreDifferentStates(){
        assertTrue(RenderConnectionCard.shareText(ID,false,false).contains("Not paired"));
        assertTrue(RenderConnectionCard.shareText(ID,true,false).contains("session stopped"));
        assertTrue(RenderConnectionCard.shareText(ID,true,true).contains("not yet verified"));
    }
    @Test public void rejectsLegacyAndOffTargetCredentials()throws Exception{
        JSONObject direct=RenderDirectMcp.credentials("0123456789abcdef0123456789abcdef",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdeFGH");
        assertTrue(RenderDirectMcp.isDirectPairing(direct));
        assertFalse(RenderDirectMcp.isLegacyPairing(direct));
        assertFalse(RenderDirectMcp.isDirectPairing(new JSONObject(direct.toString())
            .put("relay","https://another.example")));
        assertFalse(RenderDirectMcp.isDirectPairing(new JSONObject(direct.toString())
            .put("transport","videostudio-mcp-v3")));
        JSONObject legacy=new JSONObject().put("transport","videostudio-mcp-v3")
            .put("device_id","0123456789abcdef0123456789abcdef")
            .put("device_token","ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdeFGH")
            .put("relay","https://old.example");
        assertTrue(RenderDirectMcp.isLegacyPairing(legacy));
        try{RenderDirectMcp.requireDirectPairing(legacy);fail();}
        catch(IllegalStateException expected){
            assertEquals("DIRECT_RENDER_MCP_PAIRING_REQUIRED",expected.getMessage());
        }
    }
}
