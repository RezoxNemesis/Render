package org.blender.blender;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ViewConfiguration;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import com.rezox.render.agent.RenderManualJobs;
import com.rezox.render.omega.engine.OverlayBounds;
import com.rezox.render.omega.engine.EngineEvidence;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import org.json.JSONObject;

/**
 * Android touch-side controls drawn OVER real Blender's native Vulkan Surface.
 *
 * This never substitutes a reduced Blender engine or shrinks native mesh,
 * shaders, image textures, or final render resolution. Only orientation,
 * temporary workspace layout, and human-visible widget size are changed.
 *
 * No account, server, private token, or arbitrary script runner is used.
 */
public final class BlenderMobileControls {
    public static final String SETTINGS = "render_mobile_ui";
    public static final String MODE = "mode";
    public static final String PORTRAIT = "portrait";
    public static final String LANDSCAPE = "landscape";
    private static final int PANEL = Color.rgb(23,27,37);
    private static final int ORANGE = Color.rgb(255,151,77);
    private static final int WHITE = Color.rgb(248,248,250);
    private static final ExecutorService WORK = Executors.newSingleThreadExecutor();
    private static final String SPOOL = "render_bpy_jobs";

    private BlenderMobileControls(){}

    public static int preferredOrientation(Activity owner) {
        String mode = owner.getSharedPreferences(SETTINGS, Activity.MODE_PRIVATE)
                .getString(MODE, PORTRAIT);
        return LANDSCAPE.equals(mode) ?
                ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE :
                ActivityInfo.SCREEN_ORIENTATION_PORTRAIT;
    }

    public static void setMode(Activity owner,String mode) {
        if(!PORTRAIT.equals(mode) && !LANDSCAPE.equals(mode))
            throw new IllegalArgumentException("UNSUPPORTED_RENDER_ORIENTATION");
        owner.getSharedPreferences(SETTINGS,Activity.MODE_PRIVATE).edit()
             .putString(MODE,mode).apply();
    }

    public static void applySafeInsets(Activity owner) {
        // NativeActivity's original LAYOUT_FULLSCREEN flags place the first
        // row of tiny Blender icons under display notches and status cutouts.
        // Give Blender its ACTUAL drawable content rectangle instead.
        owner.getWindow().getDecorView().setSystemUiVisibility(0);
        owner.getWindow().setDecorFitsSystemWindows(true);
        WindowManager.LayoutParams attributes=owner.getWindow().getAttributes();
        attributes.layoutInDisplayCutoutMode=
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_NEVER;
        owner.getWindow().setAttributes(attributes);
    }

    private static int px(Activity a,int dp) {
        return (int)(dp*a.getResources().getDisplayMetrics().density+.5f);
    }
    private static GradientDrawable shape(int color,int radius,Activity a) {
        GradientDrawable d=new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(px(a,radius));
        d.setStroke(px(a,1),0xFF424754);
        return d;
    }
    private static TextView button(Activity a,String text) {
        TextView b=new TextView(a);
        b.setText(text);
        b.setTextColor(WHITE);
        b.setGravity(Gravity.CENTER);
        b.setTextSize(14);
        b.setMinHeight(px(a,45));
        b.setPadding(px(a,12),px(a,10),px(a,12),px(a,10));
        b.setBackground(shape(PANEL,12,a));
        b.setClickable(true);
        b.setFocusable(true);
        return b;
    }
    private static void toast(Activity a,String value){
        if(!a.isFinishing()&&!a.isDestroyed())
            a.runOnUiThread(()->Toast.makeText(a,value,Toast.LENGTH_SHORT).show());
    }

    public static void attach(BlenderActivity activity) {
        activity.setRequestedOrientation(preferredOrientation(activity));
        applySafeInsets(activity);

        FrameLayout content=new FrameLayout(activity);
        LinearLayout buttons=new LinearLayout(activity);
        buttons.setOrientation(LinearLayout.VERTICAL);
        buttons.setPadding(px(activity,5),px(activity,5),px(activity,5),px(activity,5));
        content.addView(buttons,new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,ViewGroup.LayoutParams.WRAP_CONTENT));
        FrameLayout.LayoutParams position=new FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,ViewGroup.LayoutParams.WRAP_CONTENT,
            Gravity.END|Gravity.TOP);
        position.rightMargin=px(activity,5);
        final int screenHeight=activity.getResources().getDisplayMetrics().heightPixels;
        final int safeMargin=px(activity,8);
        int savedTop=activity.getSharedPreferences(SETTINGS,Activity.MODE_PRIVATE)
            .getInt("overlay_top_px",px(activity,96));
        position.topMargin=OverlayBounds.clampTop(savedTop,screenHeight,
            px(activity,130),safeMargin);
        activity.addContentView(content,position);
        // An attached control surface is observed; a rendered Vulkan frame is NOT.
        EngineEvidence.record(activity,EngineEvidence.Stage.NATIVE_CONTROLS_ATTACHED);

        TextView handle=button(activity,"R  ☰");
        handle.setBackground(shape(0xEEA05F32,14,activity));
        buttons.addView(handle,new LinearLayout.LayoutParams(
            px(activity,58),px(activity,50)));
        LinearLayout tools=new LinearLayout(activity);
        tools.setOrientation(LinearLayout.VERTICAL);
        ScrollView menuScroll=new ScrollView(activity);
        menuScroll.setVerticalScrollBarEnabled(true);
        menuScroll.setFillViewport(false);
        menuScroll.addView(tools,new ScrollView.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));
        menuScroll.setVisibility(View.GONE);
        int menuHeight=OverlayBounds.scrollHeight(
            Math.max(px(activity,70),screenHeight-px(activity,230)),
            px(activity,360),px(activity,115));
        buttons.addView(menuScroll,new LinearLayout.LayoutParams(px(activity,207),menuHeight));
        // A real drag on this owner-visible handle moves ONLY the overlay; it
        // never injects a fake Blender touch or changes the underlying scene.
        final float[] drag=new float[3]; // X, Y, original top pixel
        final boolean[] dragged={false};
        final int touchSlop=ViewConfiguration.get(activity).getScaledTouchSlop();
        handle.setOnTouchListener((view,event)->{
            switch(event.getActionMasked()){
                case MotionEvent.ACTION_DOWN:
                    drag[0]=event.getRawX();
                    drag[1]=event.getRawY();
                    drag[2]=((FrameLayout.LayoutParams)content.getLayoutParams()).topMargin;
                    dragged[0]=false;
                    return true;
                case MotionEvent.ACTION_MOVE: {
                    if(!OverlayBounds.isTap(drag[0],drag[1],
                            event.getRawX(),event.getRawY(),touchSlop))
                        dragged[0]=true;
                    if(dragged[0]){
                        FrameLayout.LayoutParams p=(FrameLayout.LayoutParams)content.getLayoutParams();
                        p.topMargin=OverlayBounds.clampTop(
                            Math.round(drag[2]+event.getRawY()-drag[1]),
                            activity.getResources().getDisplayMetrics().heightPixels,
                            Math.max(px(activity,70),content.getHeight()),safeMargin);
                        content.setLayoutParams(p);
                    }
                    return true;
                }
                case MotionEvent.ACTION_UP:
                    if(!dragged[0] && OverlayBounds.isTap(drag[0],drag[1],
                            event.getRawX(),event.getRawY(),touchSlop)){
                        menuScroll.setVisibility(
                            menuScroll.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE);
                        // Expansion changes actual panel height. Reposition
                        // after layout so options never fall below navigation.
                        menuScroll.post(()->{
                            if(activity.isFinishing()||activity.isDestroyed())return;
                            FrameLayout.LayoutParams layout=(FrameLayout.LayoutParams)content.getLayoutParams();
                            layout.topMargin=OverlayBounds.clampTop(layout.topMargin,
                                activity.getResources().getDisplayMetrics().heightPixels,
                                Math.max(px(activity,70),content.getHeight()),safeMargin);
                            content.setLayoutParams(layout);
                        });
                    }
                    activity.getSharedPreferences(SETTINGS,Activity.MODE_PRIVATE).edit()
                        .putInt("overlay_top_px",
                            ((FrameLayout.LayoutParams)content.getLayoutParams()).topMargin).apply();
                    return true;
                case MotionEvent.ACTION_CANCEL:
                    return true;
                default:return false;
            }
        });

        add(activity,tools,"⌂  Render Home",()->confirmHome(activity));
        add(activity,tools,"▣  Render Image (Protected)",()->send(activity,
              "blender.render.plan_still",new JSONObject()));
        add(activity,tools,"▶  Render Animation",()->send(activity,
              "blender.render.plan_current",new JSONObject()));
        add(activity,tools,"↻  Resume Render / MP4",()->send(activity,
              "blender.render.resume_last",new JSONObject()));
        add(activity,tools,"▣  Save Current Session",()->send(activity,
              "blender.project.save_session",new JSONObject()));
        add(activity,tools,"◉  Fix Viewport Flicker",()->send(activity,
              "blender.ui.stabilize_viewport",new JSONObject()));
        add(activity,tools,"⬇  Export PNG / MP4",()->WORK.execute(()->{
            try {
                String job=RenderManualJobs.status(activity).optString("job_id","");
                if(job.isEmpty())job=RenderManualJobs.newestRecoverable(activity);
                if(job.isEmpty())throw new IllegalStateException("NO_RENDER_JOB");
                RenderManualJobs.export(activity,job);
                toast(activity,"Render exported to Downloads / RenderStudio");
            }catch(Exception error){
                toast(activity,"Render export unavailable: "+error.getMessage());
            }
        }));
        add(activity,tools,"▣  Focus viewport",()->send(activity,"blender.ui.focus_viewport",
              new JSONObject()));
        add(activity,tools,"A+  Larger controls",()->send(activity,"blender.ui.adjust_scale",
              values("delta",.15)));
        add(activity,tools,"A−  Smaller controls",()->send(activity,"blender.ui.adjust_scale",
              values("delta",-.15)));
        add(activity,tools,"↻  Rotate / Fit",()->{
            String selected=activity.getSharedPreferences(SETTINGS,Activity.MODE_PRIVATE)
                    .getString(MODE,PORTRAIT);
            String next=PORTRAIT.equals(selected)?LANDSCAPE:PORTRAIT;
            setMode(activity,next);
            activity.setRequestedOrientation(preferredOrientation(activity));
            applySafeInsets(activity);
            toast(activity,next.equals(PORTRAIT)?"Portrait Focus":"Landscape Full Editor");
            send(activity,"blender.ui.set_mode",values("mode",next));
        });

        // A real, persistent Android progress bar on top of native Blender.
        // The bpy File menu also shows progress in Blender's own Status Bar.
        LinearLayout progressPanel=new LinearLayout(activity);
        progressPanel.setOrientation(LinearLayout.VERTICAL);
        progressPanel.setPadding(px(activity,5),px(activity,4),
                                 px(activity,5),px(activity,4));
        progressPanel.setBackground(shape(PANEL,12,activity));
        progressPanel.setVisibility(View.GONE);
        LinearLayout.LayoutParams panelLayout=new LinearLayout.LayoutParams(
                px(activity,190),ViewGroup.LayoutParams.WRAP_CONTENT);
        panelLayout.topMargin=px(activity,5);
        buttons.addView(progressPanel,panelLayout);
        TextView frameStatus=new TextView(activity);
        frameStatus.setTextColor(WHITE);
        frameStatus.setTextSize(11);
        progressPanel.addView(frameStatus);
        ProgressBar frameProgress=new ProgressBar(activity,null,
                android.R.attr.progressBarStyleHorizontal);
        frameProgress.setMax(100);
        progressPanel.addView(frameProgress,new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,px(activity,7)));
        TextView renderControl=button(activity,"Pause after frame");
        renderControl.setTextSize(11);
        progressPanel.addView(renderControl,new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,px(activity,39)));
        renderControl.setOnClickListener(v->{
            if(RenderManualJobs.active()){
                RenderManualJobs.pause();
                toast(activity,"Pausing after the current frame");
            } else {
                WORK.execute(()->{
                    String job=RenderManualJobs.status(activity).optString("job_id","");
                    if(job.isEmpty())job=RenderManualJobs.newestRecoverable(activity);
                    if(!job.isEmpty()&&RenderManualJobs.start(activity,job))
                        toast(activity,"Resuming the saved render");
                    else toast(activity,"Open File → Resume Render to recover a job");
                });
            }
        });
        final Handler refreshHandler=new Handler(Looper.getMainLooper());
        final Runnable pulse=new Runnable(){
            @Override public void run(){
                if(activity.isFinishing()||activity.isDestroyed())return;
                RenderManualJobs.acceptMenuRequest(activity);
                JSONObject snapshot=RenderManualJobs.status(activity);
                String job=snapshot.optString("job_id","");
                String state=snapshot.optString("state","idle");
                boolean visible=!job.isEmpty()&&
                    (!"idle".equals(state)||RenderManualJobs.active());
                progressPanel.setVisibility(visible?View.VISIBLE:View.GONE);
                if(visible){
                    int done=snapshot.optInt("completed"),total=snapshot.optInt("total");
                    frameProgress.setProgress(total>0?(int)(100L*done/total):0);
                    String detail=snapshot.optString("detail",state);
                    if(detail.length()>50)detail=detail.substring(0,47)+"...";
                    frameStatus.setText("Render "+done+"/"+total+" frames\n"+detail);
                    renderControl.setText(RenderManualJobs.active()?
                        (snapshot.optBoolean("pausing")?"Finishing current frame…":
                         "Pause after frame"):"▶ Resume saved render");
                    renderControl.setEnabled(!snapshot.optBoolean("pausing"));
                }
                refreshHandler.postDelayed(this,1000L);
            }
        };
        content.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener(){
            @Override public void onViewAttachedToWindow(View v){
                refreshHandler.removeCallbacks(pulse);
                refreshHandler.post(pulse);
            }
            @Override public void onViewDetachedFromWindow(View v){
                refreshHandler.removeCallbacks(pulse);
            }
        });
        refreshHandler.post(pulse);

        // API 33+ handles system back gestures even when the native input
        // queue does not deliver a Java KEYCODE_BACK.
        if(Build.VERSION.SDK_INT>=33) {
            OnBackInvokedCallback onBack=()->confirmHome(activity);
            activity.getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                OnBackInvokedDispatcher.PRIORITY_DEFAULT,onBack);
            activity.renderBackCallback=onBack;
        }
    }

    private static JSONObject values(String key,Object value){
        JSONObject obj=new JSONObject();
        try {obj.put(key,value);}catch(Exception error){throw new IllegalStateException(error);}
        return obj;
    }
    private static void add(Activity a,LinearLayout host,String label,Runnable handler){
        TextView item=button(a,label);
        LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(
            px(a,195),px(a,49));
        params.topMargin=px(a,4);
        host.addView(item,params);
        item.setOnClickListener(v->handler.run());
    }

    /** User explicitly approves leaving the running native editor.
     * Uncommitted scene edits can otherwise be lost during NativeActivity shutdown.
     */
    public static void confirmHome(Activity a){
        if(a.isFinishing()||a.isDestroyed())return;
        if(RenderManualJobs.active()){
            new AlertDialog.Builder(a)
                .setTitle("Rendering in progress")
                .setMessage("Pause after the current frame before leaving. Finished frames are checkpointed and can resume without starting over.")
                .setNegativeButton("Stay in Blender",null)
                .setPositiveButton("Pause at frame boundary",(d,w)->RenderManualJobs.pause())
                .show();
            return;
        }
        new AlertDialog.Builder(a)
            .setTitle("Save work and return?")
            .setMessage("Render will save a verified .blend snapshot before returning. Your previous project and finished render frames stay preserved.")
            .setNegativeButton("Stay in Blender",null)
            .setNeutralButton("Save without leaving",(dialog,which)->
                send(a,"blender.project.save_session",new JSONObject()))
            .setPositiveButton("Save & Return",(dialog,which)->{
                toast(a,"Saving Blender project before leaving…");
                send(a,"blender.project.save_session",new JSONObject(),()->{
                    if(a.isFinishing()||a.isDestroyed())return;
                    Intent home=new Intent().setClassName(a,"com.rezox.render.RenderHubActivity");
                    home.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP);
                    a.startActivity(home);
                    a.finish();
                });
            }).show();
    }

    public static void detach(BlenderActivity activity){
        EngineEvidence.record(activity,EngineEvidence.Stage.CONTROLS_DETACHED);
        if(Build.VERSION.SDK_INT>=33 && activity.renderBackCallback!=null){
            activity.getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback(
                activity.renderBackCallback);
            activity.renderBackCallback=null;
        }
    }

    private static void send(Activity a,String action,JSONObject args){
        send(a,action,args,null);
    }
    private static void send(Activity a,String action,JSONObject args,Runnable completed){
        // The same authenticated typed bpy sidecar handles UI-only requests,
        // but they are not remotely registered as agent actions.
        WORK.execute(()->{
            String id=UUID.randomUUID().toString().replace("-","");
            File root=new File(a.getFilesDir(),SPOOL);
            File pending=new File(root,"pending");
            File result=new File(root,"results/"+id+".json");
            try {
                if(!pending.isDirectory()&&!pending.mkdirs())
                    throw new java.io.IOException("NATIVE_UI_QUEUE_UNAVAILABLE");
                JSONObject command=new JSONObject()
                    .put("id",id).put("action",action).put("args",args)
                    .put("deadline",System.currentTimeMillis()/1000+
                        (action.startsWith("blender.project.")||action.startsWith("blender.render.")?180:15));
                File temporary=File.createTempFile("render-control-",".part",pending);
                try(FileOutputStream stream=new FileOutputStream(temporary)){
                    stream.write(command.toString().getBytes(StandardCharsets.UTF_8));
                    stream.getFD().sync();
                }
                File ready=new File(pending,id+".json");
                try {Files.move(temporary.toPath(),ready.toPath(),StandardCopyOption.ATOMIC_MOVE);}
                catch(java.nio.file.AtomicMoveNotSupportedException e){
                    Files.move(temporary.toPath(),ready.toPath());
                }
                long until=System.nanoTime()+ TimeUnit.SECONDS.toNanos(
                    (action.startsWith("blender.project.")||action.startsWith("blender.render.")?180:12));
                while(System.nanoTime()<until){
                    if(result.isFile()) {
                        JSONObject response=new JSONObject(
                            new String(Files.readAllBytes(result.toPath()),StandardCharsets.UTF_8));
                        result.delete();
                        if(!"succeeded".equals(response.optString("state")))
                            toast(a,"Blender: "+response.optString("error","Control unavailable"));
                        else {
                            if(action.equals("blender.project.save_session"))
                                toast(a,"Session saved — next launch will restore it");
                            else if(action.startsWith("blender.render."))
                                toast(a,"Rendering queued in native Blender");
                            if(completed!=null)a.runOnUiThread(completed);
                        }
                        return;
                    }
                    Thread.sleep(180);
                }
                ready.delete();
                toast(a,"Blender UI is busy. Command may not have completed.");
            } catch(Exception ex){
                toast(a,"Mobile control unavailable: "+ex.getClass().getSimpleName());
            }
        });
    }
}
