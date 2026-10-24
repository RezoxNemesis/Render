package com.rezox.render.agent;

import android.content.Context;
import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.List;

/**
 * Read-only, app-owned Blender continuity evidence, independent of
 * Blender's cache/quit.blend (that file only follows an orderly exit).
 *
 * Never starts rendering, overwrites projects, scans Gallery or lowers quality.
 * Call from a worker: verifying large .blend checksums can require disk I/O.
 */
public final class RenderRecoveryStatus {
    private RenderRecoveryStatus(){}

    private static File production(Context context)throws Exception{
        return ProductionFiles.root(context);
    }

    private static boolean matches(File folder,String name,String receipt)throws Exception{
        File target=new File(folder,name), proof=new File(folder,receipt);
        if(Files.isSymbolicLink(target.toPath())||Files.isSymbolicLink(proof.toPath()) ||
           !target.isFile()||!proof.isFile()||proof.length()>4096||target.length()<256)
            return false;
        if(!target.getCanonicalFile().getParentFile().equals(folder.getCanonicalFile()) ||
           !proof.getCanonicalFile().getParentFile().equals(folder.getCanonicalFile()))
            return false;
        JSONObject record=new JSONObject(new String(Files.readAllBytes(proof.toPath()),StandardCharsets.UTF_8));
        if(!name.equals(record.optString("filename",""))||target.length()!=record.optLong("bytes",-1))
            return false;
        String expected=record.optString("sha256","");
        if(!expected.matches("[a-f0-9]{64}"))return false;
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        try(FileInputStream stream=new FileInputStream(target)){
            byte[] chunk=new byte[65536];int n=stream.read(chunk);
            if(n<7||!new String(chunk,0,7,StandardCharsets.US_ASCII).equals("BLENDER"))
                return false;
            if(n>0)md.update(chunk,0,n);
            while((n=stream.read(chunk))!=-1)md.update(chunk,0,n);
        }
        StringBuilder hash=new StringBuilder();
        for(byte b:md.digest())hash.append(String.format(Locale.ROOT,"%02x",b&255));
        return expected.equals(hash.toString());
    }

    private static String reasonLabel(int reason){
        if(reason==ApplicationExitInfo.REASON_CRASH_NATIVE)return "CRASH_NATIVE";
        if(reason==ApplicationExitInfo.REASON_LOW_MEMORY)return "LOW_MEMORY";
        if(reason==ApplicationExitInfo.REASON_ANR)return "ANR";
        if(reason==ApplicationExitInfo.REASON_CRASH)return "JAVA_CRASH";
        if(reason==ApplicationExitInfo.REASON_SIGNALED)return "SIGNALLED";
        if(reason==ApplicationExitInfo.REASON_USER_REQUESTED)return "USER_REQUESTED";
        if(reason==ApplicationExitInfo.REASON_EXIT_SELF)return "PROCESS_EXIT";
        return "OTHER_OR_UNKNOWN";
    }
    private static JSONObject systemExitEvidence(Context context){
        JSONObject result=new JSONObject();
        try{
            ActivityManager manager=context.getSystemService(ActivityManager.class);
            if(manager==null)return result.put("available",false);
            List<ApplicationExitInfo> events=manager.getHistoricalProcessExitReasons(
                context.getPackageName(),0,5);
            if(events==null||events.isEmpty())return result.put("available",false);
            ApplicationExitInfo item=events.get(0);
            return result.put("available",true)
                .put("reason",reasonLabel(item.getReason()))
                .put("reason_code",item.getReason())
                .put("occurred_at_epoch_ms",item.getTimestamp())
                .put("peak_pss_kb",item.getPss())
                .put("resident_rss_kb",item.getRss())
                .put("is_proof_of_which_render_failed",false);
        }catch(Exception error){
            try{return result.put("available",false);}catch(Exception ignored){return result;}
        }
    }

    /** Supported status comes from actual files, never from a caller's claim. */
    public static JSONObject inspect(Context context){
        JSONObject report=new JSONObject();
        try{
            File root=production(context);
            File projects=new File(root,"Projects");
            boolean latest=matches(projects,"CurrentSession.blend","CurrentSession.json");
            boolean previous=matches(projects,"CurrentSession.previous.blend","CurrentSession.previous.json");
            report.put("latest_session_verified",latest)
                  .put("previous_session_verified",previous)
                  .put("recoverable",latest||previous)
                  .put("relies_on_quit_blend",false);
            File event=new File(new File(root,"Diagnostics"),"native_render_event.json");
            try{
            if(!Files.isSymbolicLink(event.toPath()) && event.isFile() && event.length()>0 &&
                    event.length()<=8192){
                JSONObject data=new JSONObject(new String(Files.readAllBytes(event.toPath()),StandardCharsets.UTF_8));
                String state=data.optString("state","unknown");
                if(!state.matches("(started|native_callback_completed|native_callback_cancelled)"))
                    state="unknown";
                report.put("last_native_render_state",state)
                      .put("last_native_render_unconfirmed","started".equals(state))
                      .put("last_native_render_at",data.optLong("timestamp_epoch_seconds",0))
                      .put("last_native_render_engine",data.optString("render_engine","unknown"));
            }else{
                report.put("last_native_render_state","not_recorded")
                      .put("last_native_render_unconfirmed",false);
            }
            }catch(Exception logError){
                report.put("last_native_render_state","invalid_native_render_record")
                      .put("last_native_render_unconfirmed",false);
                // Render diagnostics are noncritical; a malformed log must
                // NEVER hide a separately verified recovery snapshot.
            }
            report.put("latest_android_process_exit",systemExitEvidence(context));
            report.put("device_render_crash_root_cause_verified",false)
                  .put("render_output_automatically_verified",false);
        }catch(Exception error){
            try{
                report.put("recovery_inspection_incomplete",error.getClass().getSimpleName())
                    .put("recoverable",false)
                    .put("device_render_crash_root_cause_verified",false);
            }catch(Exception ignored){}
        }
        return report;
    }

    public static String ownerSummary(JSONObject state){
        String recovery=state.optBoolean("recoverable",false)?
            "Verified project snapshot available (File > Recover > Render Studio)":
            "No verified Render Studio session snapshot found";
        String render=state.optBoolean("last_native_render_unconfirmed",false)?
            "Previous native Blender render did not report completion; check diagnostics":
            "Native render record: "+state.optString("last_native_render_state","not_recorded");
        return recovery+"\n"+render;
    }
}
