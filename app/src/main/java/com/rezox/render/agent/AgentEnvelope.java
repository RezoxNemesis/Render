package com.rezox.render.agent;

import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/** Exact transport bytes are hashed before JSON parsing; saved pointers are never commands. */
public final class AgentEnvelope {
    public final String id,digest;
    public final JSONObject command;
    public AgentEnvelope(JSONObject envelope,String deviceId)throws Exception{
        requireKeys(envelope,new String[]{"job_id","digest","payload"});
        id=string(envelope,"job_id");digest=string(envelope,"digest");
        String payload=string(envelope,"payload");
        if(!id.matches("[a-f0-9]{32}")||!digest.matches("[a-f0-9]{64}")||payload.getBytes(StandardCharsets.UTF_8).length>98304)
            throw new IllegalArgumentException("INVALID_ENVELOPE");
        if(!MessageDigest.isEqual(digest.getBytes(StandardCharsets.US_ASCII),AgentPolicy.sha256(payload).getBytes(StandardCharsets.US_ASCII)))
            throw new IllegalArgumentException("PAYLOAD_DIGEST_MISMATCH");
        command=new JSONObject(payload);
        requireKeys(command,new String[]{"device_id","request_id","api_version","action","args"});
        if(!deviceId.equals(string(command,"device_id")))throw new IllegalArgumentException("WRONG_DEVICE");
        if(!(command.get("api_version") instanceof Integer))throw new IllegalArgumentException("INVALID_API_VERSION");
        JSONObject args=command.getJSONObject("args");Set<String> fields=new HashSet<>();args.keys().forEachRemaining(fields::add);
        AgentPolicy.validate(string(command,"request_id"),command.getInt("api_version"),string(command,"action"),fields);
    }
    private static String string(JSONObject object,String key)throws Exception{
        Object value=object.get(key);if(!(value instanceof String))throw new IllegalArgumentException("INVALID_STRING_ARGUMENT");
        return (String)value;
    }
    private static void requireKeys(JSONObject object,String[] keys){
        Set<String> actual=new HashSet<>();object.keys().forEachRemaining(actual::add);
        if(!actual.equals(new HashSet<>(Arrays.asList(keys))))throw new IllegalArgumentException("INVALID_ENVELOPE_FIELDS");
    }
}
