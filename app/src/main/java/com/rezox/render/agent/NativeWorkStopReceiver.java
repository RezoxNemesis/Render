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
        // Stop new direct-MCP claims and request cancellation from the visible
        // Android agent service. Never invoke an unrelated app or Binder.
        secrets.enabled(false);
        try{
            context.startService(new Intent(context,AgentService.class).setAction(AgentService.STOP));
        }catch(RuntimeException ignored){
            // The session flag is already persisted; the next agent tick stops.
        }
        AgentWorkPresence.stage(context,"Stop requested - awaiting native checkpoint",-1);
        secrets.status("Stop requested from notification. A running Blender operation may finish before cancellation.");
    }
}
