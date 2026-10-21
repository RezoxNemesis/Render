package com.rezox.render.agent;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONObject;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.atomic.AtomicBoolean;

/** Owner-visible pairing, opt-in native execution, activity history, Stop and Revoke. */
public final class AgentActivity extends Activity {
    private AgentSecrets secrets;
    private AgentJournal journal;
    private EditText relay,enrollment;
    private TextView status,history;
    private final ExecutorService background=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private boolean busy;
    private final Runnable refresh=new Runnable(){public void run(){
        if(isFinishing()||isDestroyed())return;
        status.setText(secrets.status());history.setText(journal.history());ui.postDelayed(this,2000);
    }};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        secrets=new AgentSecrets(this);journal=new AgentJournal(this);
        ScrollView scroll=new ScrollView(this);LinearLayout content=new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);int pad=(int)(20*getResources().getDisplayMetrics().density);
        content.setPadding(pad,pad,pad,pad);content.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        scroll.addView(content);setContentView(scroll);
        label(content,"ChatGPT × Render",26);
        label(content,"All project work executes on this Android phone. The HTTPS relay carries commands and results only.",15);
        status=label(content,secrets.status(),15);
        relay=new EditText(this);relay.setHint("Relay origin, https://…");relay.setSingleLine(true);
        relay.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);content.addView(relay);
        enrollment=new EditText(this);enrollment.setHint("One-use private enrollment code");enrollment.setSingleLine(true);
        enrollment.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);content.addView(enrollment);
        try{JSONObject c=secrets.load();if(c!=null)relay.setText(c.optString("relay"));}catch(Exception ignored){}
        button(content,"Pair this phone",()->pair());
        button(content,"New ChatGPT link code",()->link());
        button(content,"Start autonomous session",()->startSession());
        button(content,"Stop native commands",()->stopSession());
        button(content,"Revoke this connection",()->new AlertDialog.Builder(this)
            .setTitle("Revoke remote control?").setMessage("Stops new work and revokes this phone's relay credential and ChatGPT access tokens. Existing imported projects are not deleted.")
            .setNegativeButton("Keep connection",null).setPositiveButton("Revoke",(d,w)->revoke()).show());
        button(content,"Check native agent locally",()->localCheck());
        button(content,"Open Render project inspector",()->startActivity(new Intent(this,com.rezox.render.MainActivity.class)));
        label(content,"Activity on this phone",20);history=label(content,journal.history(),14);
        label(content,"Available on the full-engine APK when Blender is open: bpy scene summary and native cube creation. Also available: imported-project inventory, .blend inspection and GPU diagnostics. Other modeling, animation and rendering tools require tested native handlers.",14);
        label(content,"Android may pause background execution. Work and outcomes are journaled; an unfinished native call is never silently replayed.",14);
        ui.post(refresh);
    }
    private TextView label(LinearLayout parent,String text,int size){TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setPadding(0,10,0,10);parent.addView(v);return v;}
    private void button(LinearLayout parent,String name,Runnable action){Button b=new Button(this);b.setText(name);parent.addView(b);b.setOnClickListener(v->action.run());}
    private interface Task{String run()throws Exception;}
    private void perform(Task task){
        if(busy){secrets.status("A setup request is already running.");return;}busy=true;
        background.execute(()->{
            String answer;try{answer=task.run();}catch(Exception e){answer="Request failed: "+e.getClass().getSimpleName()+". No credential was exposed.";}
            final String message=answer;ui.post(()->{busy=false;if(!isFinishing()&&!isDestroyed()){
                new AlertDialog.Builder(this).setTitle("ChatGPT × Render").setMessage(message).setPositiveButton("OK",null).show();
            }});
        });
    }
    private void pair(){
        final String origin=relay.getText().toString(),code=enrollment.getText().toString();enrollment.setText("");
        perform(()->{
            if(secrets.load()!=null)throw new IllegalStateException("Revoke the existing connection before pairing another");
            JSONObject answer=AgentHttp.post(origin,"/v1/device/enroll",null,new JSONObject().put("enrollment_code",code).put("name","Render Android"));
            if(!answer.getString("device_id").matches("[a-f0-9]{32}")||!answer.getString("device_token").matches("[A-Za-z0-9_-]{32,256}"))
                throw new IllegalArgumentException("Invalid enrollment response");
            JSONObject saved=new JSONObject().put("device_id",answer.getString("device_id"))
                .put("device_token",answer.getString("device_token")).put("relay",AgentPolicy.relayUrl(origin));
            secrets.save(saved);secrets.enabled(false);secrets.status("Phone paired. ChatGPT authorization and Start are still required.");
            return "Phone paired securely.\n\nChatGPT MCP endpoint:\n"+saved.getString("relay")+"/mcp\n\nTemporary ChatGPT authorization code (10 minutes):\n"+answer.getString("link_code")+
                "\n\nEnter this code only in your relay's authorization page. Then start the session here.";
        });
    }
    private void link(){perform(()->{
        JSONObject c=secrets.load();if(c==null)throw new IllegalStateException("Phone is not paired");
        JSONObject r=AgentHttp.post(c.getString("relay"),"/v1/device/link",c.getString("device_token"),new JSONObject());
        return "New ChatGPT authorization code (10 minutes):\n"+r.getString("link_code")+"\n\nMCP endpoint: "+c.getString("relay")+"/mcp";
    });}
    private void startSession(){
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},42);return;
        }
        try{
            if(secrets.load()==null){secrets.status("Pair this phone first.");return;}
            if(!getSystemService(NotificationManager.class).areNotificationsEnabled()){
                secrets.status("Enable Render notifications so the active connection and Stop control stay visible.");return;
            }
            secrets.enabled(true);secrets.status("Connecting to relay; no command has executed yet.");
            startForegroundService(new Intent(this,AgentService.class));
        }catch(Exception e){secrets.enabled(false);secrets.status("Cannot start session: "+e.getClass().getSimpleName());}
    }
    private void stopSession(){
        secrets.enabled(false);secrets.status("Stopped locally; current native calls stop at the next safe boundary.");
        try{startService(new Intent(this,AgentService.class).setAction(AgentService.STOP));}catch(Exception ignored){}
    }
    private void revoke(){
        stopSession();perform(()->{
            JSONObject c=secrets.load();if(c==null)return "No connection is saved.";
            AgentHttp.post(c.getString("relay"),"/v1/device/revoke",c.getString("device_token"),new JSONObject());
            secrets.clear();secrets.status("Connection revoked. Existing projects were preserved.");
            return "Phone and ChatGPT credentials revoked at the relay. Local credential ciphertext removed.";
        });
    }
    private void localCheck(){perform(()->{
        JSONObject cmd=new JSONObject().put("request_id","local-"+UUID.randomUUID()).put("api_version",1)
            .put("action","engine.status").put("args",new JSONObject());
        return "LOCAL SELF-CHECK ONLY — not a ChatGPT connection test.\n"+
            new AgentActions(this).execute(cmd,new AtomicBoolean(false)).toString(2);
    });}
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);
        if(code==42&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)startSession();
    }
    @Override protected void onDestroy(){ui.removeCallbacksAndMessages(null);background.shutdown();super.onDestroy();}
}
