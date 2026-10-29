package com.rezox.render.agent;

import org.json.JSONObject;

/**
 * The sole ChatGPT command transport for Render Studio.
 * Public HTTPS origin is not a credential. Native Blender and files remain on Android.
 */
public final class RenderDirectMcp {
    public static final String ORIGIN="https://render-studio-direct-mcp.prakasharuntandon634.workers.dev";
    public static final String MCP_ENDPOINT=ORIGIN+"/mcp";
    private static final String LEGACY_TRANSPORT="videostudio-mcp-v3";

    private RenderDirectMcp(){}

    /** Keystore credentials from a previous VideoStudio transport must never be replayed. */
    public static boolean isLegacyPairing(JSONObject saved) {
        return saved!=null && LEGACY_TRANSPORT.equals(saved.optString("transport"));
    }

    public static boolean isDirectPairing(JSONObject saved) {
        if(saved==null || isLegacyPairing(saved))return false;
        String transport=saved.optString("transport","");
        if(!transport.isEmpty() && !"render-direct-mcp".equals(transport))return false;
        String origin=saved.optString("relay","");
        try { if(!ORIGIN.equals(AgentPolicy.relayUrl(origin)))return false; }
        catch(IllegalArgumentException error){return false;}
        return saved.optString("device_id","").matches("[a-f0-9]{32}")
            && saved.optString("device_token","").matches("[A-Za-z0-9_-]{32,256}");
    }

    public static JSONObject requireDirectPairing(JSONObject saved) {
        if(!isDirectPairing(saved))
            throw new IllegalStateException("DIRECT_RENDER_MCP_PAIRING_REQUIRED");
        return saved;
    }

    public static JSONObject credentials(String deviceId,String deviceToken) {
        JSONObject c=new JSONObject();
        c.put("transport","render-direct-mcp");
        c.put("relay",ORIGIN);
        c.put("device_id",deviceId);
        c.put("device_token",deviceToken);
        return requireDirectPairing(c);
    }
}
