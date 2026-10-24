package com.rezox.render.agent;

import android.content.Context;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;

/** Durable receipt/result journal: a lost network acknowledgment never reruns a command. */
public final class AgentJournal extends SQLiteOpenHelper {
    public AgentJournal(Context c){super(c,"render_agent_jobs.db",null,2);}
    @Override public void onCreate(SQLiteDatabase db){
        db.execSQL("CREATE TABLE jobs(id TEXT PRIMARY KEY,request_key TEXT UNIQUE,digest TEXT NOT NULL,action TEXT,state TEXT,result TEXT,command TEXT,acked INTEGER DEFAULT 0,updated INTEGER)");
    }
    @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion){
        if(oldVersion==1 && newVersion==2)db.execSQL("ALTER TABLE jobs ADD COLUMN command TEXT");
        else throw new IllegalStateException("Agent journal migration required; do not discard jobs");
    }
    /** Commit acceptance before an in-memory Binder dispatch can be lost. */
    public synchronized boolean enqueue(String id,String digest,JSONObject command)throws Exception{
        if(snapshot(id,digest)!=null)return false;
        try(Cursor count=getReadableDatabase().rawQuery("SELECT COUNT(*) FROM jobs WHERE state='queued'",null)){
            if(count.moveToFirst()&&count.getInt(0)>=12)throw new IllegalStateException("RENDER_NATIVE_QUEUE_FULL_OR_STOPPING");
        }
        ContentValues v=new ContentValues();v.put("id",id);v.put("digest",digest);
        v.put("request_key",command.getString("device_id")+":"+command.getString("request_id"));
        v.put("action",command.getString("action"));v.put("state","queued");
        v.put("command",command.toString());v.put("updated",System.currentTimeMillis());
        getWritableDatabase().insertOrThrow("jobs",null,v);return true;
    }
    public synchronized List<JSONObject> queued()throws Exception{
        List<JSONObject> out=new ArrayList<>();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT id,command FROM jobs WHERE state='queued' ORDER BY updated LIMIT 12",null)){
            while(c.moveToNext())if(!c.isNull(1))out.add(new JSONObject(c.getString(1)).put("journal_id",c.getString(0)));
        }return out;
    }
    public synchronized boolean claim(String id,String digest)throws Exception{
        snapshot(id,digest);ContentValues v=new ContentValues();v.put("state","running_on_device");
        v.put("updated",System.currentTimeMillis());
        return getWritableDatabase().update("jobs",v,"id=? AND state='queued' AND digest=?",new String[]{id,digest})==1;
    }
    public synchronized JSONObject inspect(String id)throws Exception{
        if(id==null||!id.matches("[A-Za-z0-9_-]{8,128}"))throw new IllegalArgumentException("INVALID_COMMAND_ID");
        try(Cursor c=getReadableDatabase().rawQuery("SELECT state,result,updated FROM jobs WHERE id=?",new String[]{id})){
            if(!c.moveToFirst())return new JSONObject().put("command_id",id).put("state","not_found").put("safe_to_replay",false);
            JSONObject result=new JSONObject().put("command_id",id).put("state",c.getString(0))
                .put("updated_ms",c.getLong(2)).put("safe_to_replay",false);
            if(!c.isNull(1))result.put("result",new JSONObject(c.getString(1)));
            return result;
        }
    }
    public synchronized boolean cancelQueued(String id)throws Exception{
        ContentValues v=new ContentValues();v.put("state","cancelled");v.put("acked",0);
        v.put("updated",System.currentTimeMillis());
        v.put("result",new JSONObject().put("ok",false).put("error","CANCELLED_BEFORE_NATIVE_START").toString());
        return getWritableDatabase().update("jobs",v,"id=? AND state='queued'",new String[]{id})==1;
    }
    public synchronized boolean begin(String id,String fingerprint,JSONObject command)throws Exception{
        SQLiteDatabase db=getWritableDatabase();db.beginTransaction();
        try{
            try(Cursor cursor=db.rawQuery("SELECT digest FROM jobs WHERE id=?",new String[]{id})){
                if(cursor.moveToFirst()){
                    if(!fingerprint.equals(cursor.getString(0)))throw new IllegalArgumentException("JOB_DIGEST_CONFLICT");
                    db.execSQL("UPDATE jobs SET acked=0 WHERE id=? AND state<>'running_on_device'",new Object[]{id});
                    db.setTransactionSuccessful();return false;
                }
            }
            ContentValues v=new ContentValues();v.put("id",id);v.put("digest",fingerprint);
            v.put("request_key",command.getString("device_id")+":"+command.getString("request_id"));
            v.put("action",command.getString("action"));v.put("state","running_on_device");
            v.put("updated",System.currentTimeMillis());db.insertOrThrow("jobs",null,v);
            db.setTransactionSuccessful();return true;
        }finally{db.endTransaction();}
    }
    public synchronized void finish(String id,String state,JSONObject result)throws Exception{
        if(!("succeeded".equals(state)||"failed".equals(state)||"cancelled".equals(state)||"recovery_required".equals(state)))
            throw new IllegalArgumentException("INVALID_TERMINAL_STATE");
        ContentValues v=new ContentValues();v.put("state",state);v.put("result",result.toString());
        v.put("acked",0);v.put("updated",System.currentTimeMillis());
        getWritableDatabase().update("jobs",v,"id=? AND state='running_on_device'",new String[]{id});
    }
    public synchronized void recover()throws Exception{
        try(Cursor c=getReadableDatabase().rawQuery("SELECT id,result FROM jobs WHERE state='running_on_device'",null)){
            while(c.moveToNext()){
                JSONObject result=c.isNull(1)?new JSONObject():new JSONObject(c.getString(1));
                result.put("ok",false).put("error","PROCESS_INTERRUPTED_NATIVE_OUTCOME_UNKNOWN")
                    .put("safe_to_replay",false).put("state","recovery_required");
                finish(c.getString(0),"recovery_required",result);
            }
        }
    }
    public synchronized void attachNative(String id,String nativeId)throws Exception{
        ContentValues v=new ContentValues();v.put("result",new JSONObject().put("native_command_id",nativeId)
            .put("recovery_operation","native.command.status").put("safe_to_replay",false).toString());
        getWritableDatabase().update("jobs",v,"id=? AND state='running_on_device'",new String[]{id});
    }
    public synchronized List<JSONObject> pending(String deviceId)throws Exception{
        List<JSONObject> out=new ArrayList<>();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT id,digest,state,result FROM jobs WHERE acked=0 AND state NOT IN ('queued','running_on_device') AND request_key LIKE ? ORDER BY updated LIMIT 25",new String[]{deviceId+":%"})){
            while(c.moveToNext())out.add(new JSONObject().put("job_id",c.getString(0)).put("digest",c.getString(1))
                .put("state",c.getString(2)).put("result",new JSONObject(c.getString(3))));
        }return out;
    }
    /** Durable IPC idempotency receipt, never blind replay after process death. */
    public synchronized JSONObject snapshot(String id,String digest)throws Exception{
        try(Cursor c=getReadableDatabase().rawQuery(
                "SELECT digest,state,result FROM jobs WHERE id=?",new String[]{id})){
            if(!c.moveToFirst())return null;
            if(!digest.equals(c.getString(0)))throw new IllegalArgumentException("JOB_DIGEST_CONFLICT");
            String state=c.getString(1);
            String raw=c.getString(2);
            JSONObject result=raw==null?new JSONObject().put("ok",false)
                .put("error","NATIVE_RESULT_RECOVERY_REQUIRED"):new JSONObject(raw);
            return new JSONObject().put("state",state).put("result",result);
        }
    }
    public synchronized void acknowledge(String id){
        ContentValues v=new ContentValues();v.put("acked",1);getWritableDatabase().update("jobs",v,"id=?",new String[]{id});
    }
    public synchronized String history(){
        StringBuilder b=new StringBuilder();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT action,state,updated FROM jobs ORDER BY updated DESC LIMIT 20",null)){
            while(c.moveToNext())b.append(c.getString(0)).append(" — ").append(c.getString(1)).append('\n');
        }return b.length()==0?"No commands executed on this phone yet.":b.toString();
    }
}
