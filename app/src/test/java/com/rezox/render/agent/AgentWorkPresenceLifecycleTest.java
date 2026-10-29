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
public class AgentWorkPresenceLifecycleTest {
    @Test public void successfulPauseReceiptKeepsReasonAndVisibleNotice()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        AgentWorkPresence.begin(c,"render.production.execute","VideoStudio MCP v3 Binder");
        AgentWorkPresence.stage(c,"Rendering frame 104 - 3/5 verified",60);
        AgentWorkPresence.finish(c,"succeeded",new JSONObject().put("paused",true)
            .put("reason","PAUSED_THERMAL_PRESSURE"));
        AgentWorkPresence.Snapshot s=AgentWorkPresence.snapshot(c);
        assertTrue(s.isPaused());assertTrue(s.hasPersistentNotice());assertFalse(s.isWorking());
        assertEquals("PAUSED_THERMAL_PRESSURE",s.stage);assertEquals(60,s.progress);
        assertTrue(s.description().contains("Waiting for Android to cool"));
        JSONObject overlay=StudioLiveHandOverlay.snapshot(c);
        assertTrue(overlay.getBoolean("paused"));
        assertEquals("native_pause_or_recovery",overlay.getString("hand_tracking_mode"));
        assertFalse(overlay.getBoolean("fabricated_ui_taps"));
    }
    @Test public void journalFailureCannotBeDescribedAsSafePause()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        AgentWorkPresence.begin(c,"render.batch","Binder");
        AgentWorkPresence.finish(c,"recovery_required",new JSONObject().put("paused",true));
        AgentWorkPresence.Snapshot s=AgentWorkPresence.snapshot(c);
        assertTrue(s.needsRecovery());assertFalse(s.isPaused());assertTrue(s.hasPersistentNotice());
    }
    @Test public void nextSuccessfulNativeCommandClearsPauseNotice()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        AgentWorkPresence.begin(c,"render.batch","Binder");
        AgentWorkPresence.finish(c,"succeeded",new JSONObject().put("paused",true));
        AgentWorkPresence.begin(c,"scene.inspect","Binder");
        AgentWorkPresence.finish(c,"succeeded",new JSONObject());
        AgentWorkPresence.Snapshot s=AgentWorkPresence.snapshot(c);
        assertFalse(s.isPaused());assertFalse(s.hasPersistentNotice());
        assertEquals("succeeded",s.state);
    }
}
