package com.rezox.render.agent;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class AgentEnvelopeTest {
    private static final String DEVICE="01234567890123456789012345678901";
    private JSONObject envelope(String device)throws Exception{
        String payload=new JSONObject().put("device_id",device).put("request_id","command-1").put("api_version",1)
            .put("action","engine.status").put("args",new JSONObject()).toString();
        return new JSONObject().put("job_id","abcdef0123456789abcdef0123456789").put("payload",payload).put("digest",AgentPolicy.sha256(payload));
    }
    @Test public void validatesAuthenticEnvelope()throws Exception{assertEquals("engine.status",new AgentEnvelope(envelope(DEVICE),DEVICE).command.getString("action"));}
    @Test public void rejectsWrongPhone()throws Exception{
        try{new AgentEnvelope(envelope("different"),DEVICE);fail();}catch(IllegalArgumentException expected){assertEquals("WRONG_DEVICE",expected.getMessage());}
    }
    @Test public void detectsTampering()throws Exception{
        JSONObject e=envelope(DEVICE);e.put("payload",e.getString("payload").replace("engine.status","shell.execute"));
        try{new AgentEnvelope(e,DEVICE);fail();}catch(IllegalArgumentException expected){assertEquals("PAYLOAD_DIGEST_MISMATCH",expected.getMessage());}
    }
    @Test public void rejectsUnexpectedEnvelopeField()throws Exception{
        JSONObject e=envelope(DEVICE);e.put("run_shell",true);
        try{new AgentEnvelope(e,DEVICE);fail();}catch(IllegalArgumentException expected){assertEquals("INVALID_ENVELOPE_FIELDS",expected.getMessage());}
    }
}
