package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class RenderManualJobsStatusTest {
    @Test public void deadWorkerCannotKeepDisplayingRenderingOrLoseSavedFrameCounts()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        c.getSharedPreferences("render_manual_render",Context.MODE_PRIVATE).edit().putString("state","rendering")
            .putString("detail","Rendering").putInt("completed",3).putInt("total",9).putLong("updated",1234).commit();
        JSONObject status=RenderManualJobs.status(c);
        assertEquals("interrupted",status.getString("state"));assertTrue(status.getBoolean("recovery_required"));
        assertFalse(status.getBoolean("manual_worker_active"));assertTrue(status.getString("detail").contains("exact native command"));
        assertEquals(3,status.getInt("completed"));assertEquals(9,status.getInt("total"));assertEquals(1234,status.getLong("updated"));
        assertEquals("rendering",c.getSharedPreferences("render_manual_render",Context.MODE_PRIVATE).getString("state",""));
    }
    @Test public void completedAndExplicitlyPausedJobsRetainTheirState()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        for(String state:new String[]{"encoded","paused","paused_error","idle"}){
            c.getSharedPreferences("render_manual_render",Context.MODE_PRIVATE).edit().putString("state",state).commit();
            JSONObject status=RenderManualJobs.status(c);assertEquals(state,status.getString("state"));assertFalse(status.getBoolean("recovery_required"));
        }
    }
}
