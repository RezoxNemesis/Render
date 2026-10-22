package com.rezox.render.agent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * An EXPLICIT, user-perceptible Android foreground session for long native
 * Blender frame jobs. Does not replace Blender, run on cloud, forge frames,
 * override thermal policy or promise execution after a user force-stop.
 *
 * START_STICKY may restore an OS-killed service. The current native Blender
 * editor process must actually be ready: a service never fabricates a headless
 * rendering engine after the native editor has been destroyed.
 *
 * On Android 15+ mediaProcessing has an OS-enforced 6h/24h budget. Quota
 * exhaustion or force-stop is a durable pause, NOT a 20-hour guarantee.
 */
public final class RenderLongForegroundService extends Service {
    public static final String START="com.rezox.render.LONG_RENDER_START";
    public static final String RESUME="com.rezox.render.LONG_RENDER_RESUME";
    public static final String PAUSE="com.rezox.render.LONG_RENDER_PAUSE";
    public static final String CHANNEL="render-long-media-processing";
    static final String PREFS="render_long_job_v1";
    static final String JOB="job_id";
    static final String WANTED="resume_requested";
    static final String STATE="state";
    private static final int ID=91;
    private static final String MATCH="[a-f0-9]{32}";

    private final ScheduledExecutorService monitor=Executors.newSingleThreadScheduledExecutor();
    private volatile boolean destroyed;
    private volatile boolean ownerPause;
    private boolean monitorScheduled;
    private volatile boolean startPending;
    private int startAttempts;
    private String jobId="";
    private int idlePolls;
    private long lastNotice;

    static boolean valid(String value){return value!=null&&value.matches(MATCH);}

    private static void state(Context c,String job,String status,boolean autoResume){
        c.getApplicationContext().getSharedPreferences(PREFS,MODE_PRIVATE).edit()
            .putString(JOB,job).putString(STATE,status)
            .putBoolean(WANTED,autoResume)
            .putLong("last_change_ms",System.currentTimeMillis()).commit();
    }
    /** From an owner-visible editor, or an authenticated production command. */
    public static JSONObject request(Context context,String job)throws Exception{
        if(!valid(job))throw new IllegalArgumentException("INVALID_RENDER_JOB_ID");
        ProductionBatch.jobStatus(context,job); // Strictly app-owned manifest.
        Context c=context.getApplicationContext();
        state(c,job,"LAUNCH_REQUESTED",true);
        Intent start=new Intent(c,RenderLongForegroundService.class)
            .setAction(START).putExtra(JOB,job);
        try{
            // Android 12+ may reject remote commands originating in background.
            // A user can retry from Render's visible controls/notification.
            c.startForegroundService(start);
            return new JSONObject().put("job_id",job)
                .put("foreground_launch_requested",true)
                .put("native_render_started",false)
                .put("service_owned_render",true)
                .put("quality_reduced",false)
                .put("continuous_after_force_stop_guaranteed",false);
        }catch(RuntimeException error){
            state(c,job,"AWAITING_OWNER_FOREGROUND",true);
            return new JSONObject().put("job_id",job)
                .put("foreground_launch_requested",false)
                .put("native_render_started",false)
                .put("reason","FOREGROUND_START_REQUIRES_USER_ACTION")
                .put("android_exception",error.getClass().getSimpleName())
                .put("resume_from_checkpoint_available",true)
                .put("quality_reduced",false);
        }
    }

    /** Explicit pause is recorded even if Android has already killed the UI. */
    public static JSONObject requestPause(Context context)throws Exception{
        Context c=context.getApplicationContext();
        String job=c.getSharedPreferences(PREFS,MODE_PRIVATE).getString(JOB,"");
        if(!valid(job))throw new IllegalStateException("NO_LONG_RENDER_JOB");
        state(c,job,"PAUSING_AFTER_FRAME",false);
        RenderManualJobs.pause();
        return new JSONObject().put("job_id",job).put("pause_requested",true)
            .put("will_stop_after_current_native_frame",true)
            .put("quality_reduced",false);
    }

    public static JSONObject status(Context context)throws Exception{
        Context c=context.getApplicationContext();
        android.content.SharedPreferences preferences=c.getSharedPreferences(PREFS,MODE_PRIVATE);
        String job=preferences.getString(JOB,"");
        JSONObject result=new JSONObject().put("job_id",job)
            .put("foreground_state",preferences.getString(STATE,"IDLE"))
            .put("restart_requested",preferences.getBoolean(WANTED,false))
            .put("last_change_ms",preferences.getLong("last_change_ms",0L))
            .put("android_force_stop_can_prevent_restart",true)
            .put("android_media_processing_quota_is_unlimited",false)
            .put("native_engine_independent_of_activity_verified",false)
            .put("quality_reduced",false);
        if(valid(job)){
            try{
                JSONObject nativeState=ProductionBatch.jobStatus(c,job);
                result.put("render_job",nativeState)
                    .put("storage",RenderStorageBudget.forJob(c,job));
            }catch(Exception error){
                result.put("render_status_unavailable",error.getClass().getSimpleName());
            }
        }
        result.put("native_worker",RenderManualJobs.status(c));
        return result;
    }

    public static boolean editorReady(Context c){
        File ready=new File(c.getFilesDir(),"render_bpy_jobs/ready");
        long age=System.currentTimeMillis()-ready.lastModified();
        return ready.isFile()&&age>=0&&age<15000;
    }
    @Override public void onCreate(){
        super.onCreate();
        getSystemService(NotificationManager.class).createNotificationChannel(
            new NotificationChannel(CHANNEL,"Render Studio long animation",
                NotificationManager.IMPORTANCE_LOW));
    }

    private Notification notification(String detail,int completed,int total){
        Intent open=new Intent().setClassName(this,"com.rezox.render.RenderHubActivity");
        PendingIntent content=PendingIntent.getActivity(this,91,open,
            PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        PendingIntent pause=PendingIntent.getService(this,92,
            new Intent(this,RenderLongForegroundService.class).setAction(PAUSE),
            PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        String caption=completed+"/"+Math.max(1,total)+" verified frames — "+detail;
        Notification.Builder builder=new Notification.Builder(this,CHANNEL)
            .setSmallIcon(android.R.drawable.ic_media_play)
            .setContentTitle("Blender render • "+(jobId.length()==32?jobId.substring(0,8):"session"))
            .setContentText(caption)
            .setContentIntent(content)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(new Notification.Action.Builder(
                android.R.drawable.ic_media_pause,"Pause after frame",pause).build());
        if(total>0)builder.setProgress(total,Math.max(0,Math.min(total,completed)),false);
        else builder.setProgress(0,0,true);
        return builder.build();
    }

    private void promote(Notification notification){
        if(Build.VERSION.SDK_INT>=35){
            startForeground(ID,notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING);
        }else if(Build.VERSION.SDK_INT>=34){
            startForeground(ID,notification,ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        }else startForeground(ID,notification);
    }

    @Override public int onStartCommand(Intent command,int flags,int startId){
        String requested=command==null?null:command.getStringExtra(JOB);
        if(valid(requested))jobId=requested;
        if(!valid(jobId))jobId=getSharedPreferences(PREFS,MODE_PRIVATE).getString(JOB,"");
        if(!valid(jobId)){stopSelf();return START_NOT_STICKY;}
        // Promote immediately, within Android's foreground-service deadline.
        try{promote(notification("Preparing native Blender",0,0));}
        catch(RuntimeException denied){
            state(this,jobId,"FOREGROUND_PERMISSION_OR_QUOTA_BLOCKED",true);
            stopSelf();return START_NOT_STICKY;
        }

        if(command!=null && PAUSE.equals(command.getAction())){
            ownerPause=true;RenderManualJobs.pause();
            state(this,jobId,"PAUSING_AFTER_FRAME",false);
            update("Pausing after current frame");
            stopSelf();return START_NOT_STICKY;
        }

        boolean wanted=getSharedPreferences(PREFS,MODE_PRIVATE).getBoolean(WANTED,false);
        if(!wanted){
            state(this,jobId,"PAUSED_OWNER",false);
            stopSelf();return START_NOT_STICKY;
        }
        try{
            JSONObject current=ProductionBatch.jobStatus(this,jobId);
            if("encoded".equals(current.optString("state"))||
                (current.optInt("next_frame")>current.optInt("end_frame")&&
                 RenderManualJobs.stillImage(RenderManualJobs.readManifest(this,jobId)))){
                // A finished frame job may still need >10 GB of streaming
                // export. Do not re-render or pretend it is already in Downloads.
                state(this,jobId,"EXPORTING_TO_DOWNLOADS",true);
                monitor.execute(this::exportCompleted);
                return START_STICKY;
            }
        }catch(Exception problem){
            state(this,jobId,"CHECKPOINT_UNAVAILABLE",false);
            stopSelf();return START_NOT_STICKY;
        }
        if(!editorReady(this)){
            state(this,jobId,"AWAITING_EDITOR_FOREGROUND",true);
            update("Open Render Studio to restart the native Blender engine");
            stopSelf();return START_NOT_STICKY;
        }
        startPending=true;
        startAttempts=0;
        // Remote VideoStudio commands temporarily hold the native Binder lock.
        // Start the FGS immediately, then retry the job only AFTER the
        // original command returns; never return false and lose the request.
        monitor.schedule(this::attemptStart,2,TimeUnit.SECONDS);
        if(!monitorScheduled){
            monitorScheduled=true;
            monitor.scheduleWithFixedDelay(this::tick,4,5,TimeUnit.SECONDS);
        }
        return START_STICKY;
    }

    private void attemptStart(){
        if(destroyed||ownerPause)return;
        if(!getSharedPreferences(PREFS,MODE_PRIVATE).getBoolean(WANTED,false)){
            startPending=false;stopSelf();return;
        }
        if(!editorReady(this)){
            startPending=false;
            state(this,jobId,"AWAITING_EDITOR_FOREGROUND",true);
            update("Open Render to restart its native Blender editor");
            stopSelf();return;
        }
        if(RenderManualJobs.active()||RenderManualJobs.start(this,jobId)){
            startPending=false;
            state(this,jobId,"RENDERING",true);
            update("Rendering verified frames");
            return;
        }
        if(++startAttempts<12){
            state(this,jobId,"WAITING_FOR_NATIVE_EXECUTOR",true);
            update("Native Blender busy; waiting to claim frame executor");
            monitor.schedule(this::attemptStart,3,TimeUnit.SECONDS);
        }else{
            startPending=false;
            state(this,jobId,"WAITING_FOR_NATIVE_EXECUTOR",true);
            update("Native executor busy; open Render to resume");
            stopSelf();
        }
    }

    private void exportCompleted(){
        if(destroyed||ownerPause)return;
        state(this,jobId,"EXPORTING_TO_DOWNLOADS",true);
        update("Copying verified movie parts to Download/RenderStudio");
        try{
            JSONObject delivered=RenderManualJobs.export(this,jobId);
            if(delivered.optBoolean("segmented") &&
                !delivered.optBoolean("all_parts_downloads_verified"))
                throw new IllegalStateException("SEGMENT_EXPORT_UNCONFIRMED");
            if(!delivered.optBoolean("segmented") &&
                !delivered.optBoolean("readback_sha256_verified"))
                throw new IllegalStateException("DOWNLOADS_READBACK_UNCONFIRMED");
            state(this,jobId,"COMPLETED_EXPORTED",false);
            update("All video outputs verified in Downloads");
        }catch(Exception problem){
            // Existing PNG and MP4 masters remain app-private, and already
            // exported parts have independent SHA-bound MediaStore receipts.
            state(this,jobId,"OUTPUT_READY_EXPORT_RETRYABLE",false);
            update("Output safe; Downloads export pending: "+
                problem.getClass().getSimpleName());
        }finally{stopSelf();}
    }

    private void update(String message){
        if(destroyed)return;
        try{
            JSONObject s=RenderManualJobs.status(this);
            getSystemService(NotificationManager.class).notify(ID,
                notification(message,s.optInt("completed"),s.optInt("total")));
        }catch(RuntimeException ignored){/* Never fail native Blender for UI. */}
    }
    private void tick(){
        if(destroyed||ownerPause||startPending)return;
        JSONObject status=RenderManualJobs.status(this);
        String state=status.optString("state","");
        if(RenderManualJobs.active()){
            idlePolls=0;
            long now=SystemClock.elapsedRealtime();
            if(now-lastNotice>=5000){
                lastNotice=now;update(status.optString("detail","Native Blender rendering"));
            }
            return;
        }
        // Normal completion or a recoverable pause is now represented in
        // durable manifests. Never hallucinate that 24/24 frames were encoded.
        if(++idlePolls<2)return;
        if(state.equals("encoded")||state.equals("frames_complete")){
            exportCompleted();return;
        }
        String ending=state.equals("paused_error")?"PAUSED_ERROR":"PAUSED";
        state(this,jobId,ending,false);
        update(ending);
        stopSelf();
    }
    @Override public void onTaskRemoved(Intent rootIntent){
        // Ordinary swiping away of the UI is distinct from a process force-stop.
        // A START_STICKY foreground service may continue at checkpoint boundaries.
        super.onTaskRemoved(rootIntent);
    }
    @Override public void onTimeout(int startId,int fgsType){
        // Android 15+ mediaProcessing quota: a system-controlled hard boundary.
        // Never extend the quota by silently misdeclaring another FGS type.
        RenderManualJobs.pause();
        state(this,jobId,"PAUSED_ANDROID_FGS_QUOTA",true);
        update("Android render quota reached; resume from saved frame in app");
        stopSelf();
    }
    @Override public void onDestroy(){
        destroyed=true;
        monitor.shutdownNow();
        // If the system kills us while active, the manifest and consent remain.
        // The OS may later redeliver START_STICKY; user force-stop overrides it.
        if(RenderManualJobs.active())RenderManualJobs.pause();
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent){return null;}
}
