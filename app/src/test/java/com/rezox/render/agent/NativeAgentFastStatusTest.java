package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class NativeAgentFastStatusTest {
    @Test public void fastStatusIsAuthenticatedAndOutOfBandWithoutBpy()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String target=new AgentSecrets(app).renderPublicId();
        JSONObject args=new JSONObject()
            .put("operation","studio.agent.status")
            .put("target_id",target)
            .put("payload",new JSONObject());
        assertTrue(ProductionBridge.outOfBand(args));
        JSONObject result=ProductionBridge.execute(app,args,new AtomicBoolean(false));
        assertEquals("render.studio.agent.fastlane.v1",
                     result.getString("contract"));
        assertTrue(result.has("native_editor_heartbeat_ready"));
        assertFalse(result.getBoolean("operator_command_or_script_executed"));
        assertFalse(result.getBoolean("background_render_safely_paused_after_force_stop_guaranteed"));
        assertFalse(result.has("auth_token"));
        assertFalse(result.has("media_path"));
        assertTrue(result.getLong("native_status_elapsed_ms")>=0);
        JSONObject extra=new JSONObject().put("include_plans",true)
            .put("include_thermal",true);
        args.put("payload",extra);
        result=ProductionBridge.execute(app,args,new AtomicBoolean(false));
        assertTrue(result.has("plans"));
        assertTrue(result.has("device_thermal"));
        assertTrue(result.getJSONObject("plans").has("jobs"));
        assertFalse(result.toString().contains("sk-proj"));
        args.put("target_id","00000000-0000-0000-0000-000000000000");
        try{
            ProductionBridge.execute(app,args,new AtomicBoolean(false));
            fail("Accepted wrong owner Render public ID");
        }catch(IllegalArgumentException expected){
            assertEquals("RENDER_TARGET_ID_REQUIRED_OR_MISMATCH",expected.getMessage());
        }
    }
    @Test public void refusesUnexpectedFieldsAndWrongFlags()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        try{NativeAgentFastStatus.read(app,new JSONObject().put("path","/sdcard"));fail();}
        catch(IllegalArgumentException expected){
            assertEquals("UNKNOWN_PRODUCTION_ARGUMENT",expected.getMessage());
        }
        try{NativeAgentFastStatus.read(app,new JSONObject().put("include_plans","true"));fail();}
        catch(IllegalArgumentException expected){
            assertEquals("STUDIO_AGENT_FLAG_INVALID",expected.getMessage());
        }
    }
}
