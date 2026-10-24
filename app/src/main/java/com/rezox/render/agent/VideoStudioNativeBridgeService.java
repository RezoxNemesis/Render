package com.rezox.render.agent;

import android.app.Service;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;

import org.json.JSONObject;

import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * No server, open port, Gallery access, shell or arbitrary Python. The existing
 * VideoStudio Android native agent can forward a typed command through Binder.
 *
 * Android Messenger stamps Message.sendingUid with the actual caller UID.
 * Rejects every caller except the installed VideoStudio package. The owner
 * must also enable this exact bridge locally in Render.
 */
public final class VideoStudioNativeBridgeService extends Service {
    public static final String VIDEOSTUDIO_PACKAGE = "com.rezoxnemesis.videostudio";
    public static final int EXECUTE = 1;
    public static final int RESPONSE = 2;
    private static volatile AtomicBoolean runningCancellation;
    private static volatile String runningCommandId="";
    private static volatile VideoStudioNativeBridgeService currentService;
    private volatile boolean destroying;
    private final java.util.Set<String> scheduled=java.util.concurrent.ConcurrentHashMap.newKeySet();
    private final Handler retry=new Handler(Looper.getMainLooper());
    private final ThreadPoolExecutor controls=new ThreadPoolExecutor(1,1,0L,TimeUnit.MILLISECONDS,
        new ArrayBlockingQueue<>(4),new ThreadPoolExecutor.AbortPolicy());
    /** Commands waiting only inside Render Android; not the cloud transport. */
    public static int pendingBinderCommands(){
        VideoStudioNativeBridgeService current=currentService;
        return current==null?0:current.worker.getQueue().size();
    }
    public static boolean binderServiceActive(){return currentService!=null;}
    // Bound incoming Binder work. An unlimited queue can exhaust the app while
    // Blender renders or the phone is under memory/thermal pressure.
    private final ThreadPoolExecutor worker = new ThreadPoolExecutor(
            1,1,0L,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(12),
            new ThreadPoolExecutor.AbortPolicy());
    private AgentJournal journal;
    private AgentSecrets secrets;

    /** Stop makes new commands immediately unavailable and cancels active work
     * at the next Blender cooperative checkpoint; never pretend hard cancellation.
     */
    public static void requestCancel() {
        AtomicBoolean flag = runningCancellation;
        if(flag != null) flag.set(true);
    }
    public static JSONObject cancelCommand(android.content.Context context,String id)throws Exception{
        boolean queued;
        try(AgentJournal journal=new AgentJournal(context)){queued=journal.cancelQueued(id);}
        boolean active=id.equals(runningCommandId)&&runningCancellation!=null;
        if(active)runningCancellation.set(true);
        return new JSONObject().put("command_id",id).put("queued_cancelled",queued)
            .put("cancellation_requested",active).put("native_completion_confirmed",false)
            .put("current_frame_may_finish",active).put("replayed",false);
    }

    /** Shared by Android unit tests and the Binder entry point. */
    public static boolean trustedCallerPackages(String[] packages) {
        if(packages == null) return false;
        for(String id : packages)
            if(VIDEOSTUDIO_PACKAGE.equals(id)) return true;
        return false;
    }

    @Override public void onCreate() {
        super.onCreate();
        currentService=this;
        secrets = new AgentSecrets(this);
        journal = new AgentJournal(this);
        if(!AgentExecutionLock.BUSY.get()) {
            try {
                journal.recover();
                AgentWorkPresence.recoverIfInterrupted(this);
            }
            catch(Exception error) {
                secrets.videoStudioBridgeEnabled(false);
                secrets.status("Render native command journal requires recovery.");
            }
        }
        if(secrets.videoStudioBridgeEnabled()){
            try{for(JSONObject command:journal.queued()){
                String id=command.getString("journal_id");command.remove("journal_id");
                schedule(null,id,command);
            }}catch(Exception error){secrets.status("Durable Binder queue requires inspection.");}
        }
    }

    private final Messenger messenger = new Messenger(new Handler(Looper.getMainLooper()) {
        @Override public void handleMessage(Message inbound) {
            if(inbound.what != EXECUTE) return;
            final Messenger caller = inbound.replyTo;
            if(caller == null) return;
            // Only the Android system-supplied sendingUid is trusted.
            if(!trustedCallerPackages(getPackageManager().getPackagesForUid(inbound.sendingUid))) {
                send(caller,"",error("VIDEOSTUDIO_APP_NOT_AUTHORIZED"));
                return;
            }
            if(!secrets.videoStudioBridgeEnabled()) {
                send(caller,"",error("RENDER_DIRECT_BRIDGE_DISABLED_ON_PHONE"));
                return;
            }
            Bundle data = inbound.getData();
            final String id=data == null ? "" : data.getString("commandId","");
            final String action=data == null ? "" : data.getString("action","");
            final String raw=data == null ? "{}" : data.getString("args","{}");
            if(!id.matches("[A-Za-z0-9_-]{8,128}") || raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>131072 ||
                !action.matches("[A-Za-z0-9._-]{1,80}")) {
                send(caller,id,error("INVALID_RENDER_IPC_ENVELOPE"));
                return;
            }
            try {
                JSONObject args=new JSONObject(raw);
                java.util.Set<String> fields=new java.util.HashSet<>();args.keys().forEachRemaining(fields::add);
                AgentPolicy.validate(id,1,action,fields);
                if(ProductionBridge.ACTION.equals(action)&&ProductionBridge.outOfBand(args)){
                    controls.execute(()->{
                        try{send(caller,id,new JSONObject().put("ok",true)
                            .put("native_result",ProductionBridge.execute(VideoStudioNativeBridgeService.this,args,new AtomicBoolean(false)))
                            .put("target_package",getPackageName()).put("target_app",RenderConnectionCard.APP)
                            .put("render_public_id",secrets.renderPublicId()));}
                        catch(Exception error){send(caller,id,error(safeCode(error)));}
                    });
                    return;
                }
                JSONObject command=new JSONObject().put("device_id","videostudio-native-ipc")
                    .put("request_id",id).put("api_version",1).put("action",action).put("args",args);
                String digest=AgentPolicy.sha256(command.toString());
                if(!journal.enqueue(id,digest,command)){
                    JSONObject prior=journal.snapshot(id,digest);
                    if("queued".equals(prior.optString("state")))schedule(caller,id,command);
                    else if("running_on_device".equals(prior.optString("state")))
                        send(caller,id,new JSONObject().put("ok",false).put("state","running_on_device")
                            .put("command_id",id).put("safe_to_replay",false).put("poll_operation","ipc.command.status"));
                    else send(caller,id,prior.getJSONObject("result"));
                }else schedule(caller,id,command);
            } catch(Exception ex) {
                send(caller,id,error(safeCode(ex)));
            }
        }
    });

    @Override public IBinder onBind(Intent intent) {
        return messenger.getBinder();
    }

    private static String safeCode(Exception error){
        String code=error.getMessage();
        return code!=null&&code.matches("[A-Z_]{3,96}")?code:error.getClass().getSimpleName();
    }
    private void schedule(Messenger caller,String id,JSONObject command){
        if(destroying||!scheduled.add(id))return;
        try{worker.execute(()->executeNative(caller,id,command));}
        catch(RejectedExecutionException error){
            scheduled.remove(id);
            // Acceptance is already durable. Report queued, never invite a new ID.
            send(caller,id,error("COMMAND_DURABLY_QUEUED_POLL_EXACT_ID"));
            if(!destroying)retry.postDelayed(()->schedule(caller,id,command),5000);
        }
    }
    private void executeNative(Messenger caller,String id,JSONObject command) {
        if(destroying){scheduled.remove(id);return;}
        if(!AgentExecutionLock.BUSY.compareAndSet(false,true)){
            scheduled.remove(id);
            retry.postDelayed(()->schedule(caller,id,command),5000);
            return;
        }
        String action=command.optString("action");
        AtomicBoolean cancel=new AtomicBoolean(false);
        runningCancellation=cancel;
        runningCommandId=id;
        JSONObject outcome=error("RENDER_NATIVE_ACTION_FAILED");
        String state="failed";
        boolean journaled=false;
        boolean liveWork=false;
        try {
            if(!secrets.videoStudioBridgeEnabled())
                throw new IllegalStateException("RENDER_DIRECT_BRIDGE_DISABLED_ON_PHONE");
            JSONObject args=command.getJSONObject("args");
            java.util.Set<String> fields=new java.util.HashSet<>();
            args.keys().forEachRemaining(fields::add);
            AgentPolicy.validate(id,1,action,fields);
            String digest=AgentPolicy.sha256(command.toString());
            if(!journal.claim(id,digest)) {
                JSONObject prior=journal.snapshot(id,digest);
                if(prior!=null && !"running_on_device".equals(prior.optString("state")) && !"queued".equals(prior.optString("state"))) {
                    // The finally block will send exactly one native receipt.
                    // No Blender operation or journal replay occurs.
                    outcome=prior.getJSONObject("result");
                    return;
                }
                throw new IllegalStateException("NATIVE_RESULT_RECOVERY_REQUIRED");
            }
            journaled=true;
            liveWork=true;
            BlenderSpool.carrier(id);
            AgentWorkPresence.begin(this,"render."+action,"VideoStudio MCP v3 Binder");
            JSONObject nativeResult=new AgentActions(this).execute(command,cancel);
            if(cancel.get() || !secrets.videoStudioBridgeEnabled()) {
                state="cancelled";
                outcome=new JSONObject().put("ok",false).put("error","NATIVE_COMMAND_CANCELLED")
                    .put("native_result",nativeResult).put("native_call_completed_after_cancel",true);
            } else {
                state="succeeded";
                // Never return the default failure marker alongside ok=true.
                // A new object makes native success unambiguous to ChatGPT.
                outcome=new JSONObject().put("ok",true).put("native_result",nativeResult)
                    .put("executed_by","Render Android");
            }
        } catch(Exception | LinkageError error) {
            String code=error.getMessage();
            if(code==null || !code.matches("[A-Z_]{3,96}"))
                code=error.getClass().getSimpleName();
            state=error instanceof BlenderSpool.RecoveryRequired?"recovery_required":
                  cancel.get()?"cancelled":"failed";
            try { outcome.put("ok",false).put("error",code).put("state",state);
                if(error instanceof BlenderSpool.NativeActionFailure){
                    BlenderSpool.NativeActionFailure failure=(BlenderSpool.NativeActionFailure)error;
                    outcome.put("native_command_id",failure.commandId).put("native_failure",failure.receipt)
                        .put("recovery_operation","native.command.status").put("safe_to_replay",false);
                }
                if(error instanceof BlenderSpool.RecoveryRequired)
                    outcome.put("native_command_id",((BlenderSpool.RecoveryRequired)error).commandId)
                        .put("recovery_operation","native.command.status"); }
            catch(Exception ignored){}
        } finally {
            // Every completed IPC receipt clearly identifies the actual
            // Android executor so ChatGPT can distinguish Render from VideoStudio.
            try {
                outcome.put("target_app",RenderConnectionCard.APP);
                outcome.put("target_package",getPackageName());
                outcome.put("render_public_id",secrets.renderPublicId());
                outcome.put("transport","VideoStudio MCP v3 > Android Binder");
            } catch(Exception ignored) {}
            if(journaled) {
                try {
                    journal.finish(id,state,outcome);
                    secrets.recordVideoStudioNativeResult();
                }
                catch(Exception error){
                    outcome=error("RENDER_JOURNAL_WRITE_FAILED");
                    state="recovery_required";
                    secrets.videoStudioBridgeEnabled(false);
                }
            }
            if(liveWork) {
                try {AgentWorkPresence.finish(this,state,outcome.optJSONObject("native_result"));}
                catch(Exception ignored) { /* Native journal is the source of truth. */ }
            }
            send(caller,id,outcome);
            runningCancellation=null;
            BlenderSpool.carrier(null);
            runningCommandId="";
            scheduled.remove(id);
            AgentExecutionLock.BUSY.set(false);
        }
    }

    private static JSONObject error(String code) {
        JSONObject result=new JSONObject();
        try {result.put("ok",false).put("error",code);}catch(Exception ignored){}
        return result;
    }

    private static void send(Messenger replyTo,String id,JSONObject output) {
        try {
            Message message=Message.obtain(null,RESPONSE);
            Bundle data=new Bundle();
            data.putString("commandId",id);
            data.putString("result",output.toString());
            message.setData(data);
            replyTo.send(message);
        } catch(Exception ignored) {
            // The Android CommandJournal retains the native result if the
            // VideoStudio binder dies before the acknowledgment arrives.
        }
    }

    @Override public void onDestroy(){
        destroying=true;
        retry.removeCallbacksAndMessages(null);
        currentService=null;
        requestCancel();
        controls.shutdown();
        worker.shutdown();
        super.onDestroy();
    }
}
