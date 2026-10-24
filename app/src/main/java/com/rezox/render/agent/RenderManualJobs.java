package com.rezox.render.agent;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import org.json.JSONObject;
import org.json.JSONArray;
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
    private static void timing(Context c,JSONObject progress){
        JSONObject value=progress.optJSONObject("timing");
        long elapsed=value==null?0:value.optLong("render_active_ms",0);
        long average=value==null?0:value.optLong("estimated_frame_ms",0);
        long remaining=Math.max(0,progress.optInt("total_frames")-progress.optInt("completed_frames"));
        preferences(c).edit().putLong("render_active_ms",elapsed)
            .putLong("estimated_remaining_render_ms",average>0?average*remaining:-1).apply();
    }
    public static String duration(long millis){
        if(millis<0)return "unavailable";
        long minutes=millis/60000;
        return minutes>=60?(minutes/60)+"h "+(minutes%60)+"m":minutes+"m "+(millis/1000%60)+"s";
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
            String cached=p.getString("state","idle");
            boolean active=ACTIVE.get();
            boolean interrupted=!active&&(Arrays.asList("running","rendering","encoding","preparing","starting","cooling").contains(cached)
                ||("ready".equals(cached)&&"Rendering".equals(p.getString("detail",""))));
            return data.put("job_id",p.getString("job_id",""))
                .put("state",active?"running":interrupted?"interrupted":cached)
                .put("detail",interrupted?"Previous render worker interrupted; inspect the exact native command result before resuming":p.getString("detail",""))
                .put("cached_worker_state",cached).put("manual_worker_active",active)
                .put("recovery_required",interrupted)
                .put("completed",p.getInt("completed",0))
                .put("total",p.getInt("total",0))
                .put("updated",p.getLong("updated",0L))
                .put("render_active_ms",p.getLong("render_active_ms",0))
                .put("estimated_remaining_render_ms",p.getLong("estimated_remaining_render_ms",-1))
                .put("estimate_scope","remaining frames only; excludes encoding, cooling and exports")
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
                timing(app,before);
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
                    publish(app,jobId,"encoding","Encoding verified H.264 parts",done,total);
                    JSONObject result;
                    try{
                        result=ProductionVideoEncoder.encode(app,jobId,STOP);
                    }catch(IllegalStateException interrupted){
                        String cause=interrupted.getMessage();
                        if(cause!=null&&(cause.equals("PAUSED_THERMAL_PRESSURE")||
                            cause.equals("PAUSED_MEMORY_PRESSURE")||
                            cause.equals("PAUSED_STORAGE_PRESSURE"))){
                            // Previously encoded, checksum-verified MP4 parts
                            // remain committed. Wait for the REAL Android
                            // sensor and resume only the current partial part.
                            publish(app,jobId,"cooling",cause,done,total);
                            for(int t=0;t<60&&!STOP.get();t+=5)Thread.sleep(5000L);
                            continue;
                        }
                        throw interrupted;
                    }
                    if(result.optString("sha256").length()!=64)
                        throw new IllegalStateException("ENCODER_RECEIPT_MISSING");
                    publish(app,jobId,"encoded",result.optBoolean("segmented")?
                        "All MP4 segments ready":"MP4 ready for export",done,total);
                    ending="succeeded";break;
                }
                // Do not acquire a GPU/render wake lock merely to discover
                // that Android is already at SEVERE thermal pressure or the
                // next frame cannot fit on disk. Real Blender remains paused.
                JSONObject observed=ProductionThermalTelemetry.sample(app);
                ProductionThermalPolicy.Decision admission=ProductionThermalPolicy.evaluate(
                    observed.optInt("thermal_status",-1),
                    observed.optBoolean("low_memory",false),
                    observed.optLong("available_memory_bytes",0L),STOP.get());
                String admissionReason=admission.renderAllowed?"READY":admission.reason;
                if(admission.renderAllowed&&
                    !RenderStorageBudget.frameSpaceAvailable(app,jobId))
                    admissionReason="PAUSED_STORAGE_PRESSURE";
                if(!"READY".equals(admissionReason)){
                    publish(app,jobId,"cooling",admissionReason,done,total);
                    for(int elapsed=0;elapsed<120&&!STOP.get();elapsed+=5)
                        Thread.sleep(5000L);
                    continue;
                }
                JSONObject request=new JSONObject().put("job_id",jobId)
                    .put("max_frames",1).put("max_wall_ms",540000)
                    .put("cooldown_max_ms",60000);
                JSONObject after=ProductionBatch.advance(app,request,STOP);
                timing(app,after);
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
            if(STOP.get()&&!(error instanceof BlenderSpool.RecoveryRequired)){
                JSONObject last=status(app);
                publish(app,jobId,"paused","Paused before the next native frame",
                        last.optInt("completed"),last.optInt("total"));
                ending="cancelled";
            }else{
            // Do not erase the last valid PNG or overwrite the frozen .blend.
            String message=error.getMessage();
            String code=message!=null&&message.matches("[A-Z_]{3,96}")?
                message:error.getClass().getSimpleName();
            JSONObject last=status(app);
            publish(app,jobId,"paused_error","Retryable: "+code,
                    last.optInt("completed"),last.optInt("total"));
            ending="failed";
            }
        }finally{
            ScheduledFuture<?> ticker=pulse;
            if(ticker!=null)ticker.cancel(false);
            pulse=null;
            AgentWorkPresence.finish(app,ending);
            runningJob="";
            STOP.set(false);
            ACTIVE.set(false);
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
        if(video.optBoolean("segmented")){
            JSONArray parts=video.getJSONArray("segments");
            JSONArray exported=new JSONArray();
            for(int i=0;i<parts.length();i++){
                if(STOP.get())throw new IllegalStateException("EXPORT_PAUSED_AT_SEGMENT_BOUNDARY");
                exported.put(exportSegment(context,job,i));
            }
            JSONObject index=ProductionFiles.export(context,new JSONObject()
                .put("category",job).put("filename",video.getString("filename"))
                .put("expected_sha256",video.getString("sha256")));
            return new JSONObject().put("segmented",true).put("job_id",job)
                .put("segments",exported).put("index",index)
                .put("all_parts_downloads_verified",true)
                .put("no_quality_reduction",true);
        }
        return ProductionFiles.export(context,new JSONObject()
            .put("category",job).put("filename",video.getString("filename"))
            .put("expected_sha256",video.getString("sha256")));
    }

    /** Each 768MiB part can be exported separately; an MCP call never
     * needs to stream an entire 10GB movie before returning a result. */
    public static JSONObject exportSegment(Context context,String job,int index)throws Exception{
        if(index<0||index>100000||!ProductionSegmentedEncoder.partName(job,index)
                .matches("Production_[a-f0-9]{32}_part_[0-9]{5}\\.mp4"))
            throw new IllegalArgumentException("INVALID_SEGMENT_INDEX");
        JSONObject manifest=readManifest(context,job);
        JSONObject receipts=manifest.optJSONObject("encoded_segments");
        if(receipts==null||!receipts.has(Integer.toString(index)))
            throw new IllegalStateException("VIDEO_PART_NOT_YET_ENCODED");
        java.util.List<ProductionSegmentPlan.Span> plan=ProductionSegmentPlan.plan(manifest.getJSONObject("spec"));
        if(index>=plan.size())throw new IllegalArgumentException("SEGMENT_OUTSIDE_RENDER_PLAN");
        JSONObject part=ProductionSegmentedEncoder.readVerified(context,job,
            receipts.getJSONObject(Integer.toString(index)),plan.get(index));
        if(part==null)throw new IllegalStateException("VIDEO_PART_CHECKSUM_MISMATCH");
        JSONObject exported=ProductionFiles.export(context,new JSONObject()
            .put("category",job).put("filename",part.getString("filename"))
            .put("expected_sha256",part.getString("sha256")));
        return exported.put("segment_index",index).put("frames",part.getInt("frames"));
    }
}
