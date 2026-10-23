package com.rezox.render.agent;

import android.content.Context;
import android.os.Looper;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicBoolean;

/** Bounded on-device rendering: one user job, up to 12 consecutive frames per
 * command, cooling between frames rather than flooding the MCP bridge.
 *
 * This DOES NOT lower resolution, samples, bitrate or silently move rendering
 * to the cloud. Progress is checkpointed by the existing native bpy renderer.
 */
public final class ProductionBatch {
    private static final AtomicBoolean BUSY=new AtomicBoolean(false);
    private ProductionBatch(){}

    /** Injectable device boundary for deterministic scheduling tests. Test
     * receipts never establish that Blender ran on an Android device. */
    interface Runtime {
        long now();
        JSONObject sample() throws Exception;
        void sleep(long millis) throws InterruptedException;
        boolean frameSpaceAvailable() throws Exception;
        AutoCloseable wake();
        JSONObject render(JSONObject args) throws Exception;
    }

    static JSONObject jobStatus(Context context,String jobId)throws Exception{
        File file=ProductionFiles.file(context,jobId,"manifest.json");
        if(!file.isFile() || file.length()>16*1024*1024)throw new IllegalArgumentException("RENDER_MANIFEST_UNAVAILABLE");
        JSONObject m=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        JSONObject spec=m.getJSONObject("spec");
        return new JSONObject()
            .put("job_id",jobId).put("state",m.getString("state"))
            .put("next_frame",m.getInt("next_frame"))
            .put("total_frames",spec.getInt("frame_count"))
            .put("start_frame",spec.getInt("start")).put("end_frame",spec.getInt("end"))
            .put("completed_frames",m.getJSONObject("frames").length())
            .put("fingerprint",m.getString("fingerprint"))
            .put("quality_reduced",false)
            .put("source_checkpoint_preserved",true);
    }

    /** Absolute frame bounds must be used, not the number of frames in the job. */
    static boolean framesComplete(JSONObject state)throws Exception {
        return state.getInt("next_frame")>state.getInt("end_frame");
    }

    private static JSONObject report(Context context,String jobId,String reason,
                                     int processed,long elapsed,JSONObject reading)throws Exception{
        JSONObject out=jobStatus(context,jobId);
        out.put("processed_in_batch",processed).put("wall_elapsed_ms",elapsed)
            .put("reason",reason).put("thermal",reading)
            .put("video_created",out.getString("state").equals("encoded"));
        if(reason.startsWith("PAUSED_")){
            out.put("paused",true).put("retry_after_seconds",
                reason.equals("PAUSED_THERMAL_PRESSURE")?30:15);
        }else out.put("paused",false);
        return out;
    }

    public static JSONObject advance(Context context,JSONObject p,AtomicBoolean cancelled)throws Exception{
        return advance(context,p,cancelled,new Runtime(){
            public long now(){return SystemClock.elapsedRealtime();}
            public JSONObject sample()throws Exception{return ProductionThermalTelemetry.sample(context);}
            public void sleep(long millis)throws InterruptedException{Thread.sleep(millis);}
            public boolean frameSpaceAvailable()throws Exception{
                return RenderStorageBudget.frameSpaceAvailable(context,p.getString("job_id"));
            }
            public AutoCloseable wake(){return NativeWakeGuard.acquire(context,"blender.scene.render_video");}
            public JSONObject render(JSONObject args)throws Exception{
                return new BlenderSpool(context).execute("blender.production.execute",args,cancelled);
            }
        });
    }

    static JSONObject advance(Context context,JSONObject p,AtomicBoolean cancelled,Runtime runtime)throws Exception{
        ProductionBridge.fields(p,"job_id,max_frames,max_wall_ms,cooldown_max_ms,expected_fingerprint");
        String jobId=p.getString("job_id");
        JSONObject current=jobStatus(context,jobId);
        if(p.has("expected_fingerprint") &&
            !current.getString("fingerprint").equals(p.getString("expected_fingerprint")))
            throw new IllegalArgumentException("RENDER_REVISION_CONFLICT");
        int maxFrames=(int)ProductionBridge.integer(p,"max_frames",1,12,8);
        long maxWall=ProductionBridge.integer(p,"max_wall_ms",30000,540000,360000);
        long cooldown=ProductionBridge.integer(p,"cooldown_max_ms",0,90000,60000);
        if(Looper.myLooper()==Looper.getMainLooper())
            throw new IllegalStateException("PRODUCTION_BATCH_REQUIRES_WORKER_THREAD");
        if(!BUSY.compareAndSet(false,true))
            return report(context,jobId,"PAUSED_ALREADY_RENDERING",0,0,runtime.sample());
        final long started=runtime.now();
        int produced=0;
        String reason="TIME_BUDGET_REACHED";
        try{
            while(produced<maxFrames && runtime.now()-started<maxWall){
                if(cancelled.get())return report(context,jobId,"PAUSED_USER_STOP",produced,runtime.now()-started,runtime.sample());
                current=jobStatus(context,jobId);
                if(framesComplete(current)){
                    reason="FRAMES_COMPLETE";break;
                }
                JSONObject reading=runtime.sample();
                ProductionThermalPolicy.Decision decision=ProductionThermalPolicy.evaluate(
                    reading.getInt("thermal_status"),reading.getBoolean("low_memory"),
                    reading.getLong("available_memory_bytes"),cancelled.get());
                if(!decision.renderAllowed){
                    if(!decision.reason.equals("PAUSED_THERMAL_PRESSURE")||cooldown==0){
                        return report(context,jobId,cancelled.get()?"PAUSED_USER_STOP":decision.reason,produced,runtime.now()-started,reading);
                    }
                    long pauseStarted=runtime.now();
                    // Cooldown is bounded. Never reinterpret Android severe=3 as safe
                    // just because the outer case feels cool.
                    int consecutiveCool=0;
                    AgentWorkPresence.stage(context,"PAUSED_THERMAL_PRESSURE - waiting for Android sensor",-1);
                    while(runtime.now()-pauseStarted<cooldown &&
                          runtime.now()-started<maxWall &&
                          !cancelled.get()){
                        runtime.sleep(Math.max(1,Math.min(5000,Math.min(cooldown-(runtime.now()-pauseStarted),
                            maxWall-(runtime.now()-started)))));
                        reading=runtime.sample();
                        decision=ProductionThermalPolicy.evaluate(reading.getInt("thermal_status"),
                            reading.getBoolean("low_memory"),reading.getLong("available_memory_bytes"),cancelled.get());
                        // An unavailable sensor is not a confirmed cool sample
                        // after Android has already reported severe pressure.
                        if(decision.renderAllowed&&!decision.statusUnavailable){
                            consecutiveCool++;
                            if(consecutiveCool>=2)break;
                        }else if(!decision.renderAllowed&&!decision.reason.equals("PAUSED_THERMAL_PRESSURE"))
                            return report(context,jobId,cancelled.get()?"PAUSED_USER_STOP":decision.reason,produced,runtime.now()-started,reading);
                        else consecutiveCool=0;
                    }
                    if(cancelled.get())return report(context,jobId,"PAUSED_USER_STOP",produced,runtime.now()-started,reading);
                    if(!decision.renderAllowed||consecutiveCool<2)
                        return report(context,jobId,"PAUSED_THERMAL_PRESSURE",produced,runtime.now()-started,reading);
                }
                if(runtime.now()-started >= maxWall){
                    reason="TIME_BUDGET_REACHED";break;
                }
                // Disk pressure is distinct from memory/thermal pressure.
                // Stop BEFORE launching an expensive native frame rather than
                // writing a partial PNG and losing the last known good master.
                if(!runtime.frameSpaceAvailable())
                    return report(context,jobId,"PAUSED_STORAGE_PRESSURE",produced,
                        runtime.now()-started,reading);
                if(cancelled.get())return report(context,jobId,"PAUSED_USER_STOP",produced,runtime.now()-started,reading);
                JSONObject nativeArgs=new JSONObject().put("operation","render.step")
                    .put("payload",new JSONObject().put("job_id",jobId));
                int completed=current.getInt("completed_frames"),total=current.getInt("total_frames");
                AgentWorkPresence.stage(context,"Rendering frame "+current.getInt("next_frame")+
                    " - "+completed+"/"+total+" verified",total>0?(int)(completed*100L/total):-1);
                JSONObject result;
                // Keep the CPU awake only while a native frame is outstanding.
                // Cooling, memory/storage pauses and inter-frame pacing hold no lock.
                try(AutoCloseable wake=runtime.wake()){
                    result=runtime.render(nativeArgs);
                }
                if(!jobId.equals(result.optString("job_id")))
                    throw new IllegalStateException("NATIVE_RENDER_JOB_RECEIPT_MISMATCH");
                if(result.optInt("completed_frames")<=current.getInt("completed_frames"))
                    throw new IllegalStateException("NATIVE_RENDER_DID_NOT_ADVANCE");
                produced++;
                if("frames_complete".equals(result.optString("state"))){
                    reason="FRAMES_COMPLETE";break;
                }
                if(reading.optInt("thermal_status")==2){
                    // Tiny pacing at Android MODERATE prevents avoidable ramp-up
                    // without changing any pixel-quality setting.
                    runtime.sleep(ProductionThermalPolicy.evaluate(2,false,
                        reading.getLong("available_memory_bytes"),false).cooldownMillis);
                }
            }
            if(produced==maxFrames && !reason.equals("FRAMES_COMPLETE"))
                reason="BATCH_LIMIT_REACHED";
            return report(context,jobId,reason,produced,runtime.now()-started,runtime.sample());
        }finally{
            BUSY.set(false);
        }
    }
}
