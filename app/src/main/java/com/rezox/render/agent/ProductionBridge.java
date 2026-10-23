package com.rezox.render.agent;

import com.rezox.render.omega.integration.OmegaOperations;
import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.os.PowerManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/** Stable typed envelope. New operations are validated by Render, not guessed from a version string. */
public final class ProductionBridge {
    public static final String ACTION="production.execute";
    private static final String[] OPS={"capabilities","device.profile","editor.open","screenshot.capture",
        "artifact.read","artifact.export","reference.write","project.create","project.checkpoint",
        "scene.inspect","mesh.create","asset.create","material.assign","group.create","animation.keys","camera.aim",
        "world.configure","instances.plan","instances.create","reference.attach",
        "render.plan","render.step","render.batch","render.status","render.encode","drive.status","drive.backup",
        "render.storage.status","render.job.start","render.job.status","render.job.pause",
        "render.job.export","render.job.export_segment","project.checkpoint_export","native.command.status",
        "asset.search","asset.download","asset.download.status","asset.download.pause","asset.import",
        "render.quality.inspect","render.quality.configure","render.performance.inspect","render.performance.configure"};
    private static final Set<String> OPERATIONS=new HashSet<>(Arrays.asList(OPS));
    private ProductionBridge(){}
    public static void fields(JSONObject p,String allowed)throws Exception {
        Set<String> names=new HashSet<>(Arrays.asList(allowed.split(",")));
        java.util.Iterator<String> it=p.keys();while(it.hasNext())if(!names.contains(it.next()))throw new IllegalArgumentException("UNKNOWN_PRODUCTION_ARGUMENT");
    }
    public static long integer(JSONObject p,String key,long low,long high,long fallback)throws Exception {
        Object value=p.opt(key);
        if(value==null){if(fallback<low||fallback>high)throw new IllegalArgumentException("REQUIRED_INTEGER_MISSING");return fallback;}
        if(!(value instanceof Integer)&&!(value instanceof Long))throw new IllegalArgumentException("INVALID_INTEGER");
        long n=((Number)value).longValue();if(n<low||n>high)throw new IllegalArgumentException("INTEGER_OUT_OF_RANGE");return n;
    }
    public static void validate(JSONObject args)throws Exception {
        fields(args,"operation,payload,target_id");
        if(!(args.opt("operation") instanceof String)||!OPERATIONS.contains(args.getString("operation"))&&!OmegaOperations.isReserved(args.getString("operation")))throw new IllegalArgumentException("PRODUCTION_OPERATION_UNAVAILABLE");
        if(args.has("payload")&&!(args.opt("payload") instanceof JSONObject))throw new IllegalArgumentException("INVALID_PRODUCTION_PAYLOAD");
        if(args.has("target_id")&&(!(args.opt("target_id") instanceof String)||!args.getString("target_id").matches("[a-fA-F0-9-]{36}")))throw new IllegalArgumentException("INVALID_TARGET_ID");
        if(args.toString().getBytes(StandardCharsets.UTF_8).length>131072)throw new IllegalArgumentException("PRODUCTION_REQUEST_TOO_LARGE");
    }
    private static boolean editorReady(Context context){
        return NativeHeartbeat.ready(context);
    }
    public static JSONObject profile(Context context)throws Exception {
        ActivityManager manager=context.getSystemService(ActivityManager.class);ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();
        if(manager!=null)manager.getMemoryInfo(memory);
        JSONObject telemetry=ProductionThermalTelemetry.sample(context);
        return telemetry.put("native_editor_ready",editorReady(context))
            .put("maximum_instance_request",10_000_000).put("ten_million_device_test_passed",false)
            .put("quality_reduction_policy","never_silent")
            .put("render_auto_cooldown_available",true)
            .put("full_desktop_parity_verified",false);
    }
    public static JSONObject execute(Context context,JSONObject args,AtomicBoolean cancelled)throws Exception {
        validate(args);String operation=args.getString("operation");JSONObject p=args.optJSONObject("payload");if(p==null)p=new JSONObject();
        String publicId=new AgentSecrets(context).renderPublicId();
        if(!operation.equals("capabilities")&&!operation.equals("device.profile")){
            if(!publicId.equals(args.optString("target_id","")))throw new IllegalArgumentException("RENDER_TARGET_ID_REQUIRED_OR_MISMATCH");
        }
        if(cancelled.get())throw new IllegalStateException("CANCELLED_BEFORE_NATIVE_START");
        if(operation.equals("capabilities")){
            fields(p,"");JSONArray operations=new JSONArray();for(String op:OPS)operations.put(op);
            return new JSONObject().put("schema_version",1).put("envelope",ACTION).put("operations",operations)
                .put("render_public_id",publicId).put("target_package",context.getPackageName()).put("target_app","Render Studio")
                .put("requires_target_id",true).put("maximum_request_bytes",131072).put("maximum_artifact_chunk_bytes",24576)
                .put("native_editor_ready",editorReady(context)).put("native_window_capture_ready",ProductionCapture.available())
                .put("background_render_running",RenderManualJobs.active())
                .put("android_h264_encoder_available",ProductionVideoEncoder.available()).put("cloud_rendering",false)
                .put("automatic_image_to_3d_provider_installed",false).put("visual_quality_verified",false)
                .put("render_protocol","plan_then_batch_up_to_12_frames_with_cooldown_then_encode_then_export")
                .put("render_batch_max_frames",12).put("free_procedural_asset_presets",17).put("free_assets_native_editable",true)
                .put("thermal_severe_is_safely_paused",true)
                .put("drive_backup_via","user-granted Android Storage Access Framework; cloud storage only")
                .put("drive_folder_granted",ProductionDriveStorage.status(context).getBoolean("folder_granted"))
                .put("user_project_quality_changed",false)
                .put("native_frame_timeout_ms",NativeCommandBudget.FRAME_TIMEOUT_MS)
                .put("background_render_entrypoint","render.job.start")
                .put("asset_catalog","Poly Haven CC0 models, materials and HDRIs")
                .put("asset_catalog_is_infinite",false)
                .put("asset_downloads_keep_requested_resolution",true)
                .put("explicit_quality_configuration",true)
                .put("read_only_native_receipt_recovery","native.command.status")
                .put("omega_reserved_only_not_verified",new JSONArray(OmegaOperations.reserved()))
                .put("omega_capabilities_operation","omega.integration.capabilities");
        }
        if(operation.equals("device.profile")){fields(p,"");return profile(context);}
        if(operation.equals("native.command.status"))return BlenderSpool.inspect(context,p);
        // These operations remain authenticated/target-id scoped by the
        // existing Render/VideoStudio Binder checks above. No filesystem path
        // or arbitrary bpy operator is accepted from a remote command.
        if(operation.equals("render.storage.status")){
            fields(p,"job_id");
            return RenderStorageBudget.forJob(context,p.getString("job_id"));
        }
        if(operation.equals("render.job.status")){
            fields(p,"");
            return RenderLongForegroundService.status(context);
        }
        if(operation.equals("render.job.start")){
            fields(p,"job_id");
            return RenderLongForegroundService.request(context,p.getString("job_id"));
        }
        if(operation.equals("render.job.pause")){
            fields(p,"");
            return RenderLongForegroundService.requestPause(context);
        }
        if(operation.equals("render.job.export")){
            fields(p,"job_id");
            return RenderManualJobs.export(context,p.getString("job_id"));
        }
        if(operation.equals("render.job.export_segment")){
            fields(p,"job_id,index");
            return RenderManualJobs.exportSegment(context,p.getString("job_id"),
                (int)integer(p,"index",0,100000,-1));
        }
        if(operation.equals("project.checkpoint_export")){
            fields(p,"name");
            String name=p.optString("name","Project");
            if(!name.matches("[A-Za-z][A-Za-z0-9_-]{0,63}"))
                throw new IllegalArgumentException("INVALID_PROJECT_NAME");
            JSONObject nativeArgs=new JSONObject().put("operation","project.checkpoint")
                .put("payload",new JSONObject().put("name",name));
            JSONObject checkpoint;
            try(NativeWakeGuard wake=NativeWakeGuard.acquire(context,"blender.project.save_copy")){
                checkpoint=new BlenderSpool(context).execute(
                    "blender.production.execute",nativeArgs,cancelled);
            }
            if(!"Projects".equals(checkpoint.optString("category"))||
                !checkpoint.optString("filename").endsWith(".blend")||
                !checkpoint.optString("sha256").matches("[a-f0-9]{64}"))
                throw new IllegalStateException("NATIVE_PROJECT_CHECKPOINT_UNVERIFIED");
            JSONObject result=new JSONObject().put("checkpoint",checkpoint)
                .put("checkpoint_saved",true).put("source_project_unchanged",true);
            try{
                JSONObject exported=ProductionFiles.export(context,new JSONObject()
                    .put("category","Projects")
                    .put("filename",checkpoint.getString("filename"))
                    .put("expected_sha256",checkpoint.getString("sha256")));
                result.put("export",exported).put("downloads_verified",true);
            }catch(Exception problem){
                // Crucially, the native checkpoint remains in app-private
                // Projects. Never claim its successful export or redo the
                // Blender save blindly when a file provider fails.
                result.put("downloads_verified",false)
                    .put("export_retry_operation","artifact.export")
                    .put("export_error",problem.getClass().getSimpleName());
            }
            return result.put("native_execution_verified",true)
                .put("quality_reduced",false);
        }
        // The frozen Omega IDs are transport-reserved only: the native registry
        // checks which reviewed phase modules are actually installed/enabled.
        // No arbitrary operator or script name crosses the Binder/spool boundary.
        if(OmegaOperations.isReserved(operation)){
            if(!editorReady(context))throw new IllegalStateException("BLENDER_EDITOR_NOT_RUNNING");
            JSONObject nativeArgs=new JSONObject().put("operation",operation)
                .put("payload",p)
                .put("available_memory_bytes",profile(context).optLong("available_memory_bytes",0L));
            try(NativeWakeGuard wake=NativeWakeGuard.acquire(context,"omega.dispatch")){
                return new BlenderSpool(context).execute("omega.dispatch",nativeArgs,cancelled);
            }
        }
        if(operation.equals("editor.open")){
            fields(p,"");Intent intent=new Intent().setClassName(context,"com.rezox.render.EditorLaunchActivity").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            intent.putExtra(com.rezox.render.omega.engine.EngineStartupRecovery.EXTRA_REQUEST,
                com.rezox.render.omega.engine.EngineStartupRecovery.request(context));
            context.startActivity(intent);
            return new JSONObject().put("launch_requested",true).put("editor_ready",editorReady(context))
                .put("completed_editor_start",false).put("note","Android may require the owner to foreground Render; verify native heartbeat before editing.");
        }
        if(operation.equals("screenshot.capture")){fields(p,"");return ProductionCapture.capture(context);}
        if(operation.equals("artifact.read"))return ProductionFiles.read(context,p);
        if(operation.equals("artifact.export"))return ProductionFiles.export(context,p);
        if(operation.equals("reference.write"))return ProductionFiles.writeReference(context,p);
        if(operation.equals("drive.status")){fields(p,"");return ProductionDriveStorage.status(context);}
        if(operation.equals("drive.backup"))return ProductionDriveStorage.backup(context,p);
        if(operation.equals("render.batch"))return ProductionBatch.advance(context,p,cancelled);
        if(operation.equals("render.status")){
            fields(p,"job_id");File manifest=ProductionFiles.file(context,p.getString("job_id"),"manifest.json");
            if(!manifest.isFile()||manifest.length()>16*1024*1024)throw new IllegalArgumentException("RENDER_MANIFEST_UNAVAILABLE");
            JSONObject m=new JSONObject(new String(Files.readAllBytes(manifest.toPath()),StandardCharsets.UTF_8));
            return new JSONObject().put("job_id",m.getString("job_id")).put("state",m.getString("state"))
                .put("completed_frames",m.getJSONObject("frames").length()).put("spec",m.getJSONObject("spec"))
                .put("next_frame",m.getInt("next_frame")).put("quality_reduced",false)
                .put("video",m.optJSONObject("video"))
                .put("thermal",ProductionThermalTelemetry.sample(context))
                .put("supports_resume",true)
                .put("batch_operation","render.batch");
        }
        JSONObject device=profile(context);
        ProductionThermalPolicy.Decision gate=ProductionThermalPolicy.evaluate(
            device.optInt("thermal_status",-1),device.optBoolean("low_memory"),
            device.optLong("available_memory_bytes"),cancelled.get());
        if(operation.equals("render.encode")){
            fields(p,"job_id");
            if(!gate.renderAllowed)
                return ProductionBatch.jobStatus(context,p.getString("job_id")).put("paused",true)
                    .put("reason",gate.reason).put("thermal",device).put("video_created",false);
            try(NativeWakeGuard wake=NativeWakeGuard.acquire(context,"blender.scene.render_video")){
                return ProductionVideoEncoder.encode(context,p.getString("job_id"),cancelled);
            }
        }
        if(operation.equals("render.step")||operation.equals("instances.create")){
            if(!gate.renderAllowed){
                if(operation.equals("render.step")){
                    fields(p,"job_id");
                    return ProductionBatch.jobStatus(context,p.getString("job_id"))
                        .put("paused",true).put("reason",gate.reason).put("thermal",device)
                        .put("retry_after_seconds",30);
                }
                throw new IllegalStateException(gate.reason);
            }
        }
        JSONObject nativePayload=new JSONObject(p.toString());
        if(operation.equals("instances.plan")||operation.equals("instances.create")){
            if(p.has("available_memory_bytes"))throw new IllegalArgumentException("DEVICE_MEMORY_IS_NATIVE_ONLY");
            nativePayload.put("available_memory_bytes",device.getLong("available_memory_bytes"));
        }
        JSONObject nativeArgs=new JSONObject().put("operation",operation).put("payload",nativePayload);
        try(NativeWakeGuard wake=NativeWakeGuard.acquire(context,operation.equals("render.step")?"blender.production.render_frame":"blender.production.execute")){
            return new BlenderSpool(context).execute("blender.production.execute",nativeArgs,cancelled);
        }
    }
}
