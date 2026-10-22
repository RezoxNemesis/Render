package com.rezox.render;

import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.FeatureInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.content.ClipboardManager;
import android.content.ClipData;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.rezox.render.ui.StudioUi;
import com.rezox.render.omega.engine.EngineEvidence;
import com.rezox.render.omega.engine.EngineRuntimeSeal;
import com.rezox.render.agent.RenderRecoveryStatus;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Explains the otherwise black first-launch delay: extraction of real Blender
 * Python/assets now happens on a background worker with visible progress.
 * The actual 3D window stays upstream native Blender; no low-res substitute.
 */
public final class EditorLaunchActivity extends Activity {
    private static final String VERSION="5.3";
    private static final String RUNTIME="blender_runtime.zip";
    private static final String STATE_PREF="render_editor_launch";
    private static final AtomicBoolean GLOBAL_PREFLIGHT = new AtomicBoolean(false);
    private TextView status,deviceStatus;
    private LinearLayout actions;
    private final AtomicBoolean starting=new AtomicBoolean(false);
    private volatile boolean destroyed=false;
    private volatile JSONObject recoveryEvidence;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        EngineEvidence.record(this,EngineEvidence.Stage.LAUNCHER_ACTIVITY_CREATED);
        LinearLayout page=StudioUi.page(this);
        LinearLayout top=StudioUi.row(this);
        TextView back=StudioUi.action(this,"←",StudioUi.SECONDARY);
        top.addView(back,new LinearLayout.LayoutParams(StudioUi.dp(this,52),StudioUi.dp(this,50)));
        back.setOnClickListener(v->finish());
        LinearLayout label=StudioUi.column(this);label.setPadding(StudioUi.dp(this,12),0,0,0);
        StudioUi.add(label,StudioUi.label(this,"RENDER  /  ENGINE PREPARATION"));
        StudioUi.add(label,StudioUi.text(this,"Full Blender launch",19,StudioUi.WHITE,true));
        top.addView(label,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        StudioUi.add(page,top);
        StudioUi.space(page,28);
        StudioUi.add(page,StudioUi.text(this,"Preparing your\n3D workspace.",30,StudioUi.WHITE,true));
        StudioUi.space(page,9);
        StudioUi.add(page,StudioUi.text(this,
            "The full Blender Android runtime uses Python, shaders and factory assets. First launch can require a substantial local extraction before the Vulkan editor appears.",
            14,StudioUi.MUTED,false));
        StudioUi.space(page,18);

        LinearLayout progress=StudioUi.card(this);
        StudioUi.add(progress,StudioUi.label(this,"ENGINE STARTUP"));
        StudioUi.space(progress,13);
        status=StudioUi.text(this,"Checking native engine files…",16,StudioUi.WHITE,true);
        StudioUi.add(progress,status);
        StudioUi.space(progress,8);
        StudioUi.add(progress,StudioUi.text(this,
            "This loader performs work on your phone, not a cloud computer.",
            12,StudioUi.MUTED,false));
        StudioUi.add(page,progress);
        StudioUi.space(page,15);

        LinearLayout device=StudioUi.card(this);
        StudioUi.add(device,StudioUi.label(this,"DEVICE COMPATIBILITY"));
        StudioUi.space(device,10);
        deviceStatus=StudioUi.text(this,collectDevice(),13,StudioUi.MUTED,false);
        StudioUi.add(device,deviceStatus);
        StudioUi.add(page,device);
        StudioUi.space(page,15);

        actions=StudioUi.card(this);
        StudioUi.add(actions,StudioUi.label(this,"TROUBLESHOOTING"));
        StudioUi.space(actions,10);
        TextView retry=StudioUi.action(this,"PREPARE & LAUNCH BLENDER",StudioUi.PRIMARY);
        StudioUi.add(actions,retry);
        retry.setOnClickListener(v->prepare());
        StudioUi.space(actions,10);
        TextView diagnostic=StudioUi.action(this,"VIEW STARTUP DIAGNOSTICS",StudioUi.SECONDARY);
        StudioUi.add(actions,diagnostic);
        diagnostic.setOnClickListener(v->showDiagnostics());
        StudioUi.add(page,actions);
        StudioUi.space(page,12);
        StudioUi.add(page,StudioUi.text(this,
            "If the Blender window still stays black after preparation, open Diagnostics. Startup logs can identify missing GPU features, driver errors or native crashes. A successful APK build alone cannot prove device GPU compatibility.",
            12,StudioUi.MUTED,false));
        // Automatic first launch; the button remains available after failure/return.
        status.postDelayed(this::prepare,250);
    }
    private String collectDevice() {
        StringBuilder data=new StringBuilder();
        data.append(Build.MANUFACTURER).append(" ").append(Build.MODEL)
            .append("  •  Android ").append(Build.VERSION.RELEASE)
            .append(" (API ").append(Build.VERSION.SDK_INT).append(")\n");
        boolean seen=false;
        FeatureInfo[] features=getPackageManager().getSystemAvailableFeatures();
        if(features!=null)for(FeatureInfo feature:features) {
            if("android.hardware.vulkan.version".equals(feature.name)) {
                int version=feature.version;
                data.append("Vulkan advertised: ")
                    .append((version>>22)&0x3FF).append(".")
                    .append((version>>12)&0x3FF).append("\n");
                seen=true;
            }
        }
        if(!seen)data.append("Vulkan support not reported by Android. GPU editor may not start.\n");
        ActivityManager manager=getSystemService(ActivityManager.class);
        ActivityManager.MemoryInfo info=new ActivityManager.MemoryInfo();
        manager.getMemoryInfo(info);
        data.append("RAM available: ").append(info.availMem/1024/1024)
            .append(" MiB  •  Storage free: ")
            .append(getFilesDir().getUsableSpace()/1024/1024).append(" MiB");
        return data.toString();
    }
    private void report(String value) {
        getSharedPreferences(STATE_PREF,MODE_PRIVATE).edit()
            .putString("stage",value).putLong("updated",System.currentTimeMillis()).apply();
        if(!destroyed)runOnUiThread(()->{
            if(!isFinishing()&&!isDestroyed())status.setText(value);
        });
    }
    private void prepare() {
        if(!starting.compareAndSet(false,true))return;
        if(!GLOBAL_PREFLIGHT.compareAndSet(false,true)){
            starting.set(false);
            report("Blender resources are being prepared; launch will resume automatically.");
            // Activity recreation must not strand the new UI while the old
            // Activity's background extraction is still holding the gate.
            status.postDelayed(()->{if(!destroyed&&!isFinishing())prepare();},750);
            return;
        }
        EngineEvidence.record(this,EngineEvidence.Stage.PREFLIGHT_ACCEPTED);
        new Thread(()->{
            boolean handedToUi=false;
            try {
                // SHA-checking a multi-gigabyte .blend must never block engine
                // startup. Device can open Blender while diagnostics verify.
                new Thread(()->{
                    JSONObject evidence=RenderRecoveryStatus.inspect(getApplicationContext());
                    recoveryEvidence=evidence;
                    if(!destroyed)runOnUiThread(()->{
                        if(!isFinishing()&&!isDestroyed())
                            deviceStatus.setText(collectDevice()+"\n\n"+
                                RenderRecoveryStatus.ownerSummary(evidence));
                    });
                },"render-background-session-audit").start();
                report("Checking installed Blender libraries…");
                File nativeDir=new File(getApplicationInfo().nativeLibraryDir);
                File library=new File(nativeDir,"libblender.so");
                if(!library.isFile() || library.length()<1048576)
                    throw new IllegalStateException("MISSING_BLENDER_NATIVE_LIBRARY");
                EngineEvidence.record(this,EngineEvidence.Stage.LIBRARY_VALIDATED);
                report("Checking local Blender Python and factory assets…");
                prepareRuntime();
                report("Loading Blender native engine…");
                try {
                    System.loadLibrary("blender");
                    EngineEvidence.record(this,EngineEvidence.Stage.NATIVE_LIBRARY_LOADED);
                }
                catch(LinkageError e){
                    throw new IllegalStateException("NATIVE_BLENDER_LINK_ERROR",e);
                }
                report("Launching Blender Vulkan editor…");
                handedToUi=true;
                runOnUiThread(()->{
                    try{
                        if(isFinishing()||isDestroyed())return;
                        Intent intent=new Intent().setClassName(this,
                            "org.blender.blender.BlenderActivity");
                        startActivity(intent);
                        EngineEvidence.record(this,EngineEvidence.Stage.EDITOR_ACTIVITY_REQUESTED);
                        // StartActivity does not attest an actual GPU frame.
                        status.setText("Native Blender activity requested; first Vulkan pixels remain unverified.");
                    }catch(Exception e) {
                        status.setText("EDITOR_ACTIVITY_LAUNCH_FAILED: "+e.getClass().getSimpleName());
                    }finally{GLOBAL_PREFLIGHT.set(false);}
                });
            }catch(Exception error){
                String text="Editor preparation failed: "+error.getMessage();
                EngineEvidence.record(this,EngineEvidence.Stage.PREFLIGHT_FAILED);
                report(text);
                android.util.Log.e("RenderEditorLaunch",text,error);
            }finally{
                starting.set(false);
                if(!handedToUi)GLOBAL_PREFLIGHT.set(false);
            }
        },"render-blender-preflight").start();
    }
    private void prepareRuntime()throws Exception {
        File container=new File(getFilesDir(),"blender");
        if(!container.isDirectory()&&!container.mkdirs())
            throw new java.io.IOException("RUNTIME_PARENT_NOT_WRITABLE");
        File root=new File(container,VERSION);
        File backup=new File(container,VERSION+".previous");
        // Crash between root->backup and stage->root must not force a fresh
        // project or discard a usable previous *engine* installation.
        if(!root.exists()&&EngineRuntimeSeal.hasInstalledRuntime(backup,VERSION)){
            if(!backup.renameTo(root))
                throw new java.io.IOException("PREVIOUS_BLENDER_RUNTIME_RESTORE_FAILED");
        }
        long stamp=getPackageManager().getPackageInfo(getPackageName(),0).lastUpdateTime;
        String versionStamp=Long.toString(stamp);
        if(EngineRuntimeSeal.hasSamePackageStamp(root,VERSION,versionStamp)){
            EngineEvidence.record(this,EngineEvidence.Stage.RUNTIME_CACHE_REUSED);
            report("Existing Blender runtime seal found; no extraction needed.");
            return;
        }
        // On an APK upgrade, compare stable archive identity; only changed
        // runtime bytes require extraction. This read is off Android's UI thread.
        report("Checking Blender runtime archive revision…");
        String assetDigest=EngineRuntimeSeal.archiveSha256(getAssets().open(RUNTIME));
        EngineEvidence.record(this,EngineEvidence.Stage.RUNTIME_ZIP_HASHED);
        if(EngineRuntimeSeal.sameArchive(root,VERSION,assetDigest)){
            EngineRuntimeSeal.refreshPackageStamp(root,VERSION,versionStamp,assetDigest);
            EngineEvidence.record(this,EngineEvidence.Stage.RUNTIME_CACHE_REUSED);
            report("Blender runtime unchanged across APK upgrade; saved workspace retained.");
            return;
        }
        File stage=new File(container,VERSION+".prepare");
        deleteOwnedTree(stage);
        if(!stage.mkdirs())throw new java.io.IOException("CANNOT_CREATE_RUNTIME_STAGE");
        String stageCanonical=stage.getCanonicalPath()+File.separator;
        long total=0;int entries=0;
        EngineEvidence.record(this,EngineEvidence.Stage.RUNTIME_EXTRACTION_STARTED);
        report("Unpacking Blender resources to app storage…");
        try(InputStream stream=getAssets().open(RUNTIME);
            ZipInputStream input=new ZipInputStream(stream)) {
            ZipEntry e;
            byte[] buffer=new byte[65536];
            while((e=input.getNextEntry())!=null) {
                String name=e.getName();
                if(name.startsWith("/") || name.contains("\\") ||
                   name.startsWith("../") || name.contains("/../") ||
                   name.equals(".."))throw new java.io.IOException("UNSAFE_RUNTIME_ARCHIVE_PATH");
                File target=new File(stage,name);
                if(!target.getCanonicalPath().startsWith(stageCanonical))
                    throw new java.io.IOException("UNSAFE_RUNTIME_ARCHIVE_PATH");
                if(e.isDirectory()){
                    if(!target.isDirectory()&&!target.mkdirs())
                        throw new java.io.IOException("CANNOT_CREATE_RUNTIME_DIR");
                    continue;
                }
                File parent=target.getParentFile();
                if(parent!=null&&!parent.isDirectory()&&!parent.mkdirs())
                    throw new java.io.IOException("CANNOT_CREATE_RUNTIME_DIR");
                try(OutputStream output=new FileOutputStream(target)){
                    int n;
                    while((n=input.read(buffer))!=-1) {
                        output.write(buffer,0,n);
                        total+=n;
                    }
                }
                entries++;
                if(entries%75==0)report("Installing Blender assets… "+entries+
                    " files  •  "+(total/1024/1024)+" MiB");
            }
        }catch(Exception e){deleteOwnedTree(stage);throw e;}
        if(entries<20)throw new java.io.IOException("INCOMPLETE_BLENDER_RUNTIME");
        EngineRuntimeSeal.writeSeal(stage,VERSION,versionStamp,assetDigest);
        if(!EngineRuntimeSeal.hasInstalledRuntime(stage,VERSION))
            throw new java.io.IOException("INCOMPLETE_BLENDER_STARTUP_FILES");
        // Do not erase the previously working runtime before the new one is complete.
        // The old runtime directory is replaceable. app/Production and .blend
        // project files are NEVER touched by this operation.
        deleteOwnedTree(backup);
        boolean hadOld=root.exists();
        if(hadOld&&!root.renameTo(backup))
            throw new java.io.IOException("CANNOT_STAGE_PREVIOUS_RUNTIME");
        if(!stage.renameTo(root)){
            if(hadOld)backup.renameTo(root);
            throw new java.io.IOException("CANNOT_ACTIVATE_RUNTIME");
        }
        // Keep existing preferences when the upstream layout provides config/.
        File oldConfig=new File(backup,"config");
        File newConfig=new File(root,"config");
        if(oldConfig.isDirectory()&&!newConfig.exists())oldConfig.renameTo(newConfig);
        deleteOwnedTree(backup);
        EngineEvidence.record(this,EngineEvidence.Stage.RUNTIME_ACTIVATED);
        report("Blender assets installed: "+entries+" files, "+(total/1024/1024)+" MiB.");
    }
    private static void deleteOwnedTree(File f)throws java.io.IOException {
        if(!f.exists())return;
        if(Files.isSymbolicLink(f.toPath())) {
            if(!f.delete())throw new java.io.IOException("CANNOT_REMOVE_STAGE_LINK");
            return;
        }
        if(f.isDirectory()) {
            File[] children=f.listFiles();
            if(children==null)throw new java.io.IOException("CANNOT_LIST_STAGE");
            for(File child:children)deleteOwnedTree(child);
        }
        if(!f.delete())throw new java.io.IOException("CANNOT_REMOVE_STAGE");
    }
    private String readLog() {
        List<File> candidates=new ArrayList<>();
        candidates.add(new File(Environment.getExternalStoragePublicDirectory(
            Environment.DIRECTORY_DOWNLOADS),"blender-startup.log"));
        if(getExternalFilesDir(null)!=null)
            candidates.add(new File(getExternalFilesDir(null),"blender-startup.log"));
        StringBuilder data=new StringBuilder("RENDER EDITOR DIAGNOSTICS\n");
        data.append(collectDevice()).append("\n\n");
        data.append(EngineEvidence.snapshot(this).toString()).append("\n\n");
        if(recoveryEvidence!=null)data.append("Project and native render evidence: ").append(recoveryEvidence.toString()).append("\n\n");
        data.append("Startup stage: ").append(getSharedPreferences(STATE_PREF,MODE_PRIVATE)
            .getString("stage","Unknown")).append("\n\n");
        for(File file:candidates) {
            if(!file.isFile())continue;
            try(FileInputStream input=new FileInputStream(file)){
                long skip=Math.max(0,file.length()-32000);
                while(skip>0){long moved=input.skip(skip);if(moved<=0)break;skip-=moved;}
                byte[] bytes=new byte[32000];
                int n=input.read(bytes);
                if(n>0)data.append("Log file: ").append(file.getAbsolutePath())
                    .append("\n").append(new String(bytes,0,n,StandardCharsets.UTF_8));
                return data.toString();
            }catch(Exception e){data.append("Could not read: ").append(file.getName()).append("\n");}
        }
        data.append("No readable Blender startup log yet. Android logcat may be needed if the native process crashes before log initialization.");
        return data.toString();
    }
    private void showDiagnostics() {
        String output=readLog();
        new AlertDialog.Builder(this)
            .setTitle("Blender editor diagnostics")
            .setMessage(output)
            .setNegativeButton("Close",null)
            .setNeutralButton("Copy", (d,w)->{
                ClipboardManager cb=getSystemService(ClipboardManager.class);
                cb.setPrimaryClip(ClipData.newPlainText("Render engine diagnostics",output));
            })
            .setPositiveButton("Share", (d,w)->{
                Intent send=new Intent(Intent.ACTION_SEND);
                send.setType("text/plain");
                send.putExtra(Intent.EXTRA_TEXT,output);
                startActivity(Intent.createChooser(send,"Share engine diagnostics"));
            }).show();
    }
    @Override protected void onDestroy(){destroyed=true;super.onDestroy();}
}
