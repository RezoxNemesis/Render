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
        catch(InvocationTargetException error){throw nativeFailure(error);}
    }
    private JSONObject call(String operation)throws Exception{return call(operation,new JSONObject());}
    private Exception nativeFailure(InvocationTargetException error) {
        Throwable cause=error.getCause();
        // Keep the exact native ID and retained receipt when a mutation's
        // outcome needs inspection. A failed phase is never an automatic retry.
        try{evidence.put("failed_native_command_id",cause.getClass().getField("commandId").get(cause));}
        catch(Exception unavailable){ /* Non-native validation/launch error. */ }
        try{evidence.put("failed_native_receipt",cause.getClass().getField("receipt").get(cause));}
        catch(Exception unavailable){ /* No native completion receipt yet. */ }
        return new Exception(String.valueOf(cause.getMessage()),cause);
    }
    private void save(String state)throws Exception {
        evidence.put("stage",state).put("updated_at_ms",System.currentTimeMillis());
        FileOutputStream out=output.startWrite();
        try{out.write(evidence.toString(2).getBytes(StandardCharsets.UTF_8));output.finishWrite(out);}
        catch(Exception error){output.failWrite(out);throw error;}
    }
    private JSONObject operation(String name,JSONObject payload)throws Exception {
        save(name+" requested once");JSONObject result=call(name,payload);
        JSONArray receipts=evidence.optJSONArray("operation_receipts");
        if(receipts==null){receipts=new JSONArray();evidence.put("operation_receipts",receipts);}
        receipts.put(new JSONObject().put("operation",name).put("result",result));
        save(name+" completed");return result;
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
    private void launch()throws Exception {
        JSONObject caps=call("capabilities");
        require(caps.optBoolean("native_activity_asset_change_handling_declared"),"ANDROID_DID_NOT_RESOLVE_NATIVE_CONFIGURATION_MASK");
        if(!caps.optBoolean("native_editor_ready"))
            evidence.put("open",operation("editor.open",new JSONObject()));
        evidence.put("completed_editor_start",false);
    }
    private void configuration()throws Exception {
        require(call("capabilities").optBoolean("native_activity_asset_change_handling_declared"),"NATIVE_CONFIGURATION_HANDLING_NOT_INSTALLED");
        File handoff=new File(target.getFilesDir(),"render_native_launch.json");
        JSONObject before=new JSONObject(new String(java.nio.file.Files.readAllBytes(handoff.toPath()),StandardCharsets.UTF_8));
        String launch=before.getString("native_activity_launch_id");evidence.put("launch_id_before",launch);
        android.content.SharedPreferences events=target.getSharedPreferences("render_editor_launch",Context.MODE_PRIVATE);
        int count=events.getInt("native_configuration_count",0);evidence.put("configuration_count_before",count);
        save("requesting_actual_android_application_resource_update");
        try(android.os.ParcelFileDescriptor command=getUiAutomation().executeShellCommand("am update-appinfo 0 com.rezox.render");
            java.io.InputStream stream=new android.os.ParcelFileDescriptor.AutoCloseInputStream(command)){
            byte[] bytes=new byte[4096];int n=stream.read(bytes);
            evidence.put("android_resource_update_output",n<0?"":new String(bytes,0,n,StandardCharsets.UTF_8));
        }
        long deadline=System.nanoTime()+180_000_000_000L;
        while(System.nanoTime()<deadline){
            if(events.getInt("native_configuration_pid",0)==android.os.Process.myPid()&&
                events.getInt("native_configuration_count",0)>count&&call("capabilities").optBoolean("native_editor_ready"))break;
            Thread.sleep(3000);
        }
        JSONObject after=new JSONObject(new String(java.nio.file.Files.readAllBytes(handoff.toPath()),StandardCharsets.UTF_8));
        evidence.put("launch_id_after",after.getString("native_activity_launch_id"))
            .put("configuration_count_after",events.getInt("native_configuration_count",0));
        require(launch.equals(after.getString("native_activity_launch_id")),"ANDROID_RESOURCE_UPDATE_RECREATED_NATIVE_ACTIVITY");
        require(events.getInt("native_configuration_pid",0)==android.os.Process.myPid()&&
            events.getInt("native_configuration_count",0)>count,"ACTUAL_CONFIGURATION_CALLBACK_NOT_OBSERVED");
        evidence.put("viewport",call("viewport.inspect"));
        evidence.put("screenshot",operation("screenshot.capture",new JSONObject()));
    }
    private void diagnostics()throws Exception {
        // Engineering acceptance only: inspect the real on-device bpy process.
        // No model, benchmark scene, render job or encoding is created.
        require(call("capabilities").optBoolean("native_editor_ready"),"NATIVE_EDITOR_NOT_READY_NO_RELAUNCH");
        for(String operation:new String[]{"device.profile","artist.capabilities","artist.inspect",
                "render.quality.inspect","render.performance.inspect","render.profile.inspect","viewport.inspect"}){
            evidence.put(operation,operation(operation,new JSONObject()));
        }
        evidence.put("screenshot",operation("screenshot.capture",new JSONObject()));
        evidence.put("native_blender_readonly_confirmed",true)
            .put("production_render_created",false).put("model_created",false);
    }
    private JSONObject legacy(String action,JSONObject args)throws Exception {
        save(action+" requested once");
        Class<?> cls=Class.forName("com.rezox.render.agent.AgentActions",true,target.getClassLoader());
        Object actions=cls.getConstructor(Context.class).newInstance(target);
        JSONObject command=new JSONObject().put("request_id","workspace_"+UUID.randomUUID().toString())
            .put("api_version",1).put("action",action).put("args",args);
        try {
            JSONObject result=(JSONObject)cls.getMethod("execute",JSONObject.class,AtomicBoolean.class)
                .invoke(actions,command,new AtomicBoolean(false));
            save(action+" native receipt received");return result;
        }catch(InvocationTargetException error){throw nativeFailure(error);}
    }
    private JSONArray vector(double x,double y,double z)throws Exception {
        return new JSONArray().put(x).put(y).put(z);
    }
    private JSONObject lathe(String name,double[][] profile,boolean closed)throws Exception {
        int sides=64;JSONArray vertices=new JSONArray(),faces=new JSONArray();
        for(double[] ring:profile)for(int j=0;j<sides;j++){
            double theta=j*2*Math.PI/sides;
            vertices.put(vector(Math.rint(ring[0]*Math.cos(theta)*1e7)/1e7,
                Math.rint(ring[0]*Math.sin(theta)*1e7)/1e7,ring[1]));
        }
        int bands=closed?profile.length:profile.length-1;
        for(int i=0;i<bands;i++)for(int j=0;j<sides;j++){
            int next=(j+1)%sides,upper=(i+1)%profile.length;
            faces.put(new JSONArray().put(i*sides+j).put(i*sides+next).put(upper*sides+next).put(upper*sides+j));
        }
        if(!closed){
            JSONArray first=new JSONArray(),last=new JSONArray();
            for(int j=0;j<sides;j++){first.put(sides-1-j);last.put((profile.length-1)*sides+j);}
            faces.put(first).put(last);
        }
        return operation("mesh.create",new JSONObject().put("name",name).put("kind","MESH")
            .put("vertices",vertices).put("faces",faces).put("smooth",true));
    }
    private JSONObject surface(String object,String name,double r,double g,double b,double metallic,double roughness)throws Exception {
        return operation("material.assign",new JSONObject().put("object",object).put("name",name)
            .put("color",vector(r,g,b)).put("metallic",metallic).put("roughness",roughness));
    }
    private void areaLight(String name,double x,double y,double z,double energy,double size,JSONArray color)throws Exception {
        legacy("blender.object.add_light",new JSONObject().put("name",name).put("light_type","AREA")
            .put("location",vector(x,y,z)).put("color",color).put("energy",energy));
        double dx=-x,dy=-y,dz=.075-z;
        legacy("blender.object.set_transform",new JSONObject().put("name",name)
            .put("rotation_euler",vector(0,Math.atan2(Math.hypot(dx,dy),-dz),Math.atan2(dy,dx)+Math.PI)));
        operation("light.configure",new JSONObject().put("object",name).put("size",size));
    }
    private android.content.SharedPreferences artistState(){
        return target.getSharedPreferences("native_artist_0311",Context.MODE_PRIVATE);
    }
    private void artistModel()throws Exception {
        require(call("capabilities").optBoolean("native_editor_ready"),"NATIVE_EDITOR_NOT_READY_NO_RELAUNCH");
        evidence.put("before_checkpoint",operation("project.checkpoint",new JSONObject().put("name","WorkspaceBeforeArtistTest")));
        String engine=call("render.quality.inspect").getString("engine");
        evidence.put("scene",operation("project.create",new JSONObject().put("name","WorkspaceCeramicMugTest")));
        evidence.put("body",lathe("WS_MugBody",new double[][]{
            {.0001,.021},{.015,.021},{.032,.021},{.036,.023},{.038,.027},{.039,.030},
            {.042,.108},{.043,.121},{.0425,.126},{.041,.128},{.038,.128},{.036,.126},
            {.036,.121},{.036,.038},{.033,.033},{.025,.031},{.0001,.031}},false));
        evidence.put("body_subdivision",artist("object.add_modifier","WS_MugBody",new JSONObject()
            .put("type","SUBSURF").put("name","CeramicSurfaceSubdivision").put("levels",2)));
        evidence.put("ceramic",surface("WS_MugBody","WS_GlazedCeramic",.67,.72,.68,0,.18));
        JSONArray handle=new JSONArray();
        for(int j=0;j<=64;j++){
            double angle=-Math.PI/2+j*Math.PI/64;
            handle.put(new JSONArray().put(.039+.032*Math.cos(angle)).put(0).put(.079+.036*Math.sin(angle)).put(1));
        }
        evidence.put("handle",operation("curve.create",new JSONObject().put("name","WS_MugHandle")
            .put("strands",new JSONArray().put(handle)).put("radius",.0045).put("resolution",5)));
        surface("WS_MugHandle","WS_HandleGlaze",.67,.72,.68,0,.18);
        evidence.put("base",lathe("WS_MetalBase",new double[][]{
            {.0001,0},{.075,0},{.083,.002},{.085,.004},{.085,.014},{.083,.017},{.078,.018},{.0001,.018}},false));
        artist("object.add_modifier","WS_MetalBase",new JSONObject().put("type","SUBSURF").put("name","BaseShoulderSubdivision").put("levels",2));
        surface("WS_MetalBase","WS_AnodizedMetal",.045,.055,.065,.85,.29);
        evidence.put("accent",lathe("WS_BrassAccent",new double[][]{{.083,.002},{.0851,.002},{.0851,.004},{.083,.004}},true));
        surface("WS_BrassAccent","WS_Brass",.50,.29,.08,.93,.24);
        evidence.put("coffee",lathe("WS_Coffee",new double[][]{{.0001,.111},{.0352,.111},{.0352,.113},{.0001,.113}},false));
        surface("WS_Coffee","WS_CoffeeSurface",.026,.009,.003,0,.07);
        evidence.put("asset_group",operation("group.create",new JSONObject().put("name","WS_MugTurntable")
            .put("children",new JSONArray().put("WS_MugBody").put("WS_MugHandle").put("WS_Coffee"))));
        operation("mesh.create",new JSONObject().put("name","WS_StudioGround").put("kind","PLANE").put("scale",vector(2,2,1)));
        surface("WS_StudioGround","WS_StudioMatte",.07,.08,.10,0,.72);
        operation("world.configure",new JSONObject().put("color",vector(.18,.20,.24)).put("strength",.2));
        areaLight("WS_KeyLight",-.25,-.30,.45,40,.30,vector(1,.91,.80));
        areaLight("WS_FillLight",.25,-.10,.28,12,.25,vector(.82,.91,1));
        areaLight("WS_RimLight",.10,.25,.40,25,.18,vector(1,.95,.89));
        evidence.put("camera",operation("camera.aim",new JSONObject().put("name","WS_ProductCamera")
            .put("location",vector(.24,-.38,.23)).put("target",vector(0,0,.078)).put("lens",50)));
        evidence.put("final_settings",operation("render.quality.configure",new JSONObject().put("engine",engine)
            .put("width",1280).put("height",720).put("percentage",100).put("samples",128).put("fps",16).put("fps_base",1)));
        evidence.put("performance",operation("render.performance.configure",new JSONObject().put("persistent_data",true)));
        evidence.put("preview_profile",operation("render.profile.configure",new JSONObject().put("profile","preview")
            .put("settings",new JSONObject().put("width",640).put("height",360).put("samples",32))));
        evidence.put("asset_checkpoint",operation("project.checkpoint",new JSONObject().put("name","WorkspaceCeramicMugAsset")));
        evidence.put("focused_viewport",operation("viewport.focus",new JSONObject().put("object","WS_MugBody").put("margin",2.8)));
        evidence.put("inspection",call("artist.inspect"));
        artistState().edit().putString("scene","WorkspaceCeramicMugTest").commit();
        evidence.put("preview_quality_explicit",true).put("final_quality_separate",true).put("visual_quality_verified",false);
    }
    private void artistAnimate()throws Exception {
        require("WorkspaceCeramicMugTest".equals(call("artist.inspect").getString("scene")),"WRONG_NATIVE_ARTIST_SCENE");
        evidence.put("before_animation",operation("project.checkpoint",new JSONObject().put("name","WorkspaceBeforeAnimation")));
        JSONArray keys=new JSONArray();
        for(int i=0;i<=4;i++)keys.put(new JSONObject().put("frame",1+i*8).put("path","rotation_euler").put("value",vector(0,0,i*Math.PI/2)));
        evidence.put("animation",operation("animation.keys",new JSONObject().put("object","WS_MugTurntable").put("keys",keys)));
        evidence.put("animated_checkpoint",operation("project.checkpoint",new JSONObject().put("name","WorkspaceCeramicMugAnimation")));
        evidence.put("native_animation_keys_created",true).put("requested_output_frames",32).put("requested_output_fps",16);
    }
    private void artistRender(boolean animation)throws Exception {
        require("WorkspaceCeramicMugTest".equals(call("artist.inspect").getString("scene")),"WRONG_NATIVE_ARTIST_SCENE");
        JSONObject plan=operation("render.plan",new JSONObject().put("name",animation?"WorkspaceMugAnimationPreview":"WorkspaceMugStillPreview")
            .put("profile","preview").put("start",1).put("end",animation?32:1).put("output_kind",animation?"ANIMATION":"STILL").put("bitrate",4000000));
        String id=plan.getString("job_id");artistState().edit().putString(animation?"animation_job":"still_job",id).commit();
        evidence.put("plan",plan).put("job_id",id);
        evidence.put("start",operation("render.job.start",new JSONObject().put("job_id",id)));
        evidence.put("native_completion_claimed",false);
    }
    private void artistStatus()throws Exception {
        for(String key:new String[]{"still_job","animation_job"}){
            String id=artistState().getString(key,"");
            if(id.matches("[a-f0-9]{32}"))evidence.put(key,call("render.status",new JSONObject().put("job_id",id)));
        }
        evidence.put("foreground",call("render.job.status"));
    }
    private void artistEncode()throws Exception {
        String id=artistState().getString("animation_job","");require(id.matches("[a-f0-9]{32}"),"NO_NATIVE_ANIMATION_JOB");
        JSONObject status=call("render.status",new JSONObject().put("job_id",id));
        require(status.getInt("completed_frames")==32,"NATIVE_ANIMATION_FRAMES_NOT_COMPLETE");
        evidence.put("encode",operation("render.encode",new JSONObject().put("job_id",id)));
        evidence.put("export",operation("render.job.export",new JSONObject().put("job_id",id)));
        evidence.put("film_animation_created",true);
    }
    @Override public void onStart(){
        Bundle result=new Bundle();int code=Activity.RESULT_CANCELED;
        try{
            target=getTargetContext();
            require((target.getApplicationInfo().flags&ApplicationInfo.FLAG_DEBUGGABLE)!=0,"DEBUG_APPLICATION_REQUIRED");
            require("ranchu".equals(Build.HARDWARE)||"goldfish".equals(Build.HARDWARE),"ISOLATED_WORKSPACE_EMULATOR_REQUIRED");
            require(phase.equals("core")||phase.equals("assets")||phase.equals("render")||phase.equals("status")||phase.equals("configuration")||phase.equals("launch")||phase.equals("diagnostics")||phase.equals("artist_model")||phase.equals("artist_animate")||phase.equals("artist_preview")||phase.equals("artist_animation")||phase.equals("artist_status")||phase.equals("artist_encode"),"UNKNOWN_FIXED_TEST_PHASE");
            File folder=new File(target.getFilesDir(),"StudioValidation");folder.mkdirs();
            File path=new File(folder,"029_"+phase+".json");
            require(phase.equals("status")||phase.equals("artist_status")||!path.exists(),"EXISTING_NATIVE_TEST_RECEIPT_INSPECT_BEFORE_REPLAY");
            output=new AtomicFile(path);
            evidence=new JSONObject().put("test_id",UUID.randomUUID().toString()).put("phase",phase)
                .put("workspace_emulator_only",true).put("physical_phone_evidence",false)
                .put("film_animation_created",false).put("passed",false);
            save("checking_native_target");JSONObject caps=call("capabilities");
            require("Render Studio".equals(caps.getString("target_app"))&&"com.rezox.render".equals(caps.getString("target_package")),"WRONG_NATIVE_TARGET");
            publicId=caps.getString("render_public_id");evidence.put("render_public_id",publicId).put("capabilities",caps);
            require(target.getPackageManager().getPackageInfo(target.getPackageName(),0).getLongVersionCode()>=35,"UPGRADED_APK_REQUIRED");
            if(phase.equals("core"))core();else if(phase.equals("assets"))assets();else if(phase.equals("render"))render();else if(phase.equals("configuration"))configuration();else if(phase.equals("launch"))launch();else if(phase.equals("diagnostics"))diagnostics();else if(phase.equals("artist_model"))artistModel();else if(phase.equals("artist_animate"))artistAnimate();else if(phase.equals("artist_preview"))artistRender(false);else if(phase.equals("artist_animation"))artistRender(true);else if(phase.equals("artist_status"))artistStatus();else if(phase.equals("artist_encode"))artistEncode();else status();
            evidence.put("passed",true);save("passed_native_"+phase);code=Activity.RESULT_OK;
        }catch(Throwable error){
            try{if(evidence!=null){evidence.put("error",error.toString()).put("cause",String.valueOf(error.getCause()));save("failed_native_"+phase);}}catch(Exception ignored){}
            result.putString("error",error.toString());
        }finally{if(evidence!=null)result.putString("result",evidence.toString());finish(code,result);}
    }
}
