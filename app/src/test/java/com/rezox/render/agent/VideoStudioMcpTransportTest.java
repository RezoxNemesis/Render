package com.rezox.render.agent;

import org.junit.Test;
import static org.junit.Assert.*;

public class VideoStudioMcpTransportTest {
    private static final String HOST="https://wispy-queen-f9b5.prakasharuntandon634.workers.dev";
    private static final String KEY="AbCdEfGhIjKlMnOpQrStUvWxYz_123456789012345678901";
    @Test public void acceptsExistingPrivateVideoStudioMcpUrl(){
        assertEquals(KEY,VideoStudioMcpTransport.privateOwnerKey(HOST+"/app-mcp-v3/"+KEY));
    }
    @Test public void rejectsFakeHostsAndDowngrades(){
        String[] bad={null,"","http://wispy-queen-f9b5.prakasharuntandon634.workers.dev/app-mcp-v3/"+KEY,
            "https://evil.example/app-mcp-v3/"+KEY,
            HOST+".evil.example/app-mcp-v3/"+KEY,
            HOST+"/api/v3/app/register",HOST+"/mcp-v06/"+KEY,
            HOST+"/app-mcp-v3/"+KEY+"?extra=yes",
            HOST+"/app-mcp-v3/%2f"+KEY,
            HOST+"/app-mcp-v3/"+KEY+"/commands"};
        for(String value:bad) {
            try{VideoStudioMcpTransport.privateOwnerKey(value);fail("Accepted unsafe path");}
            catch(IllegalArgumentException expected){}
        }
    }
    @Test public void transportTypeIsSeparateFromOldRelay()throws Exception{
        org.json.JSONObject c=new org.json.JSONObject().put("transport","videostudio-mcp-v3");
        assertTrue(VideoStudioMcpTransport.isSelected(c));
        c.put("transport","legacy");
        assertFalse(VideoStudioMcpTransport.isSelected(c));
    }
}
