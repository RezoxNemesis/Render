package com.rezox.render.agent;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Explicitly user-started native executor. Never boots itself or opens a listening port. */
public final class AgentService extends Service {
    public static final String STOP="com.rezox.render.agent.STOP";
    private static final String CHANNEL="render-agent";
    private static final AtomicBoolean PROCESS_BUSY=new AtomicBoolean(false);
    private AgentSecrets secrets;
    private AgentJournal journal;
    private AgentActions actions;
    private JSONObject credentials;
    private final ScheduledExecutorService transport=Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService executor=Executors.newSingleThreadExecutor();
    private volatile Work active;
    private boolean scheduled;
    private volatile boolean destroyed;
    private static final class Work {
        final AgentEnvelope envelope;
        final AtomicBoolean cancelled=new AtomicBoolean(false);
        Work(AgentEnvelope envelope){this.envelope=envelope;}
    }
    @Override public void onCreate(){
        super.onCreate();secrets=new AgentSecrets(this);journal=new AgentJournal(this);
        try{
            credentials=secrets.load();
            if(PROCESS_BUSY.get()){
                secrets.enabled(false);secrets.status("Previous native call is still stopping; wait before restarting.");
            }else{journal.recover();actions=new AgentActions(this);}
        }catch(Exception e){secrets.enabled(false);secrets.status("Agent initialization failed: "+e.getClass().getSimpleName());}
        getSystemService(NotificationManager.class).createNotificationChannel(
            new NotificationChannel(CHANNEL,"ChatGPT x Render",NotificationManager.IMPORTANCE_LOW));
    }
    private Notification notification(){
        PendingIntent open=PendingIntent.getActivity(this,1,new Intent(this,AgentActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,2,new Intent(this,AgentService.class).setAction(STOP),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle("ChatGPT x Render").setContentText("Native command session — tap to inspect or Stop")
            .setContentIntent(open).setOngoing(true).addAction(new Notification.Action.Builder(
                android.R.drawable.ic_media_pause,"Stop",stop).build()).build();
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        startForeground(39,notification());
        if(intent!=null&&STOP.equals(intent.getAction())){
            secrets.enabled(false);Work w=active;if(w!=null)w.cancelled.set(true);
            secrets.status(w==null?"Stopped locally.":"Stopping after the current non-interruptible native call.");
        }
        if(credentials==null||actions==null){secrets.enabled(false);stopSelf();return START_NOT_STICKY;}
        if(!scheduled){scheduled=true;transport.scheduleWithFixedDelay(this::tick,0,5,TimeUnit.SECONDS);}
        return START_NOT_STICKY;
    }
    private JSONObject post(String path,JSONObject body)throws Exception{
        return AgentHttp.post(credentials.getString("relay"),path,credentials.getString("device_token"),body);
    }
    private void sendPending()throws Exception{
        for(JSONObject result:journal.pending(credentials.getString("device_id"))){
            JSONObject ack=post("/v1/device/result",result);
            if(ack.optBoolean("accepted"))journal.acknowledge(result.getString("job_id"));
        }
    }
    private void tick(){
        if(destroyed)return;
        try{
            sendPending();
            Work w=active;
            if(!secrets.enabled()&&w!=null)w.cancelled.set(true);
            JSONObject reply=post("/v1/device/poll",new JSONObject().put("enabled",secrets.enabled())
                .put("capabilities",AgentActions.capabilities(getApplicationContext())).put("active_job_id",w==null?JSONObject.NULL:w.envelope.id));
            JSONArray cancelled=reply.optJSONArray("cancel_job_ids");
            if(w!=null&&cancelled!=null)for(int i=0;i<cancelled.length();i++)
                if(w.envelope.id.equals(cancelled.getString(i)))w.cancelled.set(true);
            secrets.status(secrets.enabled()?"Relay authenticated. Waiting for authorized commands or running on this phone.":
                (active==null?"Stopped. No new commands will run.":"Stopping after current native call."));
            JSONObject job=reply.optJSONObject("job");
            if(job!=null&&secrets.enabled()&&active==null&&!destroyed){
                AgentEnvelope envelope=new AgentEnvelope(job,credentials.getString("device_id"));
                boolean wasCancelled=false;
                if(cancelled!=null)for(int i=0;i<cancelled.length();i++)if(envelope.id.equals(cancelled.getString(i)))wasCancelled=true;
                if(journal.begin(envelope.id,envelope.digest,envelope.command)){
                    Work pending=new Work(envelope);pending.cancelled.set(wasCancelled||!secrets.enabled());
                    if(!PROCESS_BUSY.compareAndSet(false,true)){
                        journal.finish(envelope.id,"recovery_required",new JSONObject().put("error","OTHER_NATIVE_CALL_STILL_ACTIVE"));
                    }else{
                        active=pending;
                        try{executor.execute(()->execute(pending));}
                        catch(java.util.concurrent.RejectedExecutionException e){
                            PROCESS_BUSY.set(false);active=null;
                            journal.finish(envelope.id,"recovery_required",new JSONObject().put("error","EXECUTOR_STOPPED_BEFORE_DISPATCH"));
                        }
                    }
                }
            }
        }catch(AgentHttp.RelayException e){
            if(e.status==401||e.status==403){
                secrets.enabled(false);Work w=active;if(w!=null)w.cancelled.set(true);
                secrets.status("Connection authorization revoked or expired. No further commands will execute.");
            }else secrets.status("Relay unavailable (HTTP "+e.status+"). Pending results are retained locally.");
        }catch(Exception e){
            secrets.status("Connection interrupted: "+e.getClass().getSimpleName()+". Pending work is journaled.");
        }finally{
            if(!secrets.enabled()&&active==null)stopSelf();
        }
    }
    private void execute(Work work){
        String state="failed";JSONObject result=new JSONObject();
        try{
            if(!secrets.enabled()||destroyed)work.cancelled.set(true);
            if(work.cancelled.get()){
                state="cancelled";result.put("executed",false);
            }else{
                result=actions.execute(work.envelope.command,work.cancelled);
                if(work.cancelled.get()||!secrets.enabled()||destroyed){
                    state="cancelled";result.put("native_call_completed_after_cancel",true);
                }else state="succeeded";
            }
        }catch(Exception|LinkageError e){
            state=e instanceof BlenderSpool.RecoveryRequired ? "recovery_required"
                :work.cancelled.get()?"cancelled":"failed";
            try{
                String code=e.getMessage();
                if(code==null||!code.matches("[A-Z_]{3,96}"))code=e.getClass().getSimpleName();
                result=new JSONObject().put("error",code).put("executed_by","android-agent");
            }catch(Exception ignored){}
        }finally{
            try{journal.finish(work.envelope.id,state,result);}
            catch(Exception e){secrets.enabled(false);secrets.status("Result journal failed. Recovery required; automatic replay disabled.");}
            active=null;PROCESS_BUSY.set(false);
        }
    }
    @Override public void onDestroy(){
        destroyed=true;Work w=active;if(w!=null)w.cancelled.set(true);
        transport.shutdownNow();executor.shutdown();stopForeground(STOP_FOREGROUND_REMOVE);
        // Journal remains open until any non-interruptible native call records its outcome.
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent){return null;}
}
