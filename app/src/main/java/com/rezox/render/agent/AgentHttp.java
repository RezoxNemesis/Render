package com.rezox.render.agent;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** HTTPS only; no redirect forwarding, bounded payloads and finite timeouts. */
public final class AgentHttp {
    private AgentHttp(){}
    public static final class RelayException extends java.io.IOException {
        public final int status;
        public final long retryAfterMillis;
        RelayException(int status){this(status,null);}
        RelayException(int status,String retryAfter){super("RELAY_HTTP_"+status);this.status=status;
            retryAfterMillis=TransportRetry.retryAfterMillis(retryAfter);}
    }
    /** Public relay health check: never claims phone pairing or native command success. */
    public static JSONObject checkHealth(String origin)throws Exception {
        String base=AgentPolicy.relayUrl(origin);
        HttpURLConnection connection=(HttpURLConnection)new URL(base+"/health").openConnection();
        try {
            connection.setRequestMethod("GET");
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(7000);
            connection.setReadTimeout(7000);
            if(connection.getResponseCode()!=200)throw new RelayException(connection.getResponseCode());
            try(InputStream in=connection.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] bytes=new byte[4096];int n;
                while((n=in.read(bytes))!=-1) {
                    if(out.size()+n>16384)throw new java.io.IOException("RELAY_HEALTH_TOO_LARGE");
                    out.write(bytes,0,n);
                }
                JSONObject data=new JSONObject(out.toString("UTF-8"));
                if(!data.optBoolean("ok") || !"chatgpt-render-relay".equals(data.optString("service")))
                    throw new java.io.IOException("UNRECOGNIZED_RELAY_SERVICE");
                return data;
            }
        } finally { connection.disconnect(); }
    }
    public static JSONObject post(String base,String path,String token,JSONObject body)throws Exception{
        base=AgentPolicy.relayUrl(base);
        if(!path.matches("/v1/device/(enroll|link|poll|result|revoke)"))throw new IllegalArgumentException("INVALID_ROUTE");
        if(token!=null && !token.matches("[A-Za-z0-9_-]{32,256}"))throw new IllegalArgumentException("INVALID_DEVICE_TOKEN");
        HttpURLConnection c=(HttpURLConnection)new URL(base+path).openConnection();
        try{
            c.setConnectTimeout(15000);c.setReadTimeout(20000);c.setInstanceFollowRedirects(false);
            c.setRequestMethod("POST");c.setDoOutput(true);
            c.setRequestProperty("Content-Type","application/json");
            if(token!=null)c.setRequestProperty("Authorization","Bearer "+token);
            byte[] data=body.toString().getBytes(StandardCharsets.UTF_8);
            if(data.length>524288)throw new IllegalArgumentException("REQUEST_TOO_LARGE");
            c.setFixedLengthStreamingMode(data.length);
            try(java.io.OutputStream out=c.getOutputStream()){out.write(data);}
            int status=c.getResponseCode();
            if(status!=200)throw new RelayException(status,c.getHeaderField("Retry-After"));
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int n;
                while((n=in.read(buffer))!=-1){if(out.size()+n>524288)throw new java.io.IOException("RESPONSE_TOO_LARGE");out.write(buffer,0,n);}
                return new JSONObject(out.toString("UTF-8"));
            }
        }finally{c.disconnect();}
    }
}
