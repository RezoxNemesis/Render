package com.rezox.render.agent;

import org.junit.Test;
import static org.junit.Assert.*;

public class VideoStudioMcpTransportTest {
    private static final String CODE="a".repeat(40);
    @Test public void singleUsePairingCodeFormat(){
        assertEquals(CODE,VideoStudioMcpTransport.pairingCode(CODE));
    }
    @Test public void neverRequestOriginalVideoStudioPrivateOwnerUrl(){
        for(String bad:new String[]{null,"","123","g".repeat(40),CODE+"x",
            "https://example.com/app-mcp-v3/"+"x".repeat(43),
            "../"+CODE}) {
            try{VideoStudioMcpTransport.pairingCode(bad);fail("Accepted unsafe credential");}
            catch(IllegalArgumentException expected){}
        }
    }
    @Test public void independentAndSharedMcpCredentialsRemainDistinct()throws Exception{
        org.json.JSONObject device=new org.json.JSONObject().put("transport","videostudio-mcp-v3");
        assertTrue(VideoStudioMcpTransport.isSelected(device));
        device.put("transport","independent-relay");
        assertFalse(VideoStudioMcpTransport.isSelected(device));
    }
}
