package com.rezox.render.omega.agent;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import org.json.JSONArray;
import org.json.JSONObject;

/** App-private, append-safe Phase 3 plan journal. Existing AgentJournal DB is untouched.
 * Claimed/executing steps become uncertain after process death; only an actual
 * audited Blender receipt can reconcile them. Never blindly duplicate geometry.
 */
public final class StageJournal extends SQLiteOpenHelper {
    private static final String DB = "render_omega_stage_journal.db";
    private static final int VERSION = 1;
    public StageJournal(Context context) { super(context, DB, null, VERSION); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE plans (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, revision TEXT NOT NULL, digest TEXT NOT NULL, stopped INTEGER NOT NULL DEFAULT 0, updated INTEGER NOT NULL)");
        db.execSQL("CREATE TABLE steps (plan_id TEXT NOT NULL, stage_id TEXT NOT NULL, ordinal INTEGER NOT NULL, key TEXT NOT NULL UNIQUE, action TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT, updated INTEGER NOT NULL, PRIMARY KEY(plan_id,stage_id))");
        db.execSQL("CREATE INDEX steps_by_plan ON steps(plan_id,ordinal)");
    }
    @Override public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        throw new IllegalStateException("STAGE_JOURNAL_MIGRATION_REQUIRED");
    }
    private static String field(JSONObject value, String name, String pattern, String code) throws Exception {
        Object raw = value.opt(name);
        if (!(raw instanceof String) || !((String) raw).matches(pattern))
            throw new IllegalArgumentException(code);
        return (String) raw;
    }
    private static String hash(JSONObject value, String key) throws Exception {
        return field(value, key, "[a-f0-9]{64}", "INVALID_" + key.toUpperCase(java.util.Locale.ROOT));
    }
    private static void assertPlan(String planId) {
        if (planId == null || !planId.matches("[a-f0-9]{32}"))
            throw new IllegalArgumentException("INVALID_PLAN_ID");
    }
    private static void assertStage(String stageId) {
        if (stageId == null || !stageId.matches("[A-Za-z][A-Za-z0-9_-]{0,31}"))
            throw new IllegalArgumentException("INVALID_STAGE_ID");
    }
    private static ContentValues values(Object... pairs) {
        ContentValues v = new ContentValues();
        for (int i = 0; i < pairs.length; i += 2) {
            String key = (String) pairs[i];
            Object raw = pairs[i + 1];
            if (raw instanceof String) v.put(key, (String)raw);
            else if (raw instanceof Integer) v.put(key, (Integer)raw);
            else if (raw instanceof Long) v.put(key, (Long)raw);
            else throw new IllegalArgumentException("INVALID_COLUMN_TYPE");
        }
        return v;
    }
    /** Accept only an already validated Phase 3 plan; recheck scope and uniqueness.
     * An identical replay is a no-op. A changed plan with the same ID is rejected.
     */
    public synchronized boolean accept(JSONObject plan) throws Exception {
        String id = field(plan, "plan_id", "[a-f0-9]{32}", "INVALID_PLAN_ID");
        String project = hash(plan, "project_id");
        String revision = hash(plan, "source_revision");
        String digest = hash(plan, "plan_digest");
        JSONArray stages = plan.getJSONArray("stages");
        if (stages.length() < 3 || stages.length() > 24)
            throw new IllegalArgumentException("INVALID_STAGE_COUNT");
        // Verify the entire list before any insert. This is not a substitute
        // for Phase 3 Python plan validation or P10 operation schema validation.
        java.util.HashSet<String> ids = new java.util.HashSet<>();
        java.util.HashSet<String> keys = new java.util.HashSet<>();
        for (int i = 0; i < stages.length(); i++) {
            JSONObject s = stages.getJSONObject(i);
            String sid = field(s, "id", "[A-Za-z][A-Za-z0-9_-]{0,31}", "INVALID_STAGE_ID");
            String key = hash(s, "idempotency_key");
            String op = field(s, "operation", "(omega\\.[a-z_]+\\.[a-z_]+|blender\\.[a-z_]+\\.[a-z_]+)", "INVALID_OPERATION");
            if (!ids.add(sid) || !keys.add(key) || op.length() > 96)
                throw new IllegalArgumentException("DUPLICATE_STAGE_ID");
            if (!revision.equals(hash(s, "expected_scene_revision")))
                throw new IllegalArgumentException("CHECKPOINT_CONFLICT");
        }
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor c = db.rawQuery("SELECT project_id,revision,digest FROM plans WHERE id=?", new String[]{id})) {
                if (c.moveToFirst()) {
                    if (!project.equals(c.getString(0)) || !revision.equals(c.getString(1)) || !digest.equals(c.getString(2)))
                        throw new IllegalArgumentException("PLAN_DIGEST_CONFLICT");
                    db.setTransactionSuccessful();
                    return false;
                }
            }
            long now = System.currentTimeMillis();
            db.insertOrThrow("plans", null, values("id", id, "project_id", project,
                    "revision", revision, "digest", digest, "updated", now));
            for (int i = 0; i < stages.length(); i++) {
                JSONObject s = stages.getJSONObject(i);
                db.insertOrThrow("steps", null, values("plan_id", id,
                        "stage_id", s.getString("id"), "ordinal", i,
                        "key", s.getString("idempotency_key"), "action", s.getString("operation"),
                        "state", "accepted", "updated", now));
            }
            db.setTransactionSuccessful();
            return true;
        } finally { db.endTransaction(); }
    }
    /** Claim only if previous stages succeeded and Stop was not requested. */
    public synchronized boolean claim(String planId, String stageId, String key) {
        assertPlan(planId); assertStage(stageId);
        if (key == null || !key.matches("[a-f0-9]{64}")) throw new IllegalArgumentException("INVALID_STAGE_KEY");
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            int ordinal;
            try (Cursor c = db.rawQuery("SELECT ordinal FROM steps WHERE plan_id=? AND stage_id=? AND key=? AND state='accepted'", new String[]{planId, stageId, key})) {
                if (!c.moveToFirst()) { db.setTransactionSuccessful(); return false; }
                ordinal = c.getInt(0);
            }
            try (Cursor c = db.rawQuery("SELECT stopped FROM plans WHERE id=?", new String[]{planId})) {
                if (!c.moveToFirst() || c.getInt(0) != 0) { db.setTransactionSuccessful(); return false; }
            }
            try (Cursor c = db.rawQuery("SELECT COUNT(*) FROM steps WHERE plan_id=? AND ordinal<? AND state<>'succeeded'", new String[]{planId, Integer.toString(ordinal)})) {
                if (!c.moveToFirst() || c.getInt(0) != 0) { db.setTransactionSuccessful(); return false; }
            }
            int changed = db.update("steps", values("state", "claimed", "updated", System.currentTimeMillis()),
                    "plan_id=? AND stage_id=? AND key=? AND state='accepted'", new String[]{planId, stageId, key});
            db.setTransactionSuccessful();
            return changed == 1;
        } finally { db.endTransaction(); }
    }
    /** Call exactly when the native spool has ACTUALLY accepted this step. */
    public synchronized boolean executing(String planId, String stageId, String key) {
        assertPlan(planId); assertStage(stageId);
        if (key == null || !key.matches("[a-f0-9]{64}")) throw new IllegalArgumentException("INVALID_STAGE_KEY");
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try {
            try (Cursor c = db.rawQuery("SELECT stopped FROM plans WHERE id=?", new String[]{planId})) {
                if (!c.moveToFirst() || c.getInt(0) != 0) { db.setTransactionSuccessful(); return false; }
            }
            int changed = db.update("steps", values("state", "executing", "updated", System.currentTimeMillis()),
                    "plan_id=? AND stage_id=? AND key=? AND state='claimed'", new String[]{planId, stageId, key});
            db.setTransactionSuccessful();
            return changed == 1;
        } finally { db.endTransaction(); }
    }
    /** Persist native evidence before marking success; no mock/queued receipt. */
    public synchronized boolean complete(String planId, String stageId, String key, JSONObject receipt) throws Exception {
        assertPlan(planId); assertStage(stageId);
        if (receipt == null || !receipt.optBoolean("native_execution_verified", false) ||
            !key.equals(receipt.optString("idempotency_key", "")) ||
            !receipt.optBoolean("postcondition_verified", false))
            throw new IllegalArgumentException("NATIVE_RECEIPT_UNCONFIRMED");
        String from = receipt.optBoolean("reconciled_after_restart", false) ? "recovery_required" : "executing";
        try (Cursor c = getReadableDatabase().rawQuery(
                "SELECT p.project_id,p.revision FROM plans p JOIN steps s ON s.plan_id=p.id WHERE p.id=? AND s.stage_id=? AND s.key=?",
                new String[]{planId, stageId, key})) {
            if (!c.moveToFirst() || !c.getString(0).equals(receipt.optString("project_id", "")) ||
                    !c.getString(1).equals(receipt.optString("source_revision", "")))
                throw new IllegalArgumentException("RECEIPT_SCOPE_CONFLICT");
        }
        if ("recovery_required".equals(from) && (!receipt.optBoolean("native_object_present", false) ||
                !receipt.optBoolean("saved_scene_receipt_match", false)))
            throw new IllegalArgumentException("RECONCILIATION_REQUIRES_NATIVE_EVIDENCE");
        ContentValues v = values("state", "succeeded", "receipt", receipt.toString(),
                "updated", System.currentTimeMillis());
        return getWritableDatabase().update("steps", v, "plan_id=? AND stage_id=? AND key=? AND state=?",
                new String[]{planId, stageId, key, from}) == 1;
    }
    public synchronized void stopNewCommands(String planId) {
        assertPlan(planId);
        getWritableDatabase().update("plans", values("stopped", 1, "updated", System.currentTimeMillis()),
                "id=?", new String[]{planId});
    }
    public synchronized void resumeNewCommands(String planId) {
        assertPlan(planId);
        getWritableDatabase().update("plans", values("stopped", 0, "updated", System.currentTimeMillis()),
                "id=?", new String[]{planId});
        // Existing uncertain steps remain unreplayable until reconciliation.
    }
    /** Any in-flight stage is INDETERMINATE after process death. */
    public synchronized int recoverInterrupted() {
        return getWritableDatabase().update("steps", values("state", "recovery_required", "updated", System.currentTimeMillis()),
                "state IN ('claimed','executing')", null);
    }
    /** Read-only status. Never expose raw user prompt or private asset paths. */
    public synchronized JSONObject status(String planId, String projectId) throws Exception {
        assertPlan(planId);
        if (projectId == null || !projectId.matches("[a-f0-9]{64}"))
            throw new IllegalArgumentException("INVALID_PROJECT_ID");
        SQLiteDatabase db = getReadableDatabase();
        JSONObject out = new JSONObject();
        try (Cursor c = db.rawQuery("SELECT revision,digest,stopped FROM plans WHERE id=? AND project_id=?", new String[]{planId, projectId})) {
            if (!c.moveToFirst()) throw new IllegalArgumentException("PLAN_NOT_FOUND_IN_PROJECT");
            out.put("plan_id", planId).put("project_id", projectId).put("source_revision", c.getString(0))
                .put("plan_digest", c.getString(1)).put("stop_new_commands", c.getInt(2) == 1);
        }
        JSONArray stages = new JSONArray();
        try (Cursor c = db.rawQuery("SELECT stage_id,state,key FROM steps WHERE plan_id=? ORDER BY ordinal", new String[]{planId})) {
            while (c.moveToNext()) stages.put(new JSONObject().put("stage_id", c.getString(0))
                    .put("state", c.getString(1)).put("idempotency_key", c.getString(2)));
        }
        return out.put("stages", stages).put("journal_kind", "app_private_sqlite")
                .put("native_effect_after_interruption", "unknown_until_reconciled");
    }
}
