package com.rezox.render.agent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Owner-only in-app notification Stop action: never an exported intent. */
public final class NativeWorkStopReceiver extends BroadcastReceiver {
    public static final String ACTION_STOP="com.rezox.render.agent.STOP_NATIVE_WORK";
    @Override public void onReceive(Context context,Intent intent){
        if(intent==null || !ACTION_STOP.equals(intent.getAction()))return;
        AgentSecrets secrets=new AgentSecrets(context);
        // Prevent any new queued native command from being dispatched.
        secrets.videoStudioBridgeEnabled(false);
        secrets.enabled(false);
        VideoStudioNativeBridgeService.requestCancel();
        AgentWorkPresence.stage(context,"Stop requested - awaiting native checkpoint",-1);
        secrets.status("Stop requested from notification. A running Blender operation may finish before cancellation.");
    }
}
