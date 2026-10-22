package com.rezox.render.agent;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.Comparator;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Owner-initiated mobile render. Uses the SAME verified ProductionBatch and
 * MediaCodec path as MCP jobs, not a second, unthrottled bpy frame loop.
 * State lives in the job manifest, so process death never erases completed PNGs.
 */
public final class RenderManualJobs {
    private static final ExecutorService WORK=Executors.newSingleThreadExecutor();
    private static final AtomicBoolean ACTIVE=new AtomicBoolean(false);
    private static final ScheduledExecutorService HEARTBEAT=Executors.newSingleThreadScheduledExecutor();
    private static volatile ScheduledFuture<?> pulse;
    private static final AtomicBoolean STOP=new AtomicBoolean(false);
    private static final String PREFS="render_manual_render";
    private static volatile String runningJob="";
    private RenderManualJobs(){}

    private static SharedPreferences preferences(Context context){
        return context.getApplicationContext().getSharedPreferences(PREFS,Context.MODE_PRIVATE);
    }
    private static void publish(Context c,String job,String state,String detail,int done,int total){
        preferences(c).edit().putString("job_id",job).putString("state",state)
            .putString("detail",detail).putInt("completed",done).putInt("total",total)
            .putLong("updated",System.currentTimeMillis()).apply();
        if(ACTIVE.get())AgentWorkPresence.stage(c,
            "Frame "+done+"/"+Math.max(total,1)+" • "+detail,
            total>0?Math.min(100,(int)(done*100L/total)):-1);
    }
    static JSONObject readManifest(Context context,String job)throws Exception{
        File path=ProductionFiles.file(context,job,"manifest.json");
        if(!path.isFile()||path.length()>16*1024*1024)
            throw new IllegalArgumentException("RENDER_MANIFEST_UNAVAILABLE");
        return new JSONObject(new String(Files.readAllBytes(path.toPath()),StandardCharsets.UTF_8));
    }
    static boolean stillImage(JSONObject manifest)throws Exception{
        String kind=manifest.getJSONObject("spec").optString("output_kind","ANIMATION");
        return "STILL".equals(kind);
    }
    public static boolean active(){return ACTIVE.get();}
    public static String currentJob(){return runningJob;}
    public static void pause(){
        STOP.set(true); // Wait for the current native frame to finish safely.
    }
    public static JSONObject status(Context c){
        SharedPreferences p=preferences(c);
        JSONObject data=new JSONObject();
        try{
            return data.put("job_id",p.getString("job_id",""))
                .put("state",ACTIVE.get()?"running":p.getString("state","idle"))
                .put("detail",p.getString("detail",""))
                .put("completed",p.getInt("completed",0))
                .put("total",p.getInt("total",0))
                .put("updated",p.getLong("updated",0L))
                .put("pausing",STOP.get()&&ACTIVE.get());
        }catch(Exception error){return data;}
    }
    public static boolean start(Context context,String jobId){
        if(jobId==null||!jobId.matches("[a-f0-9]{32}"))return false;
        if(!ACTIVE.compareAndSet(false,true))return false;
        Context app=context.getApplicationContext();
        try{
            ProductionBatch.jobStatus(app,jobId); // scope and manifest validation.
            if(AgentExecutionLock.BUSY.get()){
                ACTIVE.set(false);return false;
            }
            STOP.set(false);runningJob=jobId;
            AgentWorkPresence.begin(app,stillImage(readManifest(app,jobId)) ? "render.manual_image" : "render.manual_animation","owner-local");
            // Individual raytraced frames can last minutes. Keep the genuine
            // observed Android status fresh without faking frame completions.
            pulse=HEARTBEAT.scheduleAtFixedRate(()->{
                if(!ACTIVE.get())return;
                SharedPreferences p=preferences(app);
                int done=p.getInt("completed",0),total=p.getInt("total",0);
                AgentWorkPresence.stage(app,
                    "Render frame "+done+"/"+Math.max(total,1)+" • "+
                        p.getString("detail","Native Blender working"),
                    total>0?Math.min(100,(int)(done*100L/total)):-1);
            },5,8,TimeUnit.SECONDS);
            WORK.execute(()->runJob(app,jobId));
            return true;
        }catch(Exception error){
            runningJob="";ACTIVE.set(false);
            return false;
        }
    }
    private static void runJob(Context app,String jobId){
        String ending="paused";
        // Cooling can require hours. The foreground service owns lifetime;
        // finished PNG frames are never retried or deleted during cooldown.
        try{
            while(!STOP.get()){
                JSONObject before=ProductionBatch.jobStatus(app,jobId);
                int done=before.getInt("completed_frames"),total=before.getInt("total_frames");
                String state=before.getString("state");
                boolean still=stillImage(readManifest(app,jobId));
                publish(app,jobId,state,"encoded".equals(state)?"MP4 ready":"Rendering",done,total);
                if("encoded".equals(state)){
                    ending="succeeded";break;
                }
                if("frames_complete".equals(state)||before.getInt("next_frame")>before.getInt("end_frame")){
                    if(still){
                        publish(app,jobId,"frames_complete","Verified full-resolution PNG ready",done,total);
                        ending="succeeded";
                        break;
                    }
                    publish(app,jobId,"encoding","Creating H.264 MP4",done,total);
                    JSONObject result=ProductionVideoEncoder.encode(app,jobId,STOP);
                    if(result.optString("sha256").length()!=64)
                        throw new IllegalStateException("ENCODER_RECEIPT_MISSING");
                    publish(app,jobId,"encoded","MP4 ready for export",done,total);
                    ending="succeeded";break;
                }
                JSONObject request=new JSONObject().put("job_id",jobId)
                    .put("max_frames",1).put("max_wall_ms",540000)
                    .put("cooldown_max_ms",60000);
                JSONObject after=ProductionBatch.advance(app,request,STOP);
                done=after.getInt("completed_frames");
                String reason=after.optString("reason","FRAME_COMPLETED");
                publish(app,jobId,after.optString("state","ready"),reason,done,total);
                if(reason.equals("PAUSED_ALREADY_RENDERING")){
                    // Another native command owns the frame executor; no fake retry.
                    ending="paused";break;
                }
                if(reason.equals("PAUSED_THERMAL_PRESSURE") ||
                   reason.equals("PAUSED_MEMORY_PRESSURE") ||
                   reason.equals("PAUSED_STORAGE_PRESSURE")){
                    // Wait safely without a wake-lock or any GPU work. Recheck
                    // actual Android telemetry and storage admission later;
                    // never change the requested engine, samples or geometry.
                    publish(app,jobId,"cooling",reason,done,total);
                    for(int elapsed=0;elapsed<60&&!STOP.get();elapsed+=5)
                        Thread.sleep(5000L);
                    continue;
                }
                if(reason.startsWith("PAUSED_")){ending="paused";break;}
            }
            if(STOP.get()){
                ending="cancelled";
                JSONObject snap=status(app);
                publish(app,jobId,"paused","Paused at frame boundary",
                    snap.optInt("completed"),snap.optInt("total"));
            }
        }catch(Exception error){
            // Do not erase the last valid PNG or overwrite the frozen .blend.
            String message=error.getMessage();
            String code=message!=null&&message.matches("[A-Z_]{3,96}")?
                message:error.getClass().getSimpleName();
            JSONObject last=status(app);
            publish(app,jobId,"paused_error","Retryable: "+code,
                    last.optInt("completed"),last.optInt("total"));
            ending="failed";
        }finally{
            ScheduledFuture<?> ticker=pulse;
            if(ticker!=null)ticker.cancel(false);
            pulse=null;
            AgentWorkPresence.finish(app,ending);
            ACTIVE.set(false);
            runningJob="";
            STOP.set(false);
        }
    }
    /** File-menu bpy operator writes a bounded local request, not a web call. */
    public static void acceptMenuRequest(Context context){
        if(ACTIVE.get())return;
        try{
            File request=new File(ProductionFiles.root(context),"manual_render_request.json");
            if(!request.isFile()||request.length()<20||request.length()>2048)return;
            JSONObject body=new JSONObject(new String(Files.readAllBytes(request.toPath()),StandardCharsets.UTF_8));
            String job=body.optString("job_id");
            long age=System.currentTimeMillis()/1000-body.optLong("requested_at",0);
            if(age<0||age>3600||!job.matches("[a-f0-9]{32}")){
                request.delete();return;
            }
            // Start owner-visible foreground work, not a hidden in-memory
            // thread that stops when the Blender activity is destroyed.
            JSONObject result=RenderLongForegroundService.request(context,job);
            if(result.optBoolean("foreground_launch_requested"))request.delete();
        }catch(Exception ignored){
            // Keep request for inspection; no blind or unbounded retry storm.
        }
    }
    /** Discover a render that survived an Activity restart; never auto-run it. */
    public static String newestRecoverable(Context context){
        try{
            File[] folders=ProductionFiles.root(context).listFiles(
                f->f.isDirectory()&&f.getName().matches("[a-f0-9]{32}")&&
                   new File(f,"manifest.json").isFile());
            if(folders==null)return "";
            Arrays.sort(folders,Comparator.comparingLong(
                (File f)->new File(f,"manifest.json").lastModified()).reversed());
            for(int i=0;i<Math.min(50,folders.length);i++){
                try{
                    JSONObject s=ProductionBatch.jobStatus(context,folders[i].getName());
                    if(!"encoded".equals(s.getString("state"))){
                        return folders[i].getName();
                    }
                }catch(Exception ignored){}
            }
        }catch(Exception ignored){}
        return "";
    }
    /** Export is explicit; does not silently publish the user's render to Drive. */
    public static JSONObject export(Context context,String job)throws Exception{
        JSONObject state=ProductionBatch.jobStatus(context,job);
        JSONObject data=readManifest(context,job);
        if(stillImage(data)){
            if(!"frames_complete".equals(state.getString("state")))
                throw new IllegalStateException("STILL_FRAME_NOT_FINISHED");
            JSONObject spec=data.getJSONObject("spec");
            String frameKey=Integer.toString(spec.getInt("start"));
            JSONObject png=data.getJSONObject("frames").getJSONObject(frameKey);
            return ProductionFiles.export(context,new JSONObject()
                .put("category",job).put("filename",png.getString("filename"))
                .put("expected_sha256",png.getString("sha256")));
        }
        if(!"encoded".equals(state.getString("state")))
            throw new IllegalStateException("VIDEO_NOT_YET_ENCODED");
        JSONObject video=data.getJSONObject("video");
        return ProductionFiles.export(context,new JSONObject()
            .put("category",job).put("filename",video.getString("filename"))
            .put("expected_sha256",video.getString("sha256")));
    }
}
