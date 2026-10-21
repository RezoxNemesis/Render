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
    private static void checkArguments(String action, JSONObject args) throws Exception {
        if ("blender.scene.summary".equals(action)) {
            if (args.length() != 0) throw new IllegalArgumentException("UNEXPECTED_ARGUMENT");
            return;
        }
        if (!"blender.object.add_cube".equals(action))
            throw new IllegalArgumentException("NATIVE_BLENDER_ACTION_UNAVAILABLE");
        String name = args.optString("name","Cube");
        if (!name.matches("[A-Za-z][A-Za-z0-9_-]{0,63}"))
            throw new IllegalArgumentException("INVALID_OBJECT_NAME");
        if (args.has("size") && !finite(args.get("size"),0.001,10000))
            throw new IllegalArgumentException("INVALID_CUBE_SIZE");
        if (args.has("location")) {
            Object raw=args.get("location");
            if (!(raw instanceof JSONArray)) throw new IllegalArgumentException("INVALID_CUBE_LOCATION");
            JSONArray xyz=(JSONArray)raw;
            if (xyz.length()!=3) throw new IllegalArgumentException("INVALID_CUBE_LOCATION");
            for(int i=0;i<3;i++) if(!finite(xyz.get(i),-100000,100000))
                throw new IllegalArgumentException("INVALID_CUBE_LOCATION");
        }
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
        JSONObject envelope=new JSONObject().put("id",id).put("action",action)
            .put("args",args).put("deadline",System.currentTimeMillis()/1000+20);
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
        long deadline=SystemClock.elapsedRealtime()+20000;
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
