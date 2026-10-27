package com.rezox.render;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.rezox.render.agent.AgentWorkPresence;
import com.rezox.render.ui.StudioUi;
import com.rezox.render.ui.StudioViewportArt;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** The native Android entry to the installed Blender Creator tools. */
public final class RenderHubActivity extends Activity {
    public static final String EXTRA_CREATOR_FOCUS="render_creator_focus";
    private TextView agentWorkStatus,renderStatus;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService work=Executors.newSingleThreadExecutor();
    private final AtomicBoolean readingStatus=new AtomicBoolean(false);
    private boolean visible;
    private final Runnable refresh=new Runnable(){
        @Override public void run(){
            if(!visible)return;
            // Long-export manifests are read away from the scrolling UI.
            if(readingStatus.compareAndSet(false,true))work.execute(()->{
                String agent="Native activity unavailable",render="Saved progress unavailable";
                try{
                    AgentWorkPresence.Snapshot s=AgentWorkPresence.snapshot(RenderHubActivity.this);
                    if(s.isWorking())agent="Working in Blender · "+s.displayAction()+
                        (s.progress>=0?" · "+s.progress+"%":"");
                    else if(s.needsRecovery())agent="Interrupted command · inspect history before retrying";
                    else if(s.isPaused())agent="Paused · "+s.displayStage();
                    else if("succeeded".equals(s.state))agent="Last native action completed";
                    else if("failed".equals(s.state)||"cancelled".equals(s.state))
                        agent="Last action "+s.state+" · details in Agent Control";
                    else agent="Ready for your next native command";
                    org.json.JSONObject job=com.rezox.render.agent.RenderManualJobs.status(RenderHubActivity.this);
                    int done=job.optInt("completed"),total=job.optInt("total");
                    String state=job.optString("state","idle").replace('_',' ');
                    render=total>0?done+" / "+total+" frames verified · "+state:"No active frame export";
                    try{
                        org.json.JSONArray entries=com.rezox.render.agent.RenderJobQueue
                            .status(RenderHubActivity.this).getJSONArray("entries");
                        int queued=0;
                        for(int i=0;i<entries.length();i++)
                            if("queued".equals(entries.getJSONObject(i).optString("state")))queued++;
                        if(queued>0)render+="\n"+queued+" queued export"+(queued==1?"":"s");
                    }catch(Exception ignored){render+="\nOpen Agent Control to inspect the queue";}
                    render+="\nBlender: "+(com.rezox.render.agent.NativeHeartbeat.ready(
                        RenderHubActivity.this)?"ready":"not ready or busy");
                }catch(RuntimeException ignored){ /* Preserve a non-sensitive fallback. */ }
                final String a=agent,r=render;
                ui.post(()->{
                    readingStatus.set(false);
                    if(visible&&!isFinishing()&&!isDestroyed()){
                        if(agentWorkStatus!=null)agentWorkStatus.setText(a);
                        if(renderStatus!=null)renderStatus.setText(r);
                    }
                });
            });
            ui.postDelayed(this,2000);
        }
    };
    @Override public void onResume(){
        super.onResume();visible=true;ui.removeCallbacks(refresh);ui.post(refresh);
        work.execute(()->com.rezox.render.agent.RenderLongForegroundService
            .resumeConsentedVisibleJob(getApplicationContext()));
    }
    @Override public void onPause(){visible=false;ui.removeCallbacks(refresh);super.onPause();}
    @Override public void onDestroy(){ui.removeCallbacks(refresh);work.shutdown();super.onDestroy();}

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        LinearLayout page=StudioUi.page(this);
        boolean wide=getResources().getConfiguration().screenWidthDp>=720;
        if(wide)page.setPadding(StudioUi.dp(this,36),StudioUi.dp(this,24),
            StudioUi.dp(this,36),StudioUi.dp(this,32));
        LinearLayout brand=StudioUi.row(this);
        TextView mark=StudioUi.text(this,"R",22,0xFF191218,true);
        mark.setGravity(Gravity.CENTER);
        mark.setBackground(StudioUi.gradient(this,0xFFFFBF88,StudioUi.ORANGE,0,16));
        mark.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        brand.addView(mark,new LinearLayout.LayoutParams(StudioUi.dp(this,48),StudioUi.dp(this,48)));
        LinearLayout wordmark=StudioUi.column(this);
        wordmark.setPadding(StudioUi.dp(this,12),0,StudioUi.dp(this,8),0);
        StudioUi.add(wordmark,StudioUi.text(this,"Render Studio",19,StudioUi.WHITE,true));
        StudioUi.add(wordmark,StudioUi.label(this,"Creator edition"));
        brand.addView(wordmark,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        brand.addView(StudioUi.chip(this,"ON DEVICE",StudioUi.GREEN));
        StudioUi.add(page,brand);StudioUi.space(page,27);

        LinearLayout hero=wide?StudioUi.row(this):StudioUi.column(this);
        LinearLayout intro=StudioUi.column(this);
        StudioUi.add(intro,StudioUi.label(this,"IDEA → EDITABLE 3D"));StudioUi.space(intro,8);
        StudioUi.add(intro,StudioUi.text(this,"Make your next\n3D world.",wide?38:33,StudioUi.WHITE,true));
        StudioUi.space(intro,10);
        StudioUi.add(intro,StudioUi.text(this,
            "Build an asset. Shape a landscape. Set it in motion. Start with guided tools, then keep creating in the full Blender editor.",
            14,StudioUi.MUTED,false));
        StudioUi.space(intro,16);
        addAction(intro,"Open Creator workspace  ↗",StudioUi.PRIMARY,()->launchEditor("portrait",true));
        if(wide){
            hero.addView(intro,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
            hero.addView(new View(this),new LinearLayout.LayoutParams(StudioUi.dp(this,24),1));
        }else{StudioUi.add(hero,intro);StudioUi.space(hero,17);}
        LinearLayout visual=StudioUi.column(this);
        visual.setBackground(StudioUi.gradient(this,0xFF2D2636,0xFF101820,StudioUi.BORDER,22));
        TextView caption=StudioUi.text(this,"A PLACE TO START CREATING",10,0xFFCFC7DE,true);
        caption.setLetterSpacing(.08f);
        caption.setPadding(StudioUi.dp(this,16),StudioUi.dp(this,13),StudioUi.dp(this,12),0);
        StudioUi.add(visual,caption);
        StudioViewportArt art=new StudioViewportArt(this);
        art.setContentDescription("Illustration of a three dimensional scene");
        visual.addView(art,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
            StudioUi.dp(this,wide?190:146)));
        if(wide)hero.addView(visual,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        else StudioUi.add(hero,visual);
        StudioUi.add(page,hero);StudioUi.space(page,17);

        LinearLayout creator=StudioUi.card(this);
        StudioUi.add(creator,StudioUi.label(this,"01 / CREATE IN BLENDER"));StudioUi.space(creator,7);
        StudioUi.add(creator,StudioUi.text(this,"A simpler starting point",23,StudioUi.WHITE,true));
        StudioUi.space(creator,6);
        StudioUi.add(creator,StudioUi.text(this,
            "Editable models and materials · terrain and linked scatter · motion, rigs and cameras.",
            13,StudioUi.MUTED,false));
        StudioUi.space(creator,15);
        addAction(creator,"Quick guide & recipe examples",StudioUi.SECONDARY,this::showCreatorGuide);
        StudioUi.space(creator,11);
        StudioUi.add(creator,StudioUi.text(this,
            "In Blender: Create tab → choose a recipe → preview → create. Your existing scene stays in place.",
            12,StudioUi.MUTED,false));
        StudioUi.add(page,creator);StudioUi.space(page,14);

        LinearLayout editor=StudioUi.card(this);
        StudioUi.add(editor,StudioUi.label(this,"YOUR FULL WORKSPACE"));StudioUi.space(editor,6);
        StudioUi.add(editor,StudioUi.text(this,"Take control of every detail",21,StudioUi.WHITE,true));
        StudioUi.space(editor,6);
        StudioUi.add(editor,StudioUi.text(this,
            "Portrait focuses the viewport for touch. Landscape opens the full Blender layout, including sculpting, shaders and animation editors.",
            13,StudioUi.MUTED,false));
        StudioUi.space(editor,14);
        addAction(editor,"Open portrait focus  ↗",StudioUi.SECONDARY,()->launchEditor("portrait",false));
        StudioUi.space(editor,8);
        addAction(editor,"Open full landscape editor  ↗",StudioUi.SECONDARY,()->launchEditor("landscape",false));

        LinearLayout agent=StudioUi.violetCard(this);
        StudioUi.add(agent,StudioUi.label(this,"02 / CREATE WITH CHATGPT"));StudioUi.space(agent,7);
        StudioUi.add(agent,StudioUi.text(this,"Describe it. Refine it together.",22,StudioUi.WHITE,true));
        StudioUi.space(agent,7);
        StudioUi.add(agent,StudioUi.text(this,
            "Connect ChatGPT to Render, ask for a plan and inspect the native results. Modeling runs in Blender on your device.",
            13,0xFFC9C0DF,false));
        StudioUi.space(agent,13);
        agentWorkStatus=StudioUi.text(this,"Reading native activity…",13,StudioUi.WHITE,true);
        agentWorkStatus.setContentDescription("Live native Blender command status");
        StudioUi.add(agent,agentWorkStatus);StudioUi.space(agent,14);
        addAction(agent,"Connect / Agent Control  →",StudioUi.PURPLE,this::openAgent);
        StudioUi.space(agent,9);
        StudioUi.add(agent,StudioUi.text(this,
            "Built-in recipes are local guided tools. ChatGPT uses your paired connection.",12,0xFFC9C0DF,false));
        addPair(page,editor,agent,wide);StudioUi.space(page,14);

        LinearLayout projects=StudioUi.card(this);
        StudioUi.add(projects,StudioUi.label(this,"03 / KEEP YOUR WORK"));StudioUi.space(projects,7);
        StudioUi.add(projects,StudioUi.text(this,"Projects & backups",21,StudioUi.WHITE,true));
        StudioUi.space(projects,5);
        StudioUi.add(projects,StudioUi.text(this,
            "Import a .blend project, inspect its scene data, or choose a working and backup folder through Agent Control.",
            13,StudioUi.MUTED,false));
        StudioUi.space(projects,14);
        addAction(projects,"Import / inspect projects  →",StudioUi.SECONDARY,
            ()->startActivity(new Intent(this,MainActivity.class)));
        StudioUi.space(projects,8);
        addAction(projects,"Working folder & backups  →",StudioUi.SECONDARY,this::openAgent);

        LinearLayout jobs=StudioUi.card(this);
        StudioUi.add(jobs,StudioUi.label(this,"RENDER CONTINUITY"));StudioUi.space(jobs,7);
        StudioUi.add(jobs,StudioUi.text(this,"Pick up where you left off",21,StudioUi.WHITE,true));
        StudioUi.space(jobs,9);
        renderStatus=StudioUi.text(this,"Reading saved frame progress…",13,StudioUi.WHITE,false);
        renderStatus.setContentDescription("Saved render progress and editor readiness");
        StudioUi.add(jobs,renderStatus);StudioUi.space(jobs,12);
        LinearLayout controls=StudioUi.column(this);controls.setVisibility(View.GONE);
        TextView toggle=addAction(jobs,"Show render controls  ↓",StudioUi.SECONDARY,()->{});
        toggle.setOnClickListener(v->{
            boolean show=controls.getVisibility()!=View.VISIBLE;
            controls.setVisibility(show?View.VISIBLE:View.GONE);
            toggle.setText(show?"Hide render controls  ↑":"Show render controls  ↓");
        });
        StudioUi.space(controls,9);
        addAction(controls,"Pause at a saved frame",StudioUi.SECONDARY,()->controlJob("pause"));
        StudioUi.space(controls,8);
        addAction(controls,"Resume / retry export",StudioUi.SECONDARY,()->controlJob("resume"));
        StudioUi.space(controls,8);
        addAction(controls,"Cancel job · keep completed frames",StudioUi.DANGER,()->controlJob("cancel"));
        StudioUi.space(controls,8);
        addAction(controls,"Memory reserve / frame pacing",StudioUi.SECONDARY,
            ()->com.rezox.render.agent.RenderScheduling.showControls(this));
        StudioUi.add(jobs,controls);StudioUi.space(jobs,10);
        StudioUi.add(jobs,StudioUi.text(this,
            "Verified frames remain recoverable when Android pauses work. Reopen Render to continue a previously enabled export.",
            12,StudioUi.MUTED,false));
        addPair(page,projects,jobs,wide);StudioUi.space(page,24);

        String version="";
        try{version=getPackageManager().getPackageInfo(getPackageName(),0).versionName;}
        catch(android.content.pm.PackageManager.NameNotFoundException ignored){}
        StudioUi.add(page,StudioUi.label(this,"RENDER STUDIO  /  "+version));StudioUi.space(page,6);
        StudioUi.add(page,StudioUi.text(this,
            "Independent experimental Android port of Blender. Editor availability and performance depend on device memory and Vulkan drivers.",
            12,StudioUi.MUTED,false));
    }
    private TextView addAction(LinearLayout host,String text,int style,Runnable action){
        TextView button=StudioUi.action(this,text,style);
        button.setContentDescription(text.replace("  ↗","").replace("  →",""));
        button.setOnClickListener(v->action.run());StudioUi.add(host,button);return button;
    }
    private void addPair(LinearLayout host,LinearLayout left,LinearLayout right,boolean wide){
        if(!wide){StudioUi.add(host,left);StudioUi.space(host,14);StudioUi.add(host,right);return;}
        LinearLayout row=StudioUi.row(this);row.setGravity(Gravity.TOP);
        row.addView(left,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        row.addView(new View(this),new LinearLayout.LayoutParams(StudioUi.dp(this,14),1));
        row.addView(right,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        StudioUi.add(host,row);
    }
    private void openAgent(){startActivity(new Intent(this,com.rezox.render.agent.AgentActivity.class));}
    private void showCreatorGuide(){
        new AlertDialog.Builder(this).setTitle("Create something real")
            .setMessage("1  Open Creator workspace. In Blender, open the Create sidebar tab or the Creator menu.\n\n"+
                "2  Choose a local recipe, name the result, and preview the objects and steps. Try Wooden crate, Island world, Forest world or Animated prop.\n\n"+
                "3  Create the reviewed plan. The tools add editable Blender data and save checkpoints. View progress in the recipe panel.\n\n"+
                "For one tool at a time, expand Models, Worlds, Materials, Motion, or Camera & Rig. Select an object before adding material, animation, or a rig.\n\n"+
                "For a custom request, connect ChatGPT from Agent Control. Local recipes do not use an AI model.")
            .setPositiveButton("Open Creator",(dialog,which)->launchEditor("portrait",true))
            .setNegativeButton("Close",null).show();
    }
    private void controlJob(String control){
        work.execute(()->{
            String feedback;
            try{
                String job=com.rezox.render.agent.RenderManualJobs.status(this).optString("job_id","");
                if(job.isEmpty())job=com.rezox.render.agent.RenderManualJobs.newestRecoverable(this);
                if(job.isEmpty())feedback="No recoverable render job. Start an export in Blender first.";
                else if("pause".equals(control)){
                    com.rezox.render.agent.RenderLongForegroundService.requestPause(this);
                    feedback="Pause requested. Completed frames are kept.";
                }else if("cancel".equals(control)){
                    com.rezox.render.agent.RenderLongForegroundService.requestCancel(this,job);
                    feedback="Cancel requested. Completed frames are kept.";
                }else{
                    com.rezox.render.agent.RenderLongForegroundService.request(this,job);
                    feedback="Resume requested. Saved frames will be checked.";
                }
            }catch(Exception error){feedback="Could not update this export. Inspect its history in Agent Control.";}
            final String message=feedback;
            ui.post(()->{if(visible&&!isFinishing())Toast.makeText(this,message,Toast.LENGTH_LONG).show();});
        });
    }
    private void launchEditor(String mode,boolean creator){
        org.blender.blender.BlenderMobileControls.setMode(this,mode);
        startActivity(new Intent(this,EditorLaunchActivity.class)
            .putExtra(EXTRA_CREATOR_FOCUS,creator)
            .putExtra(com.rezox.render.omega.engine.EngineStartupRecovery.EXTRA_REQUEST,
                com.rezox.render.omega.engine.EngineStartupRecovery.request(this)));
    }
}
