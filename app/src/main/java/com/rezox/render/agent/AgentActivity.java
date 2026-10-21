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
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import com.rezox.render.ui.StudioUi;
import android.view.ViewGroup;
import android.view.Gravity;
import org.json.JSONObject;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.atomic.AtomicBoolean;

/** Owner-visible pairing, opt-in native execution, activity history, Stop and Revoke. */
public final class AgentActivity extends Activity {
    private AgentSecrets secrets;
    private AgentJournal journal;
    private EditText relay,enrollment,videoStudioPairCode;
    private TextView status,history;
    private final ExecutorService background=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private boolean busy;
    private final Runnable refresh=new Runnable(){public void run(){
        if(isFinishing()||isDestroyed())return;
        status.setText(secrets.status());history.setText(journal.history());ui.postDelayed(this,2000);
    }};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        // Explicitly allow owner screenshots and screen recordings.
        // Enrollment remains masked; credentials are in Android Keystore.
        getWindow().clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        secrets=new AgentSecrets(this);journal=new AgentJournal(this);
        LinearLayout page=StudioUi.page(this);

        LinearLayout header=StudioUi.row(this);
        TextView back=StudioUi.action(this,"←",StudioUi.SECONDARY);
        back.setMinWidth(StudioUi.dp(this,52));
        header.addView(back,new LinearLayout.LayoutParams(StudioUi.dp(this,52),StudioUi.dp(this,50)));
        back.setOnClickListener(v->finish());
        LinearLayout heading=StudioUi.column(this);
        heading.setPadding(StudioUi.dp(this,14),0,0,0);
        StudioUi.add(heading,StudioUi.label(this,"RENDER  /  AGENT CONSOLE"));
        StudioUi.add(heading,StudioUi.text(this,"Connection Control",17,StudioUi.WHITE,true));
        header.addView(heading,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        StudioUi.add(page,header);
        StudioUi.space(page,28);
        StudioUi.add(page,StudioUi.chip(this,"◉  NATIVE EXECUTION",StudioUi.VIOLET));
        StudioUi.space(page,12);
        StudioUi.add(page,StudioUi.text(this,"ChatGPT ×\nRender",34,StudioUi.WHITE,true));
        StudioUi.space(page,10);
        StudioUi.add(page,StudioUi.text(this,
            "Give commands from ChatGPT. Render executes its registered native operations on this Android device.",
            14,StudioUi.MUTED,false));
        StudioUi.space(page,20);

        LinearLayout statusPanel=StudioUi.violetCard(this);
        StudioUi.add(statusPanel,StudioUi.label(this,"CONNECTION STATUS"));
        StudioUi.space(statusPanel,9);
        status=StudioUi.text(this,secrets.status(),15,StudioUi.WHITE,true);
        StudioUi.add(statusPanel,status);
        StudioUi.space(statusPanel,7);
        StudioUi.add(statusPanel,StudioUi.text(this,
            "Pairing and HTTPS relay authentication are required before remote commands can arrive.",
            12,0xFFBBAFD4,false));
        StudioUi.add(page,statusPanel);
        StudioUi.space(page,17);

        LinearLayout localBridge=StudioUi.card(this);
        StudioUi.add(localBridge,StudioUi.label(this,"DIRECT  /  VIDEOSTUDIO APP-TO-APP MCP"));
        StudioUi.space(localBridge,9);
        StudioUi.add(localBridge,StudioUi.text(this,"No new relay.\nNo new pairing code.",20,StudioUi.WHITE,true));
        StudioUi.space(localBridge,7);
        StudioUi.add(localBridge,StudioUi.text(this,
            "Use your existing VideoStudio Native Agent as a trusted on-phone bridge. Only the installed VideoStudio app can deliver typed commands to Render, and Blender still runs here. Both apps need the updated APKs.",
            13,StudioUi.MUTED,false));
        StudioUi.space(localBridge,13);
        addAction(localBridge,"ENABLE DIRECT VIDEOSTUDIO BRIDGE",StudioUi.PRIMARY,()->enableDirectBridge());
        StudioUi.space(localBridge,10);
        addAction(localBridge,"STOP DIRECT BRIDGE",StudioUi.SECONDARY,()->disableDirectBridge());
        StudioUi.add(page,localBridge);
        StudioUi.space(page,17);

        LinearLayout shared=StudioUi.violetCard(this);
        StudioUi.add(shared,StudioUi.label(this,"PREFERRED / EXISTING VIDEOSTUDIO MCP"));
        StudioUi.space(shared,10);
        StudioUi.add(shared,StudioUi.text(this,"One connection.\nTwo native studios.",22,StudioUi.WHITE,true));
        StudioUi.space(shared,8);
        StudioUi.add(shared,StudioUi.text(this,
            "Ask ChatGPT through the existing VideoStudio MCP for a one-time Render pairing code. Enter the code here; VideoStudio's private owner key never leaves its original connection.",
            13,0xFFE2D5FF,false));
        StudioUi.space(shared,13);
        videoStudioPairCode=StudioUi.field(this,"One-time Render pairing code (10 minutes)",true);
        StudioUi.add(shared,videoStudioPairCode);
        StudioUi.space(shared,12);
        addAction(shared,"PAIR VIA VIDEOSTUDIO MCP",StudioUi.PURPLE,()->pairWithVideoStudio());
        StudioUi.space(shared,10);
        addAction(shared,"CHECK VIDEOSTUDIO MCP WORKER",StudioUi.SECONDARY,()->verifyExistingMcp());
        StudioUi.add(page,shared);
        StudioUi.space(page,17);

        LinearLayout pairPanel=StudioUi.card(this);
        StudioUi.add(pairPanel,StudioUi.label(this,"OPTIONAL / OLD INDEPENDENT RELAY"));
        StudioUi.space(pairPanel,8);
        StudioUi.add(pairPanel,StudioUi.text(this,"Connect your phone",21,StudioUi.WHITE,true));
        StudioUi.space(pairPanel,7);
        StudioUi.add(pairPanel,StudioUi.text(this,
            "Optional older method. The existing VideoStudio MCP above needs no new server or ChatGPT connector.",
            13,StudioUi.MUTED,false));
        StudioUi.space(pairPanel,14);
        relay=StudioUi.field(this,"Relay origin  ·  https://…",false);
        StudioUi.add(pairPanel,relay);
        StudioUi.space(pairPanel,10);
        enrollment=StudioUi.field(this,"One-use enrollment code",true);
        StudioUi.add(pairPanel,enrollment);
        try{JSONObject c=secrets.load();if(c!=null)relay.setText(c.optString("relay"));}catch(Exception ignored){}
        StudioUi.space(pairPanel,13);
        addAction(pairPanel,"PAIR THIS DEVICE     →",StudioUi.PURPLE,()->pair());
        StudioUi.space(pairPanel,10);
        addAction(pairPanel,"CHECK RELAY REACHABILITY",StudioUi.SECONDARY,()->testRelay());
        StudioUi.space(pairPanel,10);
        addAction(pairPanel,"GENERATE CHATGPT LINK CODE",StudioUi.SECONDARY,()->link());
        StudioUi.add(page,pairPanel);
        StudioUi.space(page,16);

        LinearLayout sessionPanel=StudioUi.card(this);
        StudioUi.add(sessionPanel,StudioUi.label(this,"02   /   AUTONOMOUS SESSION"));
        StudioUi.space(sessionPanel,8);
        StudioUi.add(sessionPanel,StudioUi.text(this,"Execution control",21,StudioUi.WHITE,true));
        StudioUi.space(sessionPanel,8);
        StudioUi.add(sessionPanel,StudioUi.text(this,
            "Start only after pairing. Every native command is logged and can be stopped from this screen or the Android notification.",
            13,StudioUi.MUTED,false));
        StudioUi.space(sessionPanel,15);
        addAction(sessionPanel,"START AGENT SESSION",StudioUi.PRIMARY,()->startSession());
        StudioUi.space(sessionPanel,10);
        addAction(sessionPanel,"STOP NATIVE COMMANDS",StudioUi.SECONDARY,()->stopSession());
        StudioUi.space(sessionPanel,10);
        addAction(sessionPanel,"REVOKE CONNECTION",StudioUi.DANGER,()->
            new AlertDialog.Builder(this)
                .setTitle("Revoke remote control?")
                .setMessage("This stops commands and revokes the phone's relay credential. Imported projects are preserved.")
                .setNegativeButton("Keep",null)
                .setPositiveButton("Revoke",(d,w)->revoke()).show());
        StudioUi.add(page,sessionPanel);
        StudioUi.space(page,16);

        LinearLayout utility=StudioUi.card(this);
        StudioUi.add(utility,StudioUi.label(this,"03   /   LOCAL DIAGNOSTICS"));
        StudioUi.space(utility,12);
        addAction(utility,"CHECK AGENT LOCALLY",StudioUi.SECONDARY,()->localCheck());
        StudioUi.space(utility,10);
        addAction(utility,"OPEN PROJECT INSPECTOR",StudioUi.SECONDARY,
            ()->startActivity(new Intent(this,com.rezox.render.MainActivity.class)));
        StudioUi.add(page,utility);
        StudioUi.space(page,16);

        LinearLayout logs=StudioUi.card(this);
        StudioUi.add(logs,StudioUi.label(this,"LAST 20 NATIVE COMMANDS"));
        StudioUi.space(logs,10);
        history=StudioUi.text(this,journal.history(),13,StudioUi.MUTED,false);
        StudioUi.add(logs,history);
        StudioUi.add(page,logs);
        StudioUi.space(page,18);
        StudioUi.add(page,StudioUi.text(this,
            "SCREEN CAPTURE ENABLED  •  Secret fields remain masked. This connection never uses cloud Blender rendering. Device and permission limitations still apply.",
            11,StudioUi.MUTED,false));
        ui.post(refresh);
    }
    private void addAction(LinearLayout parent,String title,int style,Runnable action) {
        TextView view=StudioUi.action(this,title,style);
        StudioUi.add(parent,view);
        view.setOnClickListener(v->action.run());
    }
    private void enableDirectBridge(){
        new AlertDialog.Builder(this)
            .setTitle("Enable VideoStudio native access?")
            .setMessage("Only the installed VideoStudio Android application can send typed Render commands using Android Binder caller verification. VideoStudio keeps its original MCP connection and projects. Render performs all Blender work locally. You can stop this link any time.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Enable",(dialog,which)->{
                secrets.videoStudioBridgeEnabled(true);
                secrets.status("Direct VideoStudio MCP bridge enabled. Awaiting commands from the installed VideoStudio Native Agent.");
            }).show();
    }
    private void disableDirectBridge(){
        secrets.videoStudioBridgeEnabled(false);
        VideoStudioNativeBridgeService.requestCancel();
        secrets.status("Direct VideoStudio native command access stopped. VideoStudio's own projects and MCP remain untouched.");
    }
    private void pairWithVideoStudio(){
        final String oneTimeCode=videoStudioPairCode.getText().toString().trim();
        videoStudioPairCode.setText(""); // Do not retain a reusable code in the UI.
        if(oneTimeCode.isEmpty()){
            new AlertDialog.Builder(this).setTitle("One-time code required")
                .setMessage("Ask ChatGPT to get the new Render pairing code using your existing VideoStudio MCP. Enter that short-lived code here. Do not copy your private VideoStudio owner link.")
                .setPositiveButton("OK",null).show();
            return;
        }
        perform(()->{
            if(secrets.load()!=null)
                throw new IllegalStateException("Revoke the previous Render pairing before changing transport. VideoStudio stays connected.");
            JSONObject credentials=VideoStudioMcpTransport.pair(oneTimeCode);
            secrets.save(credentials);
            secrets.enabled(false);
            secrets.status("Render paired to existing VideoStudio MCP. Start the native agent session.");
            return "Render uses your existing VideoStudio MCP! No second ChatGPT connection or extra relay is needed. Start Agent Session on this phone to accept native Blender commands.";
        });
    }
    private void verifyExistingMcp(){
        perform(()->{
            JSONObject check=VideoStudioMcpTransport.checkSharedWorker();
            return "Existing VideoStudio MCP Worker reachable: "+check.optString("service")
                +"\nThe phone still needs one-time pairing and Start Agent Session.";
        });
    }
    private void testRelay(){
        String requested=relay.getText().toString().trim();
        perform(()->{
            if(requested.isEmpty())
                return "No relay address has been entered. Paste the HTTPS URL of your private hosted Render relay here, then run this check.";
            JSONObject health=AgentHttp.checkHealth(requested);
            return "RELAY REACHABLE\n"+health.optString("service","Unknown server")
                + "\n\nThis verifies HTTPS connectivity only. It does not mean the device is paired or ChatGPT can send commands.";
        });
    }
    private interface Task{String run()throws Exception;}
    private void perform(Task task){
        if(busy){secrets.status("A setup request is already running.");return;}busy=true;
        background.execute(()->{
            String answer;try{answer=task.run();}catch(Exception e){answer=explainFailure(e);}
            final String message=answer;ui.post(()->{busy=false;if(!isFinishing()&&!isDestroyed()){
                new AlertDialog.Builder(this).setTitle("ChatGPT × Render").setMessage(message).setPositiveButton("OK",null).show();
            }});
        });
    }
    /** Report actionable setup failures without exposing credentials or server URLs in error text. */
    private String explainFailure(Exception e) {
        if(e instanceof IllegalArgumentException || e instanceof IllegalStateException){
            String code=e.getMessage();
            if(code!=null && code.matches("[A-Za-z0-9 .:/()_-]{1,200}"))return code;
            return "Incorrect connection input. Check the HTTPS relay address and one-use code.";
        }
        if(e instanceof AgentHttp.RelayException){
            int status=((AgentHttp.RelayException)e).status;
            if(status==404)return "Render channel not deployed on the existing VideoStudio MCP Worker yet. The Worker needs its additive Render update.";
            if(status==403)return "Pairing code invalid, expired, already used or not authorized by VideoStudio.";
            if(status==409)return "This relay has already enrolled a phone. Generate a fresh authorized setup before retrying.";
            if(status==401)return "Authorization failed or expired. Pair with a fresh one-use enrollment code.";
            if(status==429)return "Too many attempts. Wait briefly before trying again.";
            if(status>=500)return "The relay is having a server problem. Try Check Relay Reachability in a minute.";
            return "The relay rejected the setup request (HTTP "+status+"). Check the setup details.";
        }
        if(e instanceof java.net.UnknownHostException)return "Cannot find the relay address. Check the URL and your internet connection.";
        if(e instanceof java.net.SocketTimeoutException)return "The relay did not respond in time. A free hosting service may be starting up; try again.";
        if(e instanceof javax.net.ssl.SSLException)return "Secure HTTPS verification failed. Check the relay URL; plain HTTP is not supported.";
        if(e instanceof java.io.IOException)return "Cannot reach the relay. Check its URL, your network, or the server status.";
        return "Connection setup failed ("+e.getClass().getSimpleName()+"). No private credential was displayed.";
    }
    private void pair(){
        final String origin=relay.getText().toString().trim(),code=enrollment.getText().toString().trim();
        enrollment.setText("");
        if(origin.isEmpty()){secrets.status("Relay URL missing. Deploy the private relay first, then paste its HTTPS address.");
            new AlertDialog.Builder(this).setTitle("Relay address needed")
                .setMessage("The relay address field is empty. This is a real HTTPS service URL, not your GitHub repository or ChatGPT account. Once deployed, paste the exact URL here.")
                .setPositiveButton("OK",null).show();return;}
        if(code.isEmpty()){secrets.status("One-use enrollment code missing.");
            new AlertDialog.Builder(this).setTitle("Enrollment code needed")
                .setMessage("The one-use enrollment code has not been entered. It is issued when your relay is configured. A ChatGPT password, API key or random code will not work.")
                .setPositiveButton("OK",null).show();return;}
        perform(()->{
            AgentPolicy.relayUrl(origin);
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
        JSONObject c=secrets.load();if(c==null)throw new IllegalStateException("Pair Render first using the VideoStudio MCP one-time code.");
        if(VideoStudioMcpTransport.isSelected(c))return "Render uses your existing VideoStudio MCP. No new ChatGPT link code or connector is needed.";
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
            secrets.enabled(true);
            secrets.status(VideoStudioMcpTransport.isSelected(secrets.load())
                ?"Connecting through VideoStudio MCP. No Blender operation has executed yet."
                :"Connecting to standalone relay. No command has executed yet.");
            startForegroundService(new Intent(this,AgentService.class));
        }catch(Exception e){secrets.enabled(false);secrets.status("Cannot start session: "+e.getClass().getSimpleName());}
    }
    private void stopSession(){
        disableDirectBridge();
        secrets.enabled(false);secrets.status("Stopped locally; current native calls stop at the next safe boundary.");
        try{startService(new Intent(this,AgentService.class).setAction(AgentService.STOP));}catch(Exception ignored){}
    }
    private void revoke(){
        stopSession();perform(()->{
            JSONObject c=secrets.load();if(c==null)return "No connection is saved.";
            if(VideoStudioMcpTransport.isSelected(c))VideoStudioMcpTransport.unlink(c);
            else AgentHttp.post(c.getString("relay"),"/v1/device/revoke",c.getString("device_token"),new JSONObject());
            secrets.clear();secrets.status("Connection revoked. Existing projects were preserved.");
            return "Render pairing was revoked. The original VideoStudio MCP connection and projects are preserved.";
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
