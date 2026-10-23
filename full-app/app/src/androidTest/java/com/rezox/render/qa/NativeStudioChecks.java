package com.rezox.render.qa;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.graphics.Bitmap;
import android.os.Build;
import android.os.Bundle;
import android.util.AtomicFile;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONArray;
import org.json.JSONObject;

/** Fixed native integration checks on an isolated debug emulator, never a command relay.
 * Every scene/edit/render call passes through the same ProductionBridge as VideoStudio.
 * Host tests, launch acknowledgements and screenshots are not counted as rendered frames.
 */
public final class NativeStudioChecks extends Instrumentation {
    private Context target;
    private String phase,publicId;
    private JSONObject evidence;
    private AtomicFile output;

    @Override public void onCreate(Bundle args) {super.onCreate(args);phase=args==null?"":args.getString("phase","");start();}
    private JSONObject call(String operation,JSONObject payload)throws Exception {
        Class<?> cls=Class.forName("com.rezox.render.agent.ProductionBridge",true,target.getClassLoader());
        JSONObject args=new JSONObject().put("operation",operation).put("payload",payload);
        if(publicId!=null)args.put("target_id",publicId);
        try{return (JSONObject)cls.getMethod("execute",Context.class,JSONObject.class,AtomicBoolean.class)
            .invoke(null,target,args,new AtomicBoolean(false));}
        catch(InvocationTargetException error){throw new Exception(String.valueOf(error.getCause().getMessage()),error.getCause());}
    }
    private JSONObject call(String operation)throws Exception{return call(operation,new JSONObject());}
    private void save(String state)throws Exception {
        evidence.put("stage",state).put("updated_at_ms",System.currentTimeMillis());
        FileOutputStream out=output.startWrite();
        try{out.write(evidence.toString(2).getBytes(StandardCharsets.UTF_8));output.finishWrite(out);}
        catch(Exception error){output.failWrite(out);throw error;}
    }
    private JSONObject operation(String name,JSONObject payload)throws Exception {
        save(name+" requested once");JSONObject result=call(name,payload);save(name+" completed");return result;
    }
    private void require(boolean condition,String reason){if(!condition)throw new IllegalStateException(reason);}
    private JSONObject artist(String operator,String object,JSONObject parameters)throws Exception {
        return operation("operator.execute",new JSONObject().put("operator",operator)
            .put("parameters",parameters.put("object",object)).put("expected_object",object));
    }
    private void core()throws Exception {
        require(call("capabilities").optBoolean("native_editor_ready"),"NATIVE_EDITOR_NOT_READY_NO_RELAUNCH");
        evidence.put("checkpoint",operation("project.checkpoint",new JSONObject().put("name","QA029BeforeChecks")));
        JSONObject original=call("render.quality.inspect");evidence.put("original_settings",original);
        JSONObject changed=operation("render.performance.configure",new JSONObject().put("persistent_data",!original.getBoolean("persistent_data")));
        JSONObject after=changed.getJSONObject("after");
        for(String key:new String[]{"engine","width","height","percentage","samples","fps","fps_base","denoising"})
            require(String.valueOf(original.opt(key)).equals(String.valueOf(after.opt(key))),"PERFORMANCE_CHANGED_QUALITY_"+key);
        evidence.put("performance_roundtrip",changed);
        operation("render.performance.configure",new JSONObject().put("persistent_data",original.getBoolean("persistent_data")));
        String object="QA029Mesh_"+UUID.randomUUID().toString().substring(0,8);
        evidence.put("mesh",operation("mesh.create",new JSONObject().put("name",object).put("kind","CUBE")));
        JSONObject subdivided=artist("mesh.subdivide",object,new JSONObject().put("cuts",1));
        require(subdivided.getInt("polygons")>6,"NATIVE_SUBDIVISION_DID_NOT_CREATE_GEOMETRY");
        evidence.put("subdivision",subdivided);
        evidence.put("normals",artist("mesh.recalculate_normals",object,new JSONObject()));
        evidence.put("uv",artist("uv.smart_project",object,new JSONObject()));
        try{artist("object.add_modifier",object,new JSONObject().put("type","SUBSURF").put("levels",-1));
            throw new IllegalStateException("INVALID_MODIFIER_WAS_ACCEPTED");}
        catch(Exception expected){require(String.valueOf(expected.getMessage()).contains("INVALID_SUBSURF_LEVEL"),"UNEXPECTED_NEGATIVE_TEST_ERROR_"+expected.getMessage());}
        JSONObject modifier=artist("object.add_modifier",object,new JSONObject().put("type","SUBSURF").put("name","QASubdivision").put("levels",1));
        require(modifier.getJSONArray("modifiers").length()==1,"REJECTED_MODIFIER_LEFT_A_MUTATION");
        evidence.put("modifier",modifier);
        evidence.put("applied",artist("object.modifier_apply",object,new JSONObject().put("modifier","QASubdivision")));
        evidence.put("transforms",artist("object.transform_apply",object,new JSONObject().put("scale",true)));
        Bitmap bitmap=Bitmap.createBitmap(4,4,Bitmap.Config.ARGB_8888);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();bitmap.compress(Bitmap.CompressFormat.PNG,100,bytes);bitmap.recycle();
        byte[] image=bytes.toByteArray();byte[] hash=MessageDigest.getInstance("SHA-256").digest(image);StringBuilder digest=new StringBuilder();
        for(byte value:hash)digest.append(String.format(java.util.Locale.ROOT,"%02x",value&255));
        JSONObject receipt=operation("reference.write",new JSONObject().put("sha256",digest.toString()).put("extension","png")
            .put("offset",0).put("total_bytes",image.length).put("base64",Base64.encodeToString(image,Base64.NO_WRAP)).put("finish",true));
        require(receipt.optBoolean("complete"),"NATIVE_IMAGE_IMPORT_INCOMPLETE");
        evidence.put("image_import",receipt);
        JSONObject metadata=call("reference.metadata",new JSONObject().put("asset",digest+".png"));
        require(metadata.getInt("width")==4&&metadata.getInt("height")==4,"NATIVE_IMAGE_METADATA_MISMATCH");
        evidence.put("image_metadata",metadata);
        evidence.put("viewport",call("viewport.inspect"));
        evidence.put("screenshot",operation("screenshot.capture",new JSONObject()));
        evidence.put("final_checkpoint",operation("project.checkpoint",new JSONObject().put("name","QA029ArtistTools")));
    }
    private void assets()throws Exception {
        JSONObject search=null;long deadline=System.nanoTime()+180_000_000_000L;
        do{
            search=call("asset.search",new JSONObject().put("query","grass").put("kind","models"));
            evidence.put("catalog",search);save("native_asset_catalog");
            if("ready".equals(search.optString("state")))break;
            if("unavailable".equals(search.optString("state"))&&!search.optString("network_error").isEmpty())
                throw new IllegalStateException("NATIVE_ASSET_NETWORK_"+search.getString("network_error"));
            Thread.sleep(2000);
        }while(System.nanoTime()<deadline);
        require(search!=null&&search.optInt("total_matches")>0,"NATIVE_ASSET_SEARCH_DID_NOT_RETURN_MATCHES");
        JSONObject download=operation("asset.download",new JSONObject().put("asset_id","wooden_stool_02").put("resolution","1k").put("kind","models"));
        String id=download.getString("download_id");evidence.put("download_id",id);
        deadline=System.nanoTime()+600_000_000_000L;
        JSONObject state;
        do{
            state=call("asset.download.status",new JSONObject().put("download_id",id));
            evidence.put("download",state);save("native_asset_download_progress");
            if("downloaded".equals(state.optString("state")))break;
            require(!"failed".equals(state.optString("state")),"NATIVE_ASSET_DOWNLOAD_"+state.optString("error"));
            Thread.sleep(2000);
        }while(System.nanoTime()<deadline);
        require("downloaded".equals(state.optString("state")),"NATIVE_ASSET_DOWNLOAD_TIMEOUT");
        JSONObject imported=operation("asset.import",new JSONObject().put("download_id",id));
        require(imported.optInt("objects")>0,"NATIVE_ASSET_IMPORT_EMPTY");evidence.put("imported_asset",imported);
        evidence.put("checkpoint",operation("project.checkpoint",new JSONObject().put("name","QA029CC0Asset")));
        evidence.put("screenshot",operation("screenshot.capture",new JSONObject()));
    }
    private void render()throws Exception {
        // Explicit small QA settings only; original scene settings and frozen jobs remain intact.
        JSONObject plan=operation("render.plan",new JSONObject().put("name","QA029Background")
            .put("width",160).put("height",90).put("samples",8).put("engine","CYCLES").put("start",1).put("end",6).put("fps",24));
        String id=plan.getString("job_id");evidence.put("plan",plan);
        target.getSharedPreferences("native_studio_029_tests",Context.MODE_PRIVATE).edit().putString("render_job",id).commit();
        evidence.put("start",operation("render.job.start",new JSONObject().put("job_id",id)));
        require(evidence.getJSONObject("start").optBoolean("foreground_launch_requested"),"ANDROID_FOREGROUND_RENDER_LAUNCH_DENIED");
        evidence.put("background_completion_claimed",false);
    }
    private void status()throws Exception {
        String id=target.getSharedPreferences("native_studio_029_tests",Context.MODE_PRIVATE).getString("render_job","");
        require(id.matches("[a-f0-9]{32}"),"NO_NATIVE_QA_RENDER_JOB");
        evidence.put("foreground",call("render.job.status"));
        evidence.put("render",call("render.status",new JSONObject().put("job_id",id)));
    }
    @Override public void onStart(){
        Bundle result=new Bundle();int code=Activity.RESULT_CANCELED;
        try{
            target=getTargetContext();
            require((target.getApplicationInfo().flags&ApplicationInfo.FLAG_DEBUGGABLE)!=0,"DEBUG_APPLICATION_REQUIRED");
            require("ranchu".equals(Build.HARDWARE)||"goldfish".equals(Build.HARDWARE),"ISOLATED_WORKSPACE_EMULATOR_REQUIRED");
            require(phase.equals("core")||phase.equals("assets")||phase.equals("render")||phase.equals("status"),"UNKNOWN_FIXED_TEST_PHASE");
            File folder=new File(target.getFilesDir(),"StudioValidation");folder.mkdirs();
            File path=new File(folder,"029_"+phase+".json");
            require(phase.equals("status")||!path.exists(),"EXISTING_NATIVE_TEST_RECEIPT_INSPECT_BEFORE_REPLAY");
            output=new AtomicFile(path);
            evidence=new JSONObject().put("test_id",UUID.randomUUID().toString()).put("phase",phase)
                .put("workspace_emulator_only",true).put("physical_phone_evidence",false)
                .put("film_animation_created",false).put("passed",false);
            save("checking_native_target");JSONObject caps=call("capabilities");
            require("Render Studio".equals(caps.getString("target_app"))&&"com.rezox.render".equals(caps.getString("target_package")),"WRONG_NATIVE_TARGET");
            publicId=caps.getString("render_public_id");evidence.put("render_public_id",publicId).put("capabilities",caps);
            require(target.getPackageManager().getPackageInfo(target.getPackageName(),0).getLongVersionCode()>=35,"UPGRADED_APK_REQUIRED");
            if(phase.equals("core"))core();else if(phase.equals("assets"))assets();else if(phase.equals("render"))render();else status();
            evidence.put("passed",true);save("passed_native_"+phase);code=Activity.RESULT_OK;
        }catch(Throwable error){
            try{if(evidence!=null){evidence.put("error",error.toString()).put("cause",String.valueOf(error.getCause()));save("failed_native_"+phase);}}catch(Exception ignored){}
            result.putString("error",error.toString());
        }finally{if(evidence!=null)result.putString("result",evidence.toString());finish(code,result);}
    }
}
