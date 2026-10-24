package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/**
 * Authenticated read-only work-plan status while Blender's single bpy thread
 * is busy in a long frame. Owner-private app storage, no token/path disclosure.
 * Never mutates, resumes or pretends a force-stopped process is still working.
 */
public final class NativeStudioPlanStatus {
    private NativeStudioPlanStatus(){}
    private static final String ID="[a-f0-9]{32}";
    private static final int MAX_RECEIPT=100000;

    static File folder(Context context)throws Exception{
        File root=ProductionFiles.root(context),dir=new File(root,"StudioPlans");
        // A native-only status directory is not an exportable artifact
        // category. Keep it separate from owner Downloads and user files.
        if(Files.isSymbolicLink(dir.toPath())||
           !root.getCanonicalFile().equals(dir.getCanonicalFile().getParentFile()))
            throw new IOException("STUDIO_PLAN_FOLDER_OUTSIDE_SCOPE");
        if(!dir.isDirectory()&&!dir.mkdirs())
            throw new IOException("STUDIO_PLAN_FOLDER_UNAVAILABLE");
        return dir;
    }
    private static JSONObject raw(Context context,String id)throws Exception{
        if(id==null||!id.matches(ID))throw new IllegalArgumentException("STUDIO_PLAN_ID_INVALID");
        File dir=folder(context);
        File f=new File(dir,id+".json");
        if(Files.isSymbolicLink(f.toPath())||!dir.getCanonicalFile().equals(f.getCanonicalFile().getParentFile()))
            throw new IOException("STUDIO_PLAN_OUTSIDE_SCOPE");
        if(!f.isFile()||f.length()<=0||f.length()>MAX_RECEIPT)
            throw new IllegalArgumentException("STUDIO_PLAN_RECEIPT_UNAVAILABLE");
        JSONObject value=new JSONObject(new String(Files.readAllBytes(f.toPath()),StandardCharsets.UTF_8));
        if(!id.equals(value.optString("plan_id")))throw new IOException("STUDIO_PLAN_RECEIPT_ID_MISMATCH");
        JSONArray steps=value.optJSONArray("steps");
        if(steps==null||steps.length()<1||steps.length()>16||
           !value.optString("fingerprint").matches("[a-f0-9]{64}"))
            throw new IOException("STUDIO_PLAN_RECEIPT_INVALID");
        String state=value.optString("state");
        if(!("queued".equals(state)||"running".equals(state)||"paused".equals(state)||
             "needs_review".equals(state)||"cancelled".equals(state)||"completed".equals(state)))
            throw new IOException("STUDIO_PLAN_STATE_INVALID");
        int done=value.optInt("next",-1);
        if(done<0||done>steps.length())throw new IOException("STUDIO_PLAN_PROGRESS_INVALID");
        return value;
    }
    private static JSONObject publicStatus(JSONObject source)throws Exception{
        String state=source.getString("state"),id=source.getString("plan_id");
        JSONArray steps=source.getJSONArray("steps");
        int completed=source.getInt("next"),total=steps.length();
        JSONArray receipts=source.optJSONArray("receipts");
        JSONArray trail=new JSONArray();
        if(receipts!=null){
            for(int i=Math.max(0,receipts.length()-16);i<receipts.length();i++){
                JSONObject receipt=receipts.optJSONObject(i);
                if(receipt!=null)trail.put(new JSONObject()
                    .put("index",receipt.optInt("index",-1))
                    .put("operation",receipt.optString("operation",""))
                    .put("state",receipt.optString("state","")));
            }
        }
        long last=source.optLong("updated_epoch_ms",0L);
        boolean stale="running".equals(state)&&last>0L&&
            System.currentTimeMillis()-last>35000L;
        // A Blender timer blocked by an active frame can appear stale. Never
        // silently assert it is still running; status is "unconfirmed" until
        // the actual bpy executor updates its next durable receipt.
        return new JSONObject().put("plan_id",id)
            .put("name",source.optString("name","Artist Work"))
            .put("state",stale?"running_status_unconfirmed":state)
            .put("last_native_recorded_state",state)
            .put("completed_steps",completed).put("total_steps",total)
            .put("fraction",completed/(double)total)
            .put("updated_epoch_ms",last)
            .put("requires_manual_review","needs_review".equals(state))
            .put("results",trail)
            .put("source","owner-private fsynced native Blender plan record")
            .put("native_executor_live_verified",false)
            .put("background_resume_after_force_stop_guaranteed",false);
    }
    public static JSONObject status(Context context,JSONObject p)throws Exception{
        ProductionBridge.fields(p,"plan_id");
        return publicStatus(raw(context,p.getString("plan_id")));
    }
    public static JSONObject list(Context context,JSONObject p)throws Exception{
        ProductionBridge.fields(p,"");
        File dir=folder(context);
        File[] files=dir.listFiles((parent,name)->name.matches(ID+"\\.json"));
        List<JSONObject> list=new ArrayList<>();
        int invalid=0;
        if(files!=null){
            for(int i=0;i<Math.min(files.length,128);i++){
                File file=files[i];
                try{list.add(publicStatus(raw(context,file.getName().substring(0,32))));}
                catch(Exception ex){invalid++;}
            }
        }
        list.sort(Comparator.comparingLong((JSONObject j)->j.optLong("updated_epoch_ms",0L)).reversed());
        JSONArray recent=new JSONArray();
        int pending=0,needsReview=0;
        for(JSONObject value:list){
            String state=value.optString("last_native_recorded_state");
            if("queued".equals(state))pending++;
            if("needs_review".equals(state))needsReview++;
        }
        for(int i=0;i<Math.min(32,list.size());i++)recent.put(list.get(i));
        return new JSONObject().put("jobs",recent).put("pending",pending)
            .put("needs_review",needsReview).put("invalid_receipts",invalid)
            .put("readonly_available_while_renderer_busy",true)
            .put("native_scene_actions_serialized",true)
            .put("native_executor_live_verified",false)
            .put("running_after_android_force_stop_guaranteed",false);
    }
}
