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

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
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
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private AgentJournal journal;
    private AgentSecrets secrets;

    /** Stop makes new commands immediately unavailable and cancels active work
     * at the next Blender cooperative checkpoint; never pretend hard cancellation.
     */
    public static void requestCancel() {
        AtomicBoolean flag = runningCancellation;
        if(flag != null) flag.set(true);
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
        secrets = new AgentSecrets(this);
        journal = new AgentJournal(this);
        if(!AgentExecutionLock.BUSY.get()) {
            try { journal.recover(); }
            catch(Exception error) {
                secrets.videoStudioBridgeEnabled(false);
                secrets.status("Render native command journal requires recovery.");
            }
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
            if(!id.matches("[A-Za-z0-9_-]{8,128}") || raw.length()>32768 ||
                !action.matches("[A-Za-z0-9._-]{1,80}")) {
                send(caller,id,error("INVALID_RENDER_IPC_ENVELOPE"));
                return;
            }
            try { worker.execute(() -> executeNative(caller,id,action,raw)); }
            catch(RejectedExecutionException ex) {
                send(caller,id,error("RENDER_AGENT_STOPPING"));
            }
        }
    });

    @Override public IBinder onBind(Intent intent) {
        return messenger.getBinder();
    }

    private void executeNative(Messenger caller,String id,String action,String raw) {
        if(!AgentExecutionLock.BUSY.compareAndSet(false,true)){
            send(caller,id,error("RENDER_NATIVE_EXECUTOR_BUSY"));
            return;
        }
        AtomicBoolean cancel=new AtomicBoolean(false);
        runningCancellation=cancel;
        JSONObject outcome=error("RENDER_NATIVE_ACTION_FAILED");
        String state="failed";
        boolean journaled=false;
        try {
            if(!secrets.videoStudioBridgeEnabled())
                throw new IllegalStateException("RENDER_DIRECT_BRIDGE_DISABLED_ON_PHONE");
            JSONObject args=new JSONObject(raw);
            java.util.Set<String> fields=new java.util.HashSet<>();
            args.keys().forEachRemaining(fields::add);
            AgentPolicy.validate(id,1,action,fields);
            JSONObject command=new JSONObject().put("device_id","videostudio-native-ipc")
                .put("request_id",id).put("api_version",1).put("action",action).put("args",args);
            String digest=AgentPolicy.sha256(command.toString());
            if(!journal.begin(id,digest,command)) {
                JSONObject prior=journal.snapshot(id,digest);
                if(prior!=null && !"running_on_device".equals(prior.optString("state"))) {
                    // The finally block will send exactly one native receipt.
                    // No Blender operation or journal replay occurs.
                    outcome=prior.getJSONObject("result");
                    return;
                }
                throw new IllegalStateException("NATIVE_RESULT_RECOVERY_REQUIRED");
            }
            journaled=true;
            JSONObject nativeResult=new AgentActions(this).execute(command,cancel);
            if(cancel.get() || !secrets.videoStudioBridgeEnabled()) {
                state="cancelled";
                outcome.put("ok",false).put("error","NATIVE_COMMAND_CANCELLED");
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
            try { outcome.put("ok",false).put("error",code).put("state",state); }
            catch(Exception ignored){}
        } finally {
            // Every completed IPC receipt clearly identifies the actual
            // Android executor so ChatGPT can distinguish Render from VideoStudio.
            try {
                outcome.put("target_app",RenderConnectionCard.APP);
                outcome.put("target_package",RenderConnectionCard.PACKAGE);
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
                    secrets.videoStudioBridgeEnabled(false);
                }
            }
            send(caller,id,outcome);
            runningCancellation=null;
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
        requestCancel();
        worker.shutdown();
        super.onDestroy();
    }
}
