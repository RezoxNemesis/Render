package com.rezox.render.omega.agent;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import static org.junit.Assert.*;

/** Robolectric tests use real app-private SQLite, not an in-memory fake journal. */
@RunWith(RobolectricTestRunner.class)
public final class StageJournalTest {
    private Context context;
    private static final String PLAN="c".repeat(32), PROJECT="a".repeat(64), REV="b".repeat(64);
    private static final String[] KEYS={"1".repeat(64), "2".repeat(64), "3".repeat(64)};
    @Before public void setUp() {
        context=org.robolectric.RuntimeEnvironment.getApplication();
        context.deleteDatabase("render_omega_stage_journal.db");
    }
    private static JSONObject plan() throws Exception {
        JSONObject result=new JSONObject().put("plan_id",PLAN).put("project_id",PROJECT)
                .put("source_revision",REV).put("plan_digest","f".repeat(64));
        JSONArray steps=new JSONArray();
        for (int i=0;i<3;i++)
            steps.put(new JSONObject().put("id",new String[]{"plan","create","audit"}[i])
                    .put("operation",new String[]{"omega.agent.plan_validate","blender.object.add_cube","blender.scene.summary"}[i])
                    .put("expected_scene_revision",REV).put("idempotency_key",KEYS[i]));
        return result.put("stages",steps);
    }
    private static JSONObject verified(int stage, boolean reconciliation) throws Exception {
        return new JSONObject().put("native_execution_verified",true)
                .put("postcondition_verified",true).put("idempotency_key",KEYS[stage])
                .put("reconciled_after_restart",reconciliation)
                .put("project_id",PROJECT).put("source_revision",REV)
                .put("native_object_present",true).put("saved_scene_receipt_match",true);
    }
    @Test public void survivesRestartAndNeverDuplicates() throws Exception {
        StageJournal first=new StageJournal(context);
        assertTrue(first.accept(plan()));
        assertFalse(first.accept(plan()));
        assertTrue(first.claim(PLAN,"plan",KEYS[0]));
        assertTrue(first.executing(PLAN,"plan",KEYS[0]));
        assertTrue(first.complete(PLAN,"plan",KEYS[0],verified(0,false)));
        assertTrue(first.claim(PLAN,"create",KEYS[1]));
        assertTrue(first.executing(PLAN,"create",KEYS[1]));
        first.close(); // Force process restart boundary.
        StageJournal restart=new StageJournal(context);
        assertEquals(1,restart.recoverInterrupted());
        assertFalse(restart.claim(PLAN,"create",KEYS[1]));
        assertFalse(restart.claim(PLAN,"audit",KEYS[2]));
        assertEquals("recovery_required",restart.status(PLAN,PROJECT)
                .getJSONArray("stages").getJSONObject(1).getString("state"));
        assertTrue(restart.complete(PLAN,"create",KEYS[1],verified(1,true)));
        assertFalse(restart.complete(PLAN,"create",KEYS[1],verified(1,true)));
        assertTrue(restart.claim(PLAN,"audit",KEYS[2]));
        restart.close();
    }
    @Test public void stopResumeDoesNotOverrideRecovery() throws Exception {
        StageJournal db=new StageJournal(context);
        assertTrue(db.accept(plan()));
        db.stopNewCommands(PLAN);
        assertFalse(db.claim(PLAN,"plan",KEYS[0]));
        db.resumeNewCommands(PLAN);
        assertTrue(db.claim(PLAN,"plan",KEYS[0]));
        assertEquals(1,db.recoverInterrupted());
        db.resumeNewCommands(PLAN);
        assertFalse(db.claim(PLAN,"plan",KEYS[0]));
        db.close();
    }
    @Test public void rejectsFakeReceiptsWrongProjectAndDigestConflict() throws Exception {
        StageJournal db=new StageJournal(context);
        db.accept(plan());
        assertTrue(db.claim(PLAN,"plan",KEYS[0]));
        assertTrue(db.executing(PLAN,"plan",KEYS[0]));
        try { db.complete(PLAN,"plan",KEYS[0],new JSONObject().put("native_execution_verified",true));
            fail("receipt without postcondition must fail");
        } catch (IllegalArgumentException expected) { assertEquals("NATIVE_RECEIPT_UNCONFIRMED",expected.getMessage()); }
        try { db.status(PLAN,"0".repeat(64)); fail("wrong project must fail"); }
        catch (IllegalArgumentException expected) { assertEquals("PLAN_NOT_FOUND_IN_PROJECT",expected.getMessage()); }
        JSONObject changed=plan().put("plan_digest","e".repeat(64));
        try { db.accept(changed); fail("plan replay conflict must fail"); }
        catch (IllegalArgumentException expected) { assertEquals("PLAN_DIGEST_CONFLICT",expected.getMessage()); }
        db.close();
    }
}
