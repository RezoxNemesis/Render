package com.rezox.render.agent;

import android.content.Context;
import android.os.SystemClock;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

/** App-private native bpy main-thread command spool. Never executes Python text. */
public final class BlenderSpool {
    public static final class RecoveryRequired extends Exception {
        RecoveryRequired(String code) { super(code); }
    }
    private final File root;
    public BlenderSpool(Context context) {
        root = new File(context.getFilesDir(), "render_bpy_jobs");
    }
    private static boolean finite(Object value, double low, double high) {
        if (!(value instanceof Number)) return false;
        double number = ((Number)value).doubleValue();
        return Double.isFinite(number) && number >= low && number <= high;
    }
    private static void vector(JSONObject args,String key,double low,double high,String code) throws Exception {
        Object raw=args.get(key);
        if(!(raw instanceof JSONArray))throw new IllegalArgumentException(code);
        JSONArray triple=(JSONArray)raw;
        if(triple.length()!=3)throw new IllegalArgumentException(code);
        for(int i=0;i<3;i++)if(!finite(triple.get(i),low,high))
            throw new IllegalArgumentException(code);
    }
    private static void name(JSONObject args,boolean required)throws Exception {
        if(required&&!args.has("name"))throw new IllegalArgumentException("INVALID_OBJECT_NAME");
        String n=args.optString("name","Cube");
        if(!n.matches("[A-Za-z][A-Za-z0-9_-]{0,63}"))
            throw new IllegalArgumentException("INVALID_OBJECT_NAME");
    }
    private static void frame(JSONObject args)throws Exception {
        Object raw=args.get("frame");
        if(!(raw instanceof Integer)||((Integer)raw)<1||((Integer)raw)>100000)
            throw new IllegalArgumentException("INVALID_FRAME");
    }
    private static void checkArguments(String action, JSONObject args) throws Exception {
        if("blender.scene.summary".equals(action)){
            if(args.length()!=0)throw new IllegalArgumentException("UNEXPECTED_ARGUMENT");
            return;
        }
        if("blender.project.save_copy".equals(action)){
            if(args.length()!=0)throw new IllegalArgumentException("UNEXPECTED_ARGUMENT");
            return;
        }
        if("blender.scene.set_frame".equals(action)){
            if(args.length()!=1)throw new IllegalArgumentException("UNEXPECTED_ARGUMENT");
            frame(args);return;
        }
        if("blender.object.add_cube".equals(action)){
            name(args,false);
            if(args.has("size")&&!finite(args.get("size"),0.001,10000))
                throw new IllegalArgumentException("INVALID_CUBE_SIZE");
            if(args.has("location"))vector(args,"location",-100000,100000,"INVALID_CUBE_LOCATION");
            return;
        }
        if("blender.object.set_transform".equals(action)){
            name(args,true);
            if(!args.has("location")&&!args.has("rotation_euler")&&!args.has("scale"))
                throw new IllegalArgumentException("TRANSFORM_FIELD_REQUIRED");
            if(args.has("location"))vector(args,"location",-100000,100000,"INVALID_OBJECT_LOCATION");
            if(args.has("rotation_euler"))vector(args,"rotation_euler",-1000,1000,"INVALID_OBJECT_ROTATION");
            if(args.has("scale"))vector(args,"scale",0.001,10000,"INVALID_OBJECT_SCALE");
            return;
        }
        if("blender.object.keyframe".equals(action)){
            name(args,true);frame(args);
            String path=args.getString("data_path");
            if(!path.equals("location")&&!path.equals("rotation_euler")&&!path.equals("scale"))
                throw new IllegalArgumentException("INVALID_KEYFRAME_PATH");
            vector(args,"value",path.equals("scale")?0.001:
                path.equals("rotation_euler")?-1000:-100000,
                path.equals("scale")?10000:path.equals("rotation_euler")?1000:100000,
                "INVALID_KEYFRAME_VALUE");
            return;
        }
        if("blender.object.add_primitive".equals(action)){
            if(args.has("name"))name(args,true);
            if(args.has("kind")&&!java.util.Arrays.asList("UV_SPHERE","ICO_SPHERE","CYLINDER","CONE","PLANE","TORUS")
                .contains(args.getString("kind")))throw new IllegalArgumentException("INVALID_PRIMITIVE_KIND");
            if(args.has("size")&&!finite(args.get("size"),0.001,10000))
                throw new IllegalArgumentException("INVALID_PRIMITIVE_SIZE");
            if(args.has("location"))vector(args,"location",-100000,100000,"INVALID_PRIMITIVE_LOCATION");
            return;
        }
        if("blender.object.add_camera".equals(action)){
            if(args.has("name"))name(args,true);
            if(args.has("location"))vector(args,"location",-100000,100000,"INVALID_CAMERA_LOCATION");
            if(args.has("rotation_euler"))vector(args,"rotation_euler",-1000,1000,"INVALID_CAMERA_ROTATION");
            return;
        }
        if("blender.object.add_light".equals(action)){
            if(args.has("name"))name(args,true);
            if(args.has("light_type")&&!java.util.Arrays.asList("POINT","SUN","SPOT","AREA")
                .contains(args.getString("light_type")))throw new IllegalArgumentException("INVALID_LIGHT_KIND");
            if(args.has("location"))vector(args,"location",-100000,100000,"INVALID_LIGHT_LOCATION");
            if(args.has("color"))vector(args,"color",0,1,"INVALID_LIGHT_COLOR");
            if(args.has("energy")&&!finite(args.get("energy"),0,10000000))
                throw new IllegalArgumentException("INVALID_LIGHT_ENERGY");
            return;
        }
        if("blender.object.modifier_add".equals(action)){
            name(args,true);
            if(!java.util.Arrays.asList("SUBSURF","BEVEL","SOLIDIFY","MIRROR")
                .contains(args.getString("modifier_type")))
                throw new IllegalArgumentException("INVALID_MODIFIER_TYPE");
            if(args.has("levels")){
                Object value=args.get("levels");
                if(!(value instanceof Integer)||(Integer)value<0||(Integer)value>6)
                    throw new IllegalArgumentException("INVALID_MODIFIER_LEVEL");
            }
            if(args.has("width")&&!finite(args.get("width"),0,1000))
                throw new IllegalArgumentException("INVALID_MODIFIER_WIDTH");
            return;
        }
        if("blender.material.assign".equals(action)){
            name(args,true);
            if(args.has("material_name")){
                String material=args.getString("material_name");
                if(!material.matches("[A-Za-z][A-Za-z0-9_-]{0,63}"))
                    throw new IllegalArgumentException("INVALID_MATERIAL_NAME");
            }
            if(args.has("color"))vector(args,"color",0,1,"INVALID_MATERIAL_COLOR");
            if(args.has("metallic")&&!finite(args.get("metallic"),0,1))
                throw new IllegalArgumentException("INVALID_MATERIAL_SURFACE");
            if(args.has("roughness")&&!finite(args.get("roughness"),0,1))
                throw new IllegalArgumentException("INVALID_MATERIAL_SURFACE");
            return;
        }
        if("blender.scene.render_settings".equals(action)){
            if(args.length()==0)throw new IllegalArgumentException("RENDER_SETTINGS_REQUIRED");
            if(args.has("denoising") && !(args.get("denoising") instanceof Boolean))
                throw new IllegalArgumentException("INVALID_DENOISING_SETTING");
            for(String field:new String[]{"resolution_x","resolution_y","samples"}){
                if(args.has(field)){
                    Object value=args.get(field);
                    int minimum=field.equals("samples")?1:16;
                    int maximum=field.equals("samples")?4096:16384;
                    if(!(value instanceof Integer)||(Integer)value<minimum||(Integer)value>maximum)
                        throw new IllegalArgumentException("INVALID_RENDER_SETTINGS");
                }
            }
            if(args.has("engine")&&!java.util.Arrays.asList(
                "CYCLES","BLENDER_EEVEE","BLENDER_EEVEE_NEXT","BLENDER_WORKBENCH")
                .contains(args.getString("engine")))
                throw new IllegalArgumentException("INVALID_RENDER_ENGINE");
            return;
        }
        if("blender.scene.render_still".equals(action)){
            if(args.length()!=0)throw new IllegalArgumentException("UNEXPECTED_ARGUMENT");
            return;
        }
        if ("blender.scene.populate_lively".equals(action) ||
            "blender.scene.render_video".equals(action)) {
            if (args.length()!=0) throw new IllegalArgumentException("UNEXPECTED_ARGUMENT");
            return;
        }
        if ("blender.project.restore_scene".equals(action)) {
            if (args.length()!=1 || !args.has("filename") ||
                    !args.getString("filename").matches("Render_[a-f0-9]{32}\\.blend"))
                throw new IllegalArgumentException("INVALID_SAVED_PROJECT_FILENAME");
            return;
        }
        throw new IllegalArgumentException("NATIVE_BLENDER_ACTION_UNAVAILABLE");
    }
    public JSONObject execute(String action, JSONObject args, AtomicBoolean cancelled) throws Exception {
        checkArguments(action,args);
        if (cancelled.get()) throw new IllegalStateException("CANCELLED_BEFORE_NATIVE_START");
        File pending=new File(root,"pending");
        File working=new File(root,"working");
        File results=new File(root,"results");
        if (!pending.isDirectory() && !pending.mkdirs()) throw new IllegalStateException("CANNOT_CREATE_NATIVE_QUEUE");
        if (!working.isDirectory() && !working.mkdirs()) throw new IllegalStateException("CANNOT_CREATE_NATIVE_QUEUE");
        if (!results.isDirectory() && !results.mkdirs()) throw new IllegalStateException("CANNOT_CREATE_NATIVE_QUEUE");
        File ready=new File(root,"ready");
        if (!ready.isFile() || System.currentTimeMillis()-ready.lastModified()>15000)
            throw new IllegalStateException("BLENDER_EDITOR_NOT_RUNNING");
        String id=UUID.randomUUID().toString().replace("-","");
        File request=new File(pending,id+".json");
        File claimed=new File(working,id+".json");
        File resultFile=new File(results,id+".json");
        long timeoutMillis=action.equals("blender.scene.render_video") ? 1800000L :
            action.equals("blender.scene.render_still") ? 480000L :
            action.equals("blender.project.save_copy") ? 120000L : 20000L;
        JSONObject envelope=new JSONObject().put("id",id).put("action",action)
            .put("args",args).put("deadline",System.currentTimeMillis()/1000+timeoutMillis/1000);
        byte[] contents=envelope.toString().getBytes(StandardCharsets.UTF_8);
        if(contents.length>16384)throw new IllegalArgumentException("NATIVE_COMMAND_TOO_LARGE");
        File temporary=File.createTempFile("render-",".part",pending);
        try(FileOutputStream output=new FileOutputStream(temporary)) {
            output.write(contents);output.getFD().sync();
        }
        try {Files.move(temporary.toPath(),request.toPath(),StandardCopyOption.ATOMIC_MOVE);}
        catch(java.nio.file.AtomicMoveNotSupportedException e) {
            Files.move(temporary.toPath(),request.toPath());
        }
        long deadline=SystemClock.elapsedRealtime()+timeoutMillis;
        while(SystemClock.elapsedRealtime()<deadline){
            if(resultFile.isFile()){
                if(resultFile.length()>65536)throw new IllegalStateException("BLENDER_RESULT_TOO_LARGE");
                byte[] bytes=Files.readAllBytes(resultFile.toPath());
                resultFile.delete();
                JSONObject reply=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
                if(!id.equals(reply.optString("id")))throw new RecoveryRequired("BLENDER_RESULT_ID_MISMATCH");
                if(!"succeeded".equals(reply.optString("state")))
                    throw new IllegalStateException(reply.optString("error","BLENDER_NATIVE_ACTION_FAILED"));
                JSONObject result=reply.getJSONObject("result");
                result.put("bridge","Render app-private bpy main-thread executor");
                result.put("native_execution_verified",true);
                return result;
            }
            if(cancelled.get()){
                if(request.delete())throw new IllegalStateException("CANCELLED_BEFORE_NATIVE_START");
                if(claimed.isFile())throw new RecoveryRequired("NATIVE_EXECUTION_OUTCOME_UNCERTAIN");
                throw new RecoveryRequired("NATIVE_EXECUTION_OUTCOME_UNCERTAIN");
            }
            Thread.sleep(150);
        }
        // A command may have been taken by Blender without an acknowledgment.
        request.delete();
        throw new RecoveryRequired("BLENDER_NATIVE_TIMEOUT_RECOVERY_REQUIRED");
    }
}
