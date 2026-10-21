package com.rezox.render.agent;

import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.UUID;

/**
 * Reuse the EXISTING private VideoStudio MCP v3 Cloudflare Worker.
 * Render is a different Android native executor with a different Keystore
 * owner key, device ID, queue, project store, and STOP state.
 * No Railway/Render.com server and no cloud modeling/rendering.
 */
public final class VideoStudioMcpTransport {
    private static final String HOST="wispy-queen-f9b5.prakasharuntandon634.workers.dev";
    public static final String ORIGIN="https://"+HOST;
    private static final String FAMILY="videostudio-mcp-v3";
    private VideoStudioMcpTransport(){}

    /** The existing VideoStudio MCP provides a single-use pairing code. */
    public static String pairingCode(String supplied) {
        if(supplied==null || !supplied.trim().matches("[a-f0-9]{40}"))
            throw new IllegalArgumentException("Enter the one-time pairing code from VideoStudio MCP, not the private owner link.");
        return supplied.trim();
    }
    private static JSONObject request(String method,String route,String token,JSONObject body)throws Exception {
        if(!route.matches("/api/v3/render/(health|link|poll|result|unlink)"))
            throw new IllegalArgumentException("INVALID_VIDEOSTUDIO_ROUTE");
        if(token!=null && !token.matches("[A-Za-z0-9_-]{43,128}"))
            throw new IllegalArgumentException("INVALID_RENDER_OWNER_CREDENTIAL");
        HttpURLConnection c=(HttpURLConnection)new URL(ORIGIN+route).openConnection();
        try {
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(12000);
            c.setReadTimeout(22000);
            c.setRequestMethod(method);
            c.setRequestProperty("Accept","application/json");
            if(token!=null)c.setRequestProperty("Authorization","Bearer "+token);
            if("POST".equals(method)) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type","application/json");
                byte[] data=body.toString().getBytes(StandardCharsets.UTF_8);
                if(data.length>196608)throw new IllegalArgumentException("COMMAND_TOO_LARGE");
                c.setFixedLengthStreamingMode(data.length);
                try(OutputStream out=c.getOutputStream()){out.write(data);}
            }
            int status=c.getResponseCode();
            if(status!=200)throw new AgentHttp.RelayException(status);
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int read;
                while((read=in.read(buffer))!=-1){
                    if(out.size()+read>196608)throw new java.io.IOException("RESPONSE_TOO_LARGE");
                    out.write(buffer,0,read);
                }
                return new JSONObject(out.toString("UTF-8"));
            }
        }finally {c.disconnect();}
    }
    public static JSONObject checkSharedWorker()throws Exception {
        JSONObject result=request("GET","/api/v3/render/health",null,null);
        if(!result.optBoolean("ok") || !"videostudio-render-mcp-v3".equals(result.optString("service")))
            throw new java.io.IOException("RENDER_BRIDGE_WORKER_NOT_READY");
        return result;
    }
    public static JSONObject pair(String shortCode)throws Exception {
        String code=pairingCode(shortCode);
        byte[] random=new byte[32];
        new SecureRandom().nextBytes(random);
        String renderKey=Base64.getUrlEncoder().withoutPadding().encodeToString(random);
        String renderId=UUID.randomUUID().toString();
        JSONObject metadata=new JSONObject().put("appVersion","0.12.0")
            .put("protocolFamily","render-native").put("nativeAgent","render-native-v1")
            .put("protocolVersion",3).put("appGeneration",1)
            .put("galleryAccess",false);
        JSONObject request=new JSONObject().put("pairingCode",code)
            .put("renderDeviceId",renderId).put("renderOwnerKey",renderKey)
            .put("meta",metadata);
        JSONObject response=VideoStudioMcpTransport.request(
            "POST","/api/v3/render/link",null,request);
        if(!response.optBoolean("linked") || !renderId.equals(response.optString("deviceId")))
            throw new java.io.IOException("RENDER_PAIRING_NOT_CONFIRMED");
        return new JSONObject().put("transport",FAMILY)
            .put("relay",ORIGIN).put("device_id",renderId).put("device_token",renderKey);
    }
    public static boolean isSelected(JSONObject credentials){
        return FAMILY.equals(credentials.optString("transport"));
    }
    public static JSONObject poll(JSONObject credentials,JSONObject payload)throws Exception {
        JSONObject body=new JSONObject().put("deviceId",credentials.getString("device_id"))
            .put("enabled",payload.getBoolean("enabled"))
            .put("activeJobId",payload.opt("active_job_id"))
            .put("capabilities",payload.optJSONArray("capabilities")==null?
                new JSONArray():payload.getJSONArray("capabilities"));
        return request("POST","/api/v3/render/poll",credentials.getString("device_token"),body);
    }
    public static JSONObject complete(JSONObject credentials,JSONObject receipt)throws Exception {
        JSONObject body=new JSONObject(receipt.toString());
        body.put("deviceId",credentials.getString("device_id"));
        return request("POST","/api/v3/render/result",credentials.getString("device_token"),body);
    }
    public static JSONObject unlink(JSONObject credentials)throws Exception {
        return request("POST","/api/v3/render/unlink",credentials.getString("device_token"),
            new JSONObject().put("deviceId",credentials.getString("device_id")));
    }
}
