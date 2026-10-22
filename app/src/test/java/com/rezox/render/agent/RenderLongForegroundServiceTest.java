package com.rezox.render.agent;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class RenderLongForegroundServiceTest {
    @Test public void rejectsArbitraryJobPathsAndNames(){
        assertFalse(RenderLongForegroundService.valid("../private"));
        assertFalse(RenderLongForegroundService.valid("/storage/emulated/0"));
        assertFalse(RenderLongForegroundService.valid("not-a-job"));
        assertTrue(RenderLongForegroundService.valid("a".repeat(32)));
    }
    @Test public void durableResumePreferenceAndExplicitPauseAreTruthful()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        SharedPreferences prefs=app.getSharedPreferences(
            RenderLongForegroundService.PREFS,Context.MODE_PRIVATE);
        prefs.edit().clear().commit();
        String job="d".repeat(32);
        try{
            prefs.edit().putString(RenderLongForegroundService.JOB,job)
                .putString(RenderLongForegroundService.STATE,"WAITING_THERMAL")
                .putBoolean(RenderLongForegroundService.WANTED,true).commit();
            JSONObject before=RenderLongForegroundService.status(app);
            assertEquals(job,before.getString("job_id"));
            assertTrue(before.getBoolean("restart_requested"));
            assertFalse(before.getBoolean("quality_reduced"));
            assertFalse(before.getBoolean("android_media_processing_quota_is_unlimited"));
            assertFalse(before.getBoolean("native_engine_independent_of_activity_verified"));
            JSONObject paused=RenderLongForegroundService.requestPause(app);
            assertTrue(paused.getBoolean("pause_requested"));
            assertFalse(RenderLongForegroundService.status(app).getBoolean("restart_requested"));
            assertEquals("PAUSING_AFTER_FRAME",RenderLongForegroundService.status(app).getString("foreground_state"));
        }finally{prefs.edit().clear().commit();}
    }
    @Test public void authenticatedCommandCannotStartUnknownJob()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        try{RenderLongForegroundService.request(app,"../../../");fail();}
        catch(IllegalArgumentException expected){}
        try{RenderLongForegroundService.request(app,"f".repeat(32));fail();}
        catch(IllegalArgumentException expected){}
    }
    @Test public void bridgeExposesTypedSafeActionsWithNoArbitraryScript()throws Exception{
        for(String op:new String[]{"render.job.start","render.job.pause","render.job.status",
                "render.job.export","render.storage.status","project.checkpoint_export"}){
            ProductionBridge.validate(new JSONObject().put("operation",op)
                .put("target_id","01dfff8e-368e-4b4a-aedf-e1bec09e5490")
                .put("payload",new JSONObject()));
        }
        try{
            ProductionBridge.validate(new JSONObject().put("operation","python.eval")
                .put("payload",new JSONObject()));
            fail("Unsafe generic Python action must stay excluded");
        }catch(IllegalArgumentException expected){}
    }
}
