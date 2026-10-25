package com.rezox.render.agent;

import android.app.Service;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

/** Visible on-device file I/O, separate from native renders and their quality settings. */
public final class FileTransferService extends Service {
    private static final String CHANNEL="render-file-transfers";
    private static final int NOTICE=94;
    private final ExecutorService worker=Executors.newSingleThreadExecutor();
    private final AtomicBoolean stopping=new AtomicBoolean(false);
    private volatile String active="";
    private volatile PowerManager.WakeLock wake;
    private final Object wakeGuard=new Object();
    private final AtomicInteger pendingRuns=new AtomicInteger();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private volatile boolean destroyed;
    private int latestStartId;
    private final Runnable refresh=new Runnable(){public void run(){
        if(destroyed)return;
        synchronized(wakeGuard){if(pendingRuns.get()>0&&wake!=null&&!wake.isHeld())wake.acquire(20*60*1000L);}
        try{getSystemService(NotificationManager.class).notify(NOTICE,notification());}catch(RuntimeException ignored){}
        ui.postDelayed(this,1500);
    }};

    public static JSONObject request(Context c,String id)throws Exception{
        JSONObject status=FileTransfers.status(c,id);
        if(status.getString("state").equals("completed"))return status;
        try{
            c.startForegroundService(new Intent(c,FileTransferService.class).putExtra("transfer_id",id));
            return status.put("foreground_launch_requested",true).put("foreground_start_confirmed",false);
        }catch(RuntimeException denied){
            return FileTransfers.defer(c,id,denied.getClass().getSimpleName()).put("foreground_launch_requested",false);
        }
    }
    @Override public void onCreate(){
        super.onCreate();
        getSystemService(NotificationManager.class).createNotificationChannel(
            new NotificationChannel(CHANNEL,"Render file transfers",NotificationManager.IMPORTANCE_LOW));
    }
    private PendingIntent control(String action){
        Intent intent=new Intent(this,FileTransferService.class).setAction(action).putExtra("transfer_id",active);
        return PendingIntent.getService(this,action.hashCode(),intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }
    private Notification notification(){
        String text="Preparing verified file transfer";
        int progress=0;boolean unknown=true;
        try{
            if(!active.isEmpty()){
                JSONObject status=FileTransfers.status(this,active);long total=status.optLong("total_bytes",-1),done=status.optLong("bytes_transferred",0);
                text=status.optString("state","queued")+" · "+done/1048576+" MiB"+(total>0?" / "+total/1048576+" MiB":"");
                if(total>0){progress=(int)Math.min(100,done*100/total);unknown=false;}
            }
        }catch(Exception ignored){}
        PendingIntent open=PendingIntent.getActivity(this,94,new Intent(this,AgentActivity.class),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this,CHANNEL).setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Render file transfer").setContentText(text).setContentIntent(open).setOngoing(true)
            .setProgress(100,progress,unknown)
            .addAction(new Notification.Action.Builder(android.R.drawable.ic_media_pause,"Pause",control("pause")).build())
            .addAction(new Notification.Action.Builder(android.R.drawable.ic_menu_close_clear_cancel,"Cancel",control("cancel")).build()).build();
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId){
        latestStartId=startId;
        String requested=intent==null?null:intent.getStringExtra("transfer_id");
        if(pendingRuns.get()==0&&requested!=null&&!requested.isEmpty())active=requested;
        try{
            if(Build.VERSION.SDK_INT>=29)startForeground(NOTICE,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            else startForeground(NOTICE,notification());
        }catch(RuntimeException denied){
            try{if(requested!=null)FileTransfers.defer(this,requested,denied.getClass().getSimpleName());}catch(Exception ignored){}
            stopSelfResult(startId);return START_NOT_STICKY;
        }
        ui.removeCallbacks(refresh);ui.postDelayed(refresh,1500);
        if(intent!=null&&("pause".equals(intent.getAction())||"cancel".equals(intent.getAction()))){
            try{FileTransfers.control(this,requested,intent.getAction());}catch(Exception ignored){}
            if(pendingRuns.get()==0){stopForeground(STOP_FOREGROUND_REMOVE);stopSelfResult(startId);}
            return START_NOT_STICKY;
        }
        stopping.set(false);pendingRuns.incrementAndGet();worker.submit(()->{
            try{
                PowerManager manager=getSystemService(PowerManager.class);
                synchronized(wakeGuard){wake=manager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"Render:FileTransfer");wake.setReferenceCounted(false);wake.acquire(20*60*1000L);}
                while(!stopping.get()){
                    org.json.JSONArray tasks=FileTransfers.list(this).getJSONArray("transfers");String next=null;
                    for(int i=0;i<tasks.length();i++)if("queued".equals(tasks.getJSONObject(i).optString("state"))){next=tasks.getJSONObject(i).getString("transfer_id");break;}
                    if(next==null)break;active=next;
                    FileTransfers.run(this,next,stopping);
                    getSystemService(NotificationManager.class).notify(NOTICE,notification());
                    synchronized(wakeGuard){if(wake!=null&&!wake.isHeld())wake.acquire(20*60*1000L);}
                }
            }catch(Exception ignored){ /* Persisted tasks remain inspectable and explicitly resumable. */ }
            finally{int pending;synchronized(wakeGuard){if(wake!=null&&wake.isHeld())wake.release();wake=null;pending=pendingRuns.decrementAndGet();}if(pending==0)ui.post(()->{
                if(pendingRuns.get()==0&&stopSelfResult(latestStartId))stopForeground(STOP_FOREGROUND_REMOVE);
            });}
        });
        return START_NOT_STICKY; // OS/process interruption requires explicit resume; never promises force-stop execution.
    }
    @Override public void onTimeout(int startId,int type){
        stopping.set(true);try{if(!active.isEmpty())FileTransfers.defer(this,active,"ANDROID_DATA_SYNC_TIME_BUDGET_REQUIRES_OWNER_OPEN");}catch(Exception ignored){}
        stopForeground(STOP_FOREGROUND_REMOVE);stopSelf();
    }
    @Override public void onDestroy(){destroyed=true;stopping.set(true);ui.removeCallbacks(refresh);worker.shutdown();synchronized(wakeGuard){if(wake!=null&&wake.isHeld())wake.release();wake=null;}super.onDestroy();}
    @Override public IBinder onBind(Intent intent){return null;}
}
