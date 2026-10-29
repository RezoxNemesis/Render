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
    private EditText enrollment;
    private TextView status,history,workingHand,workingCaption;
    private ObjectAnimator handAnimator;
    private final ExecutorService background=Executors.newSingleThreadExecutor();
    private final Handler ui=new Handler(Looper.getMainLooper());
    private boolean busy;
    private final Runnable refresh=new Runnable(){public void run(){
        if(isFinishing()||isDestroyed())return;
        status.setText(secrets.status());
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
        status=StudioUi.text(this,secrets.status(),15,StudioUi.WHITE,true);
        StudioUi.add(statusPanel,status);
        StudioUi.space(statusPanel,7);
        StudioUi.add(statusPanel,StudioUi.text(this,
            "This app uses only your dedicated Render Studio HTTPS MCP. Blender actions run natively on this phone.",
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

        LinearLayout identity=StudioUi.violetCard(this);
        StudioUi.add(identity,StudioUi.label(this,"01 / DIRECT RENDER STUDIO MCP"));
        StudioUi.space(identity,8);
        StudioUi.add(identity,StudioUi.text(this,"One studio. One native connection.",22,StudioUi.WHITE,true));
        StudioUi.space(identity,9);
        StudioUi.add(identity,StudioUi.text(this,
            "Dedicated MCP over HTTPS. No VideoStudio app, Binder carrier or shared owner credential.",
            13,StudioUi.MUTED,false));
        StudioUi.space(identity,11);
        StudioUi.add(identity,StudioUi.text(this,
            "PUBLIC RENDER ID  •  "+secrets.renderPublicId(),11,0xFFB9B0D6,false));
        StudioUi.space(identity,12);
        addAction(identity,"SHARE RENDER MCP DETAILS",StudioUi.PURPLE,()->shareRenderConnection());
        addAction(identity,"COPY PUBLIC RENDER ID",StudioUi.SECONDARY,()->copyRenderAppId());
        StudioUi.add(page,identity);
        StudioUi.space(page,14);
        LinearLayout cloudBackup=StudioUi.card(this);
        StudioUi.add(cloudBackup,StudioUi.label(this,"PROJECT FOLDERS / FILE TRANSFERS"));
        StudioUi.space(cloudBackup,7);
        StudioUi.add(cloudBackup,StudioUi.text(this,
            "Choose a working folder in device storage or Google Drive, when its Android provider supports folders. ChatGPT can create subfolders, import original files and export verified project copies through your existing Render connection. Transfers and native Blender imports report separately. No Gallery access.",
            12,StudioUi.MUTED,false));
        StudioUi.space(cloudBackup,10);
        addAction(cloudBackup,"CHOOSE WORKING / BACKUP FOLDER",StudioUi.SECONDARY,()->{
            try{ProductionDriveStorage.chooseFolder(this);}
            catch(Exception e){Toast.makeText(this,"Folder picker unavailable: "+e.getClass().getSimpleName(),Toast.LENGTH_LONG).show();}
        });
        addAction(cloudBackup,"FILE TRANSFERS / PAUSE / RESUME / CANCEL",StudioUi.SECONDARY,()->showFileTransfers());
        addAction(cloudBackup,"CHOOSE MODEL / IMAGE / VIDEO FILE",StudioUi.SECONDARY,()->StorageDocuments.pickFile(this));
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

        // The direct Render Studio MCP is the sole connection mode.
        LinearLayout advanced=page;
        LinearLayout pairPanel=StudioUi.card(this);
        StudioUi.add(pairPanel,StudioUi.label(this,"02 / PAIR RENDER STUDIO"));
        StudioUi.space(pairPanel,8);
        StudioUi.add(pairPanel,StudioUi.text(this,"Connect this Android device",21,StudioUi.WHITE,true));
        StudioUi.space(pairPanel,8);
        StudioUi.add(pairPanel,StudioUi.text(this,
            "Dedicated endpoint: "+RenderDirectMcp.MCP_ENDPOINT,
            12,StudioUi.MUTED,false));
        StudioUi.space(pairPanel,7);
        StudioUi.add(pairPanel,StudioUi.text(this,
            "Enter a one-use enrollment code from your existing Render Studio Cloudflare Worker. After pairing, authorize ChatGPT using the generated link code.",
            13,StudioUi.MUTED,false));
        try {
            if(RenderDirectMcp.isLegacyPairing(secrets.load())){
                StudioUi.add(pairPanel,StudioUi.text(this,
                    "Legacy VideoStudio pairing detected. It cannot run in this version. A successful direct pairing will replace only that stored credential; projects and native files remain.",
                    13,StudioUi.WHITE,true));
            }
        }catch(Exception ignored){}
        StudioUi.space(pairPanel,12);
        enrollment=StudioUi.field(this,"One-use Render Studio enrollment code",true);
        StudioUi.add(pairPanel,enrollment);
        StudioUi.space(pairPanel,10);
        addAction(pairPanel,"PAIR THIS DEVICE",StudioUi.PRIMARY,()->pair());
        StudioUi.space(pairPanel,10);
        addAction(pairPanel,"CHECK DIRECT MCP REACHABILITY",StudioUi.SECONDARY,()->testRelay());
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
        else if(getIntent()!=null&&"com.rezox.render.agent.PICK_STORAGE".equals(getIntent().getAction())){
            setIntent(new Intent(this,AgentActivity.class));ProductionDriveStorage.chooseFolder(this);
        }
        else if(getIntent()!=null&&"com.rezox.render.agent.PICK_FILE".equals(getIntent().getAction())){
            setIntent(new Intent(this,AgentActivity.class));StorageDocuments.pickFile(this);
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
                ui.post(()->Toast.makeText(this,"Imported "+count+" reference(s); inspect reference.list through the dedicated Render MCP.",Toast.LENGTH_LONG).show());
            }catch(Exception e){
                ui.post(()->Toast.makeText(this,"Reference import failed: "+e.getMessage(),Toast.LENGTH_LONG).show());
            }
        });
    }
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);
        if(StudioReferenceInbox.isExplicitOwnerMediaIntent(intent))
            confirmSharedReference(intent);
        else if("com.rezox.render.agent.PICK_STORAGE".equals(intent.getAction()))ProductionDriveStorage.chooseFolder(this);
        else if("com.rezox.render.agent.PICK_MEDIA".equals(intent.getAction()))StudioReferenceInbox.openPicker(this);
        else if("com.rezox.render.agent.PICK_FILE".equals(intent.getAction()))StorageDocuments.pickFile(this);
    }
    private void showFileTransfers(){
        perform(()->{
            org.json.JSONArray rows=FileTransfers.list(this).getJSONArray("transfers");
            if(rows.length()==0)return "No file transfers yet. Ask ChatGPT to inspect storage.capabilities through your existing Render connection.";
            String[] labels=new String[rows.length()];
            for(int i=0;i<rows.length();i++){
                JSONObject row=rows.getJSONObject(i);
                labels[i]=transferTitle(row)+" · "+transferState(row);
            }
            ui.post(()->new AlertDialog.Builder(this).setTitle("File transfers")
                .setItems(labels,(dialog,index)->{
                    try{
                        JSONObject row=rows.getJSONObject(index);String id=row.getString("transfer_id");
                        new AlertDialog.Builder(this).setTitle(transferTitle(row))
                            .setMessage(transferSummary(row))
                            .setNeutralButton("Pause",(d,w)->perform(()->transferSummary(FileTransfers.control(this,id,"pause"))))
                            .setNegativeButton("Cancel transfer",(d,w)->perform(()->transferSummary(FileTransfers.control(this,id,"cancel"))))
                            .setPositiveButton("Resume",(d,w)->perform(()->{
                                FileTransfers.control(this,id,"resume");return transferSummary(FileTransferService.request(this,id));
                            })).show();
                    }catch(Exception e){Toast.makeText(this,"Transfer unavailable",Toast.LENGTH_LONG).show();}
                }).setNegativeButton("Close",null).show());
            return "File transfers report copied bytes separately from native Blender imports. Failed or interrupted transfers require an explicit Resume.";
        });
    }
    private String transferTitle(JSONObject row){
        String name=row.optString("display_name","");
        if(!name.isEmpty())return name;
        switch(row.optString("kind")){
            case "import":return "Import original file";
            case "export":return "Export project or output";
            case "fetch":return "Download original file";
            case "unpack":return "Extract asset dependencies";
            default:return "File transfer";
        }
    }
    private String transferState(JSONObject row){return row.optString("state","unknown").replace('_',' ');}
    private String transferSummary(JSONObject row){
        if(row.optBoolean("cancelled"))return "No file selected.";
        long done=row.optLong("bytes_transferred",0),total=row.optLong("total_bytes",-1);
        String text=transferState(row)+"\n"+android.text.format.Formatter.formatShortFileSize(this,done);
        if(total>=0)text+=" / "+android.text.format.Formatter.formatShortFileSize(this,total);
        JSONObject result=row.optJSONObject("result");
        if(result!=null){
            if(result.optBoolean("provider_readback_sha256_verified"))text+="\nVerified copy saved. The original project is retained.";
            if(result.optBoolean("original_bytes_preserved"))text+="\nOriginal bytes saved for native Blender import.";
        }
        if(row.has("error_hint"))text+="\n\n"+row.optString("error_hint").replace("Use storage.task.refresh on this transfer","Ask ChatGPT to refresh this transfer");
        if(row.optBoolean("requires_owner_open"))text+="\nOpen Render and explicitly Resume when Android permits.";
        return text;
    }
    private void addAction(LinearLayout parent,String title,int style,Runnable action) {
        TextView view=StudioUi.action(this,title,style);
        StudioUi.add(parent,view);
        view.setOnClickListener(v->action.run());
    }
    private void shareRenderConnection(){
        JSONObject saved=null;
        try{saved=secrets.load();}catch(Exception ignored){}
        String card=RenderConnectionCard.shareText(secrets.renderPublicId(),
            RenderDirectMcp.isDirectPairing(saved),secrets.enabled(),getPackageName());
        Intent send=new Intent(Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(Intent.EXTRA_TEXT,card);
        try{startActivity(Intent.createChooser(send,"Share Render Studio MCP details"));}
        catch(android.content.ActivityNotFoundException ignored){
            ClipboardManager clipboard=getSystemService(ClipboardManager.class);
            clipboard.setPrimaryClip(ClipData.newPlainText("Render Studio MCP",card));
            Toast.makeText(this,"Render MCP details copied",Toast.LENGTH_LONG).show();
        }
    }
    private void copyRenderAppId(){
        ClipboardManager clipboard=getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText(
            "Render Studio public app ID",secrets.renderPublicId()));
        Toast.makeText(this,"Public Render app ID copied",Toast.LENGTH_SHORT).show();
    }
    private void testRelay(){
        perform(()->{
            JSONObject health=AgentHttp.checkHealth(RenderDirectMcp.ORIGIN);
            return "DIRECT RENDER MCP REACHABLE\n"+health.optString("service","Unknown server")
                +"\n\nOnly the Worker endpoint was checked. Pair and start the Android session before claiming native command connectivity.";
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
            if(status==404)return "The dedicated Render Studio MCP endpoint does not support that route.";
            if(status==403)return "Render Studio enrollment code invalid, expired or already used.";
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
        final String code=enrollment.getText().toString().trim();
        enrollment.setText("");
        if(code.isEmpty()){
            secrets.status("Direct Render Studio enrollment code required.");
            new AlertDialog.Builder(this).setTitle("Enrollment code needed")
                .setMessage("Enter the one-use enrollment code from the existing Render Studio Worker. This is not your ChatGPT password or a VideoStudio code.")
                .setPositiveButton("OK",null).show();return;
        }
        perform(()->{
            JSONObject previous=secrets.load();
            if(RenderDirectMcp.isDirectPairing(previous))
                throw new IllegalStateException("REVOKE_EXISTING_RENDER_PAIRING_FIRST");
            if(previous!=null&&!RenderDirectMcp.isLegacyPairing(previous))
                throw new IllegalStateException("UNRECOGNIZED_PAIRING_REVOKE_FIRST");
            JSONObject health=AgentHttp.checkHealth(RenderDirectMcp.ORIGIN);
            JSONObject answer=AgentHttp.post(RenderDirectMcp.ORIGIN,"/v1/device/enroll",null,
                new JSONObject().put("enrollment_code",code).put("name","Render Studio Android"));
            JSONObject saved=RenderDirectMcp.credentials(
                answer.getString("device_id"),answer.getString("device_token"));
            secrets.enabled(false);
            secrets.save(saved); // Replaces legacy transport credentials only after successful enrollment.
            secrets.status("Direct Render Studio MCP paired. Authorize ChatGPT and Start Agent Session.");
            return "Render Studio paired securely.\n\nChatGPT MCP endpoint:\n"
                +RenderDirectMcp.MCP_ENDPOINT
                +"\n\nTemporary ChatGPT link code (10 minutes):\n"
                +answer.getString("link_code")
                +"\n\nAuthorize this code in the Render Studio MCP login, then start the session.";
        });
    }
    private void link(){perform(()->{
        JSONObject c=RenderDirectMcp.requireDirectPairing(secrets.load());
        JSONObject r=AgentHttp.post(RenderDirectMcp.ORIGIN,"/v1/device/link",
            c.getString("device_token"),new JSONObject());
        return "New Render Studio ChatGPT authorization code (10 minutes):\n"
            +r.getString("link_code")+"\n\nMCP endpoint: "+RenderDirectMcp.MCP_ENDPOINT;
    });}
    private void startSession(){
        if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},42);return;
        }
        try{
            RenderDirectMcp.requireDirectPairing(secrets.load());
            if(!getSystemService(NotificationManager.class).areNotificationsEnabled()){
                secrets.status("Enable Render notifications so the active native session and Stop control stay visible.");return;
            }
            secrets.enabled(true);
            secrets.status("Connecting to dedicated Render Studio MCP. No native command has executed yet.");
            startForegroundService(new Intent(this,AgentService.class));
        }catch(Exception e){
            secrets.enabled(false);
            secrets.status("Direct Render MCP pairing required. Pair this phone with its one-use enrollment code.");
        }
    }
    private void stopSession(){
        secrets.enabled(false);
        secrets.status("Stopped locally; a current native call stops at the next safe boundary.");
        try{startService(new Intent(this,AgentService.class).setAction(AgentService.STOP));}catch(Exception ignored){}
    }
    private void revoke(){
        stopSession();perform(()->{
            JSONObject c=secrets.load();if(c==null)return "No connection is saved.";
            if(RenderDirectMcp.isDirectPairing(c))
                AgentHttp.post(RenderDirectMcp.ORIGIN,"/v1/device/revoke",
                    c.getString("device_token"),new JSONObject());
            // Old relay credentials are deleted locally without contacting VideoStudio.
            secrets.clear();
            secrets.status("Render connection revoked. All native projects were preserved.");
            return "Render Studio MCP pairing revoked or legacy credential discarded. Local projects and files were preserved.";
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
        if(requestCode==StorageDocuments.PICK_FILE)perform(()->transferSummary(StorageDocuments.acceptFile(this,resultCode,data)));
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
                    "Working folder linked. Import uses read access; creating folders and exporting requires the provider's write access.":
                    "No working folder selected.",Toast.LENGTH_LONG).show();
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
