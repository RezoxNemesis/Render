package com.rezox.render.agent;

import android.Manifest;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationManager;
import android.content.Intent;
import android.content.ClipboardManager;
import android.content.ClipData;
import android.content.pm.PackageInfo;
import android.widget.Toast;
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
    private TextView status,history,bridgeState,workingHand,workingCaption;
    private ObjectAnimator handAnimator;
    private final ExecutorService background=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private boolean busy;
    private final Runnable refresh=new Runnable(){public void run(){
        if(isFinishing()||isDestroyed())return;
        status.setText(secrets.videoStudioBridgeEnabled()?localBridgeStatus():secrets.status());
        if(bridgeState!=null)bridgeState.setText(localBridgeStatus());
        AgentWorkPresence.Snapshot state=AgentWorkPresence.snapshot(AgentActivity.this);
        if(workingCaption!=null)workingCaption.setText(state.description());
        if(workingHand!=null) {
            workingHand.setText(state.isWorking()?"👆":
                    state.needsRecovery()?"⚠":"✋");
            if(state.isWorking() && handAnimator!=null && !handAnimator.isRunning())
                handAnimator.start();
            if(!state.isWorking() && handAnimator!=null && handAnimator.isRunning()){
                handAnimator.cancel();
                workingHand.setTranslationY(0f);
            }
        }
        history.setText(journal.history());ui.postDelayed(this,750);
    }};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        // Explicitly allow owner screenshots and screen recordings.
        // Enrollment remains masked; credentials are in Android Keystore.
        getWindow().clearFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        secrets=new AgentSecrets(this);journal=new AgentJournal(this);
        if(!AgentExecutionLock.BUSY.get())AgentWorkPresence.recoverIfInterrupted(this);
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
        status=StudioUi.text(this,secrets.videoStudioBridgeEnabled()?localBridgeStatus():secrets.status(),15,StudioUi.WHITE,true);
        StudioUi.add(statusPanel,status);
        StudioUi.space(statusPanel,7);
        StudioUi.add(statusPanel,StudioUi.text(this,
            "Direct Render commands use the existing VideoStudio MCP. Pairing to a separate hosted relay is optional.",
            12,0xFFBBAFD4,false));
        StudioUi.add(page,statusPanel);
        StudioUi.space(page,13);
        // This hand moves ONLY while a verified native execution is ongoing.
        // It does not claim to control other Android apps or user tabs.
        LinearLayout workCard=StudioUi.card(this);
        StudioUi.add(workCard,StudioUi.label(this,"LIVE NATIVE ACTIVITY"));
        StudioUi.space(workCard,12);
        LinearLayout handRow=StudioUi.row(this);
        workingHand=StudioUi.text(this,"✋",34,StudioUi.WHITE,true);
        workingHand.setContentDescription("Actual native Blender work indicator");
        handRow.addView(workingHand,new LinearLayout.LayoutParams(
                StudioUi.dp(this,55),StudioUi.dp(this,54)));
        workingCaption=StudioUi.text(this,"No native Blender command is running",
                14,StudioUi.WHITE,true);
        handRow.addView(workingCaption,new LinearLayout.LayoutParams(
                0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        StudioUi.add(workCard,handRow);
        StudioUi.space(workCard,8);
        StudioUi.add(workCard,StudioUi.text(this,
                "The hand and Android notification report Render's own native command journal. GitHub coding and unrelated app taps are not simulated.",
                12,StudioUi.MUTED,false));
        StudioUi.add(page,workCard);
        handAnimator=ObjectAnimator.ofFloat(workingHand,"translationY",0f,
                -StudioUi.dp(this,9));
        handAnimator.setDuration(480);
        handAnimator.setRepeatMode(ValueAnimator.REVERSE);
        handAnimator.setRepeatCount(ValueAnimator.INFINITE);
        StudioUi.space(page,17);

        LinearLayout localBridge=StudioUi.violetCard(this);
        StudioUi.add(localBridge,StudioUi.label(this,"PRIMARY / VIDEOSTUDIO MCP → RENDER"));
        StudioUi.space(localBridge,9);
        StudioUi.add(localBridge,StudioUi.text(this,"Connect & share\nwith ChatGPT.",22,StudioUi.WHITE,true));
        StudioUi.space(localBridge,8);
        StudioUi.add(localBridge,StudioUi.text(this,
            "Connect Render as a separate Blender executor through the SAME VideoStudio MCP. No extra relay, private app key, pairing code or cloud Start Session step. Native Blender work stays on your phone.",
            13,0xFFE2D5FF,false));
        StudioUi.space(localBridge,12);
        bridgeState=StudioUi.text(this,localBridgeStatus(),13,StudioUi.GREEN,true);
        StudioUi.add(localBridge,bridgeState);
        StudioUi.space(localBridge,10);
        StudioUi.add(localBridge,StudioUi.text(this,
            "RENDER APP ID  •  "+secrets.renderPublicId(),11,0xFFB9B0D6,false));
        StudioUi.space(localBridge,16);
        addAction(localBridge,"CONNECT / SHARE WITH CHATGPT    ↗",StudioUi.PRIMARY,
            ()->connectShare());
        StudioUi.space(localBridge,10);
        addAction(localBridge,"SHARE RENDER CONNECTION",StudioUi.PURPLE,
            ()->shareRenderConnection());
        StudioUi.space(localBridge,10);
        addAction(localBridge,"COPY RENDER APP ID",StudioUi.SECONDARY,
            ()->copyRenderAppId());
        StudioUi.space(localBridge,10);
        addAction(localBridge,"CHECK VIDEOSTUDIO APP",StudioUi.SECONDARY,
            ()->checkVideoStudioApp());
        StudioUi.space(localBridge,10);
        addAction(localBridge,"STOP VIDEOSTUDIO BRIDGE",StudioUi.DANGER,
            ()->disableDirectBridge());
        StudioUi.add(page,localBridge);
        StudioUi.space(page,14);
        LinearLayout cloudBackup=StudioUi.card(this);
        StudioUi.add(cloudBackup,StudioUi.label(this,"OPTIONAL / GOOGLE DRIVE BACKUP"));
        StudioUi.space(cloudBackup,7);
        StudioUi.add(cloudBackup,StudioUi.text(this,
            "Choose a folder in Google Drive (if its Android document provider supports folders), or another document provider. Blender still renders on this phone. Saved .blend, PNG and MP4 files can be copied to the chosen location without Gallery access.",
            12,StudioUi.MUTED,false));
        StudioUi.space(cloudBackup,10);
        addAction(cloudBackup,"CHOOSE BACKUP FOLDER",StudioUi.SECONDARY,()->{
            try{ProductionDriveStorage.chooseFolder(this);}
            catch(Exception e){Toast.makeText(this,"Folder picker unavailable: "+e.getClass().getSimpleName(),Toast.LENGTH_LONG).show();}
        });
        StudioUi.add(page,cloudBackup);
        LinearLayout referenceCard=StudioUi.card(this);
        StudioUi.add(referenceCard,StudioUi.label(this,"REFERENCE IMAGE / VIDEO INBOX"));
        StudioUi.add(referenceCard,StudioUi.text(this,
            "Import only photos or videos you choose. Render checks the real file bytes and saves a private checksum. It never browses Gallery or guesses the unseen side of a character.",
            12,StudioUi.MUTED,false));
        addAction(referenceCard,"IMPORT PHOTOS / VIDEOS INTO RENDER",StudioUi.SECONDARY,()->{
            try{StudioReferenceInbox.openPicker(this);}
            catch(Exception e){Toast.makeText(this,"Reference picker unavailable: "+e.getClass().getSimpleName(),Toast.LENGTH_LONG).show();}
        });
        StudioUi.add(page,referenceCard);
        StudioUi.space(page,17);

        // Keep legacy cloud modes supported but do not confuse them with
        // the recommended single, direct VideoStudio MCP connection.
        LinearLayout advanced=StudioUi.column(this);
        advanced.setVisibility(View.GONE);
        TextView advancedToggle=StudioUi.action(this,
            "OPTIONAL CLOUD PAIRING / ADVANCED     ▾",StudioUi.SECONDARY);
        StudioUi.add(page,advancedToggle);
        StudioUi.space(page,8);
        StudioUi.add(page,advanced);
        advancedToggle.setOnClickListener(v->{
            boolean expand=advanced.getVisibility()!=View.VISIBLE;
            advanced.setVisibility(expand?View.VISIBLE:View.GONE);
            advancedToggle.setText(expand?"HIDE ADVANCED CLOUD OPTIONS     ▴":
                "OPTIONAL CLOUD PAIRING / ADVANCED     ▾");
        });
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
        StudioUi.add(advanced,shared);
        StudioUi.space(advanced,17);

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
        StudioUi.add(advanced,pairPanel);
        StudioUi.space(advanced,16);

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
        StudioUi.add(advanced,sessionPanel);
        StudioUi.space(advanced,16);

        LinearLayout utility=StudioUi.card(this);
        StudioUi.add(utility,StudioUi.label(this,"03   /   LOCAL DIAGNOSTICS"));
        StudioUi.space(utility,12);
        addAction(utility,"CHECK AGENT LOCALLY",StudioUi.SECONDARY,()->localCheck());
        StudioUi.space(utility,10);
        addAction(utility,"OPEN BLENDER TO RESUME NATIVE JOBS",StudioUi.PRIMARY,()->{
            try {
                startActivity(new Intent().setClassName(this,
                        "com.rezox.render.EditorLaunchActivity"));
            }catch(android.content.ActivityNotFoundException unavailable){
                secrets.status("Full native Blender editor is not installed in this APK.");
            }
        });
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
        if(StudioReferenceInbox.isExplicitOwnerMediaIntent(getIntent()))
            confirmSharedReference(getIntent());
        else if(getIntent()!=null&&"com.rezox.render.agent.PICK_MEDIA".equals(getIntent().getAction())){
            setIntent(new Intent(this,AgentActivity.class));
            StudioReferenceInbox.openPicker(this);
        }
    }
    private void confirmSharedReference(Intent inbound){
        if(inbound==null || !StudioReferenceInbox.isExplicitOwnerMediaIntent(inbound))return;
        new AlertDialog.Builder(this)
            .setTitle("Import these images/videos into Render?")
            .setMessage("Only the files explicitly selected or shared with Render are copied into its private reference inbox. No Gallery browsing occurs.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Import",(dialog,which)->receiveReferenceIntent(inbound))
            .show();
    }
    private void receiveReferenceIntent(Intent inbound){
        if(inbound==null||!StudioReferenceInbox.isExplicitOwnerMediaIntent(inbound))return;
        // Permission-limited source URIs are used only for this owner-selected copy.
        setIntent(new Intent(this,AgentActivity.class));
        background.execute(()->{
            try{
                JSONObject receipt=StudioReferenceInbox.receive(getApplicationContext(),inbound);
                int count=receipt.getInt("imported");
                ui.post(()->Toast.makeText(this,"Imported "+count+" reference(s); inspect reference.list through your existing Render bridge.",Toast.LENGTH_LONG).show());
            }catch(Exception e){
                ui.post(()->Toast.makeText(this,"Reference import failed: "+e.getMessage(),Toast.LENGTH_LONG).show());
            }
        });
    }
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);
        if(StudioReferenceInbox.isExplicitOwnerMediaIntent(intent))
            confirmSharedReference(intent);
    }
    private void addAction(LinearLayout parent,String title,int style,Runnable action) {
        TextView view=StudioUi.action(this,title,style);
        StudioUi.add(parent,view);
        view.setOnClickListener(v->action.run());
    }
    private long installedVideoStudioBuild(){
        try {
            PackageInfo info;
            if(Build.VERSION.SDK_INT>=33)
                info=getPackageManager().getPackageInfo(
                    RenderConnectionCard.VIDEOSTUDIO_PACKAGE,
                    PackageManager.PackageInfoFlags.of(0));
            else
                info=getPackageManager().getPackageInfo(
                    RenderConnectionCard.VIDEOSTUDIO_PACKAGE,0);
            return info.getLongVersionCode();
        }catch(PackageManager.NameNotFoundException ignored){return -1;}
        catch(RuntimeException ignored){return -1;}
    }
    private String localBridgeStatus(){
        return RenderConnectionCard.localStatus(
            secrets.renderPublicId(),secrets.videoStudioBridgeEnabled(),
            installedVideoStudioBuild(),secrets.lastVideoStudioNativeResult());
    }
    private void connectShare(){
        long installed=installedVideoStudioBuild();
        if(installed<RenderConnectionCard.MIN_VIDEOSTUDIO_BUILD){
            new AlertDialog.Builder(this)
                .setTitle("Updated VideoStudio required")
                .setMessage("The compatible VideoStudio v3.5.4+ Android app is not visible on this phone. Install the updated VideoStudio APK without deleting its app data. Then return here. You can share the Render setup card meanwhile.")
                .setNegativeButton("Close",null)
                .setPositiveButton("Share setup",(d,w)->shareRenderConnection()).show();
            return;
        }
        new AlertDialog.Builder(this)
            .setTitle("Connect Render through VideoStudio MCP?")
            .setMessage("Use the existing ChatGPT↔VideoStudio MCP connection to forward only registered Render Blender commands. VideoStudio keeps its own projects, Render performs 3D work locally, and you can stop this bridge at any time. The shared card contains a NON-SECRET Render ID.")
            .setNegativeButton("Cancel",null)
            .setNeutralButton("Enable only",(d,w)->activateDirectBridge())
            .setPositiveButton("Enable & Share",(d,w)->{
                activateDirectBridge();
                shareRenderConnection();
            }).show();
    }
    private void activateDirectBridge(){
        secrets.videoStudioBridgeEnabled(true);
        secrets.status("Local Render bridge enabled. Awaiting a confirmed native command via existing VideoStudio MCP.");
        if(bridgeState!=null)bridgeState.setText(localBridgeStatus());
        // Direct Binder jobs need notification permission too; never block a
        // modelling job because the user declines the optional notification.
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(
                Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},44);
    }
    private void shareRenderConnection(){
        String card=RenderConnectionCard.shareText(secrets.renderPublicId(),
            secrets.videoStudioBridgeEnabled(),
            installedVideoStudioBuild()>=RenderConnectionCard.MIN_VIDEOSTUDIO_BUILD,getPackageName());
        Intent send=new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT,card);
        try{
            startActivity(Intent.createChooser(send,"Share Render connection with ChatGPT"));
        }catch(android.content.ActivityNotFoundException ignored){
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            clipboard.setPrimaryClip(ClipData.newPlainText("Render Studio connection",card));
            Toast.makeText(this,"Render connection card copied",Toast.LENGTH_LONG).show();
        }
    }
    private void copyRenderAppId(){
        ClipboardManager clipboard=getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText(
            "Render Studio public app ID",secrets.renderPublicId()));
        Toast.makeText(this,"Public Render app ID copied",Toast.LENGTH_SHORT).show();
    }
    private void checkVideoStudioApp(){
        long version=installedVideoStudioBuild();
        String result=version<0 ? "VideoStudio is not installed or is hidden by Android package visibility." :
            "VideoStudio installed (build "+version+").\n"+
            (version>=RenderConnectionCard.MIN_VIDEOSTUDIO_BUILD
            ?"Compatible with the current native Binder bridge."
            :"Update VideoStudio to build 354 or newer.");
        new AlertDialog.Builder(this)
            .setTitle("Render ↔ VideoStudio")
            .setMessage(result+"\n\n"+localBridgeStatus()
                +"\n\nA compatible installation and enabled bridge are not proof of a real ChatGPT command. Verify through the existing VideoStudio MCP using render.engine.status.")
            .setPositiveButton("OK",null).show();
    }
    private void disableDirectBridge(){
        secrets.videoStudioBridgeEnabled(false);
        VideoStudioNativeBridgeService.requestCancel();
        secrets.status("Render's local bridge stopped. The original VideoStudio MCP and projects remain unchanged.");
        if(bridgeState!=null)bridgeState.setText(localBridgeStatus());
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
            JSONObject credentials=VideoStudioMcpTransport.pair(this,oneTimeCode);
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
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==StudioReferenceInbox.PICK_REFERENCE && resultCode==Activity.RESULT_OK){
            Intent ownerSelected=new Intent(Intent.ACTION_OPEN_DOCUMENT);
            if(data!=null){
                ownerSelected.setData(data.getData());
                ownerSelected.setClipData(data.getClipData());
            }
            ownerSelected.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            receiveReferenceIntent(ownerSelected);
        }
        if(requestCode==ProductionDriveStorage.REQUEST_PICK_FOLDER){
            try{
                boolean selected=ProductionDriveStorage.acceptFolderSelection(this,resultCode,data);
                Toast.makeText(this,selected?
                    "Backup folder linked; Render can copy verified files to this provider.":
                    "No backup folder selected.",Toast.LENGTH_LONG).show();
            }catch(Exception e){
                Toast.makeText(this,"Backup folder permission failed: "+e.getClass().getSimpleName(),Toast.LENGTH_LONG).show();
            }
        }
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);
        if(code==42&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)startSession();
    }
    @Override protected void onDestroy(){
        ui.removeCallbacksAndMessages(null);
        if(handAnimator!=null)handAnimator.cancel();
        background.shutdown();
        super.onDestroy();
    }
}
