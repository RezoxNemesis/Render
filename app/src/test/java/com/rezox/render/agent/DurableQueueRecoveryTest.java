package com.rezox.render.agent;

import android.content.Context;
import android.database.sqlite.SQLiteDatabase;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

/** Host SQLite/persistence contracts; no native Blender work is performed. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class DurableQueueRecoveryTest {
    private JSONObject command(String id)throws Exception{return new JSONObject().put("device_id","fixture")
        .put("request_id",id).put("action","engine.status").put("api_version",1).put("args",new JSONObject());}

    @Test public void queuedCommandsSurviveReopenAndClaimedMutationsRequireExactRecovery()throws Exception{
        Context c=RuntimeEnvironment.getApplication();c.deleteDatabase("render_agent_jobs.db");
        try(AgentJournal journal=new AgentJournal(c)){
            assertTrue(journal.enqueue("command-first","digest-a",command("command-first")));
            assertFalse(journal.enqueue("command-first","digest-a",command("command-first")));
            assertTrue(journal.enqueue("command-second","digest-b",command("command-second")));
        }
        try(AgentJournal journal=new AgentJournal(c)){
            assertEquals(2,journal.queued().size());
            assertTrue(journal.claim("command-first","digest-a"));
            assertFalse(journal.claim("command-first","digest-a"));
            journal.attachNative("command-first","a".repeat(32));journal.recover();
            JSONObject recovered=journal.inspect("command-first");
            assertEquals("recovery_required",recovered.getString("state"));
            assertEquals("a".repeat(32),recovered.getJSONObject("result").getString("native_command_id"));
            assertFalse(recovered.getJSONObject("result").getBoolean("safe_to_replay"));
            assertEquals(1,journal.queued().size());
            assertTrue(journal.cancelQueued("command-second"));
            assertFalse(journal.claim("command-second","digest-b"));
            assertEquals("cancelled",journal.inspect("command-second").getString("state"));
        }
    }
    @Test public void migrationPreservesOldTerminalReceipts()throws Exception{
        Context c=RuntimeEnvironment.getApplication();c.deleteDatabase("render_agent_jobs.db");
        try(SQLiteDatabase db=c.openOrCreateDatabase("render_agent_jobs.db",0,null)){
            db.execSQL("CREATE TABLE jobs(id TEXT PRIMARY KEY,request_key TEXT UNIQUE,digest TEXT NOT NULL,action TEXT,state TEXT,result TEXT,acked INTEGER DEFAULT 0,updated INTEGER)");
            db.execSQL("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",new Object[]{"old-command","fixture:old-command","old-digest","engine.status","succeeded","{\"kept\":true}",1,1});
            db.setVersion(1);
        }
        try(AgentJournal journal=new AgentJournal(c)){
            assertTrue(journal.inspect("old-command").getJSONObject("result").getBoolean("kept"));
            assertTrue(journal.enqueue("new-command","new-digest",command("new-command")));
        }
    }
    @Test public void renderIntentCancellationKeepsOtherQueuedWork()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        c.getSharedPreferences("render_job_queue_v1",0).edit().clear().commit();
        String first="a".repeat(32),second="b".repeat(32);
        RenderJobQueue.state(c,first,"queued");RenderJobQueue.state(c,second,"queued");
        RenderJobQueue.state(c,first,"cancelled");
        assertEquals(second,RenderJobQueue.next(c));assertTrue(RenderJobQueue.cancelled(c,first));
        RenderJobQueue.state(c,second,"completed");assertEquals("",RenderJobQueue.next(c));
        assertEquals(2,RenderJobQueue.status(c).getJSONArray("entries").length());
    }
    @Test public void schedulingOverridesPreserveOmittedSettingsAndCannotReduceSafety()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        c.getSharedPreferences("render_scheduling_v1",0).edit().clear().commit();
        RenderScheduling.execute(c,new JSONObject().put("memory_reserve_mib",512).put("minimum_frame_gap_ms",1500),true);
        JSONObject changed=RenderScheduling.execute(c,new JSONObject().put("memory_reserve_mib",1024),true);
        assertEquals(1500,changed.getInt("minimum_frame_gap_ms"));assertFalse(changed.getBoolean("quality_settings_changed"));
        JSONObject reading=new JSONObject().put("thermal_status",0).put("available_memory_bytes",512L*1024*1024);
        assertEquals("PAUSED_MEMORY_PRESSURE",RenderScheduling.evaluate(c,reading,false).reason);
        reading.put("available_memory_bytes",-1);
        assertTrue(RenderScheduling.evaluate(c,reading,false).renderAllowed);
        reading.put("thermal_status",3);
        assertEquals("PAUSED_THERMAL_PRESSURE",RenderScheduling.evaluate(c,reading,false).reason);
    }
}
