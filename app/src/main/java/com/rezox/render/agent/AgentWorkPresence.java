package com.rezox.render.agent;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;

/**
 * Honest local presence. A hand in the Render console and an Android notification
 * reflect ONLY work actually accepted by Render's native executors.
 * Stores no owner token, request body, prompt, media path or private credential.
 */
public final class AgentWorkPresence {
    private static final String PREF="render_native_work_presence";
    private static final String CHANNEL="render-native-work";
    private static final int NOTIFICATION_ID=78;
    private static final long MAX_STALE_MS=35_000L;
    private static final Object LOCK=new Object();

    private AgentWorkPresence(){}

    public static final class Snapshot {
        public final String state,action,stage,source;
        public final long startedAt,updatedAt;
        public final int progress;
        Snapshot(String state,String action,String stage,String source,
                 long startedAt,long updatedAt,int progress){
            this.state=state;this.action=action;this.stage=stage;this.source=source;
            this.startedAt=startedAt;this.updatedAt=updatedAt;this.progress=progress;
        }
        public boolean isWorking(){return "running".equals(state);}
        public boolean needsRecovery(){return "recovery_required".equals(state);}
        public String description(){
            if(isWorking())return "Working in Blender • "+action+" • "+stage+
                    (progress>=0?" ("+progress+"%)":"");
            if(needsRecovery())return "Native command interrupted • inspect history before retrying";
            if("succeeded".equals(state))return "Last native command completed • "+action;
            if("failed".equals(state)||"cancelled".equals(state))
                return "Last native command "+state+" • "+action;
            return "No native Blender command is running";
        }
    }

    private static SharedPreferences prefs(Context ctx){
        return ctx.getApplicationContext().getSharedPreferences(PREF,Context.MODE_PRIVATE);
    }

    public static Snapshot snapshot(Context ctx){
        synchronized(LOCK){
            SharedPreferences p=prefs(ctx);
            String state=p.getString("state","idle");
            long last=p.getLong("updated",0L);
            if("running".equals(state) && System.currentTimeMillis()-last>MAX_STALE_MS &&
                    !AgentExecutionLock.BUSY.get()){
                state="recovery_required";
            }
            return new Snapshot(state,p.getString("action",""),p.getString("stage",""),
                    p.getString("source",""),p.getLong("started",0L),last,
                    p.getInt("progress",-1));
        }
    }

    public static void begin(Context ctx,String action,String source){
        synchronized(LOCK){
            long now=System.currentTimeMillis();
            prefs(ctx).edit().putString("state","running")
                    .putString("action",action).putString("stage","Accepted by native executor")
                    .putString("source",source).putLong("started",now)
                    .putLong("updated",now).putInt("progress",-1).apply();
            notifyOwner(ctx,true);
        }
    }

    public static void stage(Context ctx,String stage,int percent){
        synchronized(LOCK){
            SharedPreferences p=prefs(ctx);
            if(!"running".equals(p.getString("state","")))return;
            int value=percent<0?-1:Math.max(0,Math.min(100,percent));
            p.edit().putString("stage",stage).putInt("progress",value)
                    .putLong("updated",System.currentTimeMillis()).apply();
            notifyOwner(ctx,true);
        }
    }

    public static void finish(Context ctx,String state){
        synchronized(LOCK){
            if(!"succeeded".equals(state)&&!"failed".equals(state)&&
               !"cancelled".equals(state)&&!"recovery_required".equals(state))
                state="recovery_required";
            SharedPreferences p=prefs(ctx);
            p.edit().putString("state",state)
                    .putString("stage",state.equals("succeeded")?
                        "Native result journaled":"Check native result journal")
                    .putLong("updated",System.currentTimeMillis()).apply();
            notifyOwner(ctx,false);
        }
    }

    /** Called when a process was restarted, not while another executor is active. */
    public static void recoverIfInterrupted(Context ctx){
        synchronized(LOCK){
            if("running".equals(prefs(ctx).getString("state","")))
                finish(ctx,"recovery_required");
        }
    }

    private static void notifyOwner(Context ctx,boolean running){
        if(Build.VERSION.SDK_INT>=33 && ctx.checkSelfPermission(
                Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;
        NotificationManager manager=ctx.getSystemService(NotificationManager.class);
        if(manager==null)return;
        manager.createNotificationChannel(new NotificationChannel(
                CHANNEL,"Render Studio native work",NotificationManager.IMPORTANCE_LOW));
        Snapshot s=snapshot(ctx);
        Intent open=new Intent(ctx,AgentActivity.class);
        PendingIntent intent=PendingIntent.getActivity(ctx,78,open,
                PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder=new Notification.Builder(ctx,CHANNEL)
                .setSmallIcon(android.R.drawable.ic_menu_manage)
                .setContentTitle(running?"👆 Render Studio is working":"Render Studio native result")
                .setContentText(s.description())
                .setStyle(new Notification.BigTextStyle().bigText(s.description()))
                .setContentIntent(intent)
                .setOngoing(running)
                .setAutoCancel(!running)
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_PROGRESS);
        if(running){
            PendingIntent stop=PendingIntent.getBroadcast(ctx,79,
                    new Intent(ctx,NativeWorkStopReceiver.class)
                        .setAction(NativeWorkStopReceiver.ACTION_STOP),
                    PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
            builder.addAction(new Notification.Action.Builder(
                    android.R.drawable.ic_media_pause,
                    "Stop new commands",stop).build());
            builder.setWhen(s.startedAt>0?s.startedAt:System.currentTimeMillis())
                    .setUsesChronometer(true)
                    .setProgress(100,Math.max(s.progress,0),s.progress<0);
        }else{
            builder.setProgress(0,0,false).setTimeoutAfter(120_000L);
        }
        manager.notify(NOTIFICATION_ID,builder.build());
    }
}
