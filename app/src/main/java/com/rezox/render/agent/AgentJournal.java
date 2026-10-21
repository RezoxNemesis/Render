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
    public AgentJournal(Context c){super(c,"render_agent_jobs.db",null,1);}
    @Override public void onCreate(SQLiteDatabase db){
        db.execSQL("CREATE TABLE jobs(id TEXT PRIMARY KEY,request_key TEXT UNIQUE,digest TEXT NOT NULL,action TEXT,state TEXT,result TEXT,acked INTEGER DEFAULT 0,updated INTEGER)");
    }
    @Override public void onUpgrade(SQLiteDatabase db,int oldVersion,int newVersion){
        throw new IllegalStateException("Agent journal migration required; do not discard jobs");
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
        ContentValues v=new ContentValues();v.put("state","recovery_required");v.put("acked",0);
        v.put("result",new JSONObject().put("error","PROCESS_INTERRUPTED_NATIVE_OUTCOME_UNKNOWN")
            .put("safe_to_replay",false).toString());v.put("updated",System.currentTimeMillis());
        getWritableDatabase().update("jobs",v,"state='running_on_device'",null);
    }
    public synchronized List<JSONObject> pending(String deviceId)throws Exception{
        List<JSONObject> out=new ArrayList<>();
        try(Cursor c=getReadableDatabase().rawQuery("SELECT id,digest,state,result FROM jobs WHERE acked=0 AND state<>'running_on_device' AND request_key LIKE ? ORDER BY updated LIMIT 25",new String[]{deviceId+":%"})){
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
