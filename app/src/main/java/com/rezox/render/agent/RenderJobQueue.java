package com.rezox.render.agent;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONObject;

/** Durable ordered render intentions. Native manifests remain the frame authority. */
public final class RenderJobQueue {
    private RenderJobQueue(){}
    private static SharedPreferences prefs(Context c){return c.getApplicationContext()
        .getSharedPreferences("render_job_queue_v1",Context.MODE_PRIVATE);}
    private static JSONArray read(Context c)throws Exception{
        String value=prefs(c).getString("entries","[]");
        if(value.length()>131072)throw new IllegalStateException("RENDER_QUEUE_CORRUPT");
        return new JSONArray(value);
    }
    public static synchronized void state(Context c,String id,String state)throws Exception{
        if(!RenderLongForegroundService.valid(id))throw new IllegalArgumentException("INVALID_RENDER_JOB_ID");
        JSONArray entries=read(c);JSONObject found=null;
        for(int i=0;i<entries.length();i++)if(id.equals(entries.getJSONObject(i).optString("job_id")))found=entries.getJSONObject(i);
        if(found==null){
            if(entries.length()>=64){
                JSONArray retained=new JSONArray();
                for(int i=0;i<entries.length();i++){
                    JSONObject row=entries.getJSONObject(i);
                    if(!"completed".equals(row.optString("state")))retained.put(row);
                }entries=retained;
            }
            if(entries.length()>=64)throw new IllegalStateException("RENDER_QUEUE_FULL");
            found=new JSONObject().put("job_id",id).put("queued_at_ms",System.currentTimeMillis());entries.put(found);
        }
        found.put("state",state).put("updated_ms",System.currentTimeMillis());
        if(!prefs(c).edit().putString("entries",entries.toString()).commit())
            throw new IllegalStateException("RENDER_QUEUE_NOT_WRITABLE");
    }
    public static synchronized String next(Context c)throws Exception{
        JSONArray entries=read(c);
        for(int i=0;i<entries.length();i++){
            JSONObject row=entries.getJSONObject(i);
            if("queued".equals(row.optString("state")))return row.getString("job_id");
        }return "";
    }
    public static synchronized boolean cancelled(Context c,String job)throws Exception{
        JSONArray entries=read(c);
        for(int i=0;i<entries.length();i++){
            JSONObject row=entries.getJSONObject(i);
            if(job.equals(row.optString("job_id")))return "cancelled".equals(row.optString("state"));
        }return false;
    }
    public static synchronized JSONObject status(Context c)throws Exception{
        return new JSONObject().put("entries",read(c)).put("max_entries",64)
            .put("completed_frames_authority","immutable native render manifests")
            .put("force_stop_execution_guaranteed",false);
    }
}
