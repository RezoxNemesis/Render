package com.rezox.render.agent;

import android.content.Context;
import android.content.ComponentName;
import android.content.pm.PackageManager;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

/** Typed action boundary: future modules extend this registry, never a remote shell. */
public final class AgentActions {
    private final ProjectScope projects;
    private final Context context;
    private static boolean hasFullBlender(Context context) {
        if(context==null)return false;
        try{ context.getPackageManager().getActivityInfo(
            new ComponentName(context,"org.blender.blender.BlenderActivity"),0); return true; }
        catch(PackageManager.NameNotFoundException e){return false;}
    }
    public AgentActions(Context context) throws Exception {
        this.context=context.getApplicationContext();
        List<File> roots = new ArrayList<>();
        File external = context.getExternalFilesDir(null);
        if (external != null) roots.add(new File(external,"Projects"));
        roots.add(new File(context.getFilesDir(),"Projects"));
        projects = new ProjectScope(roots.toArray(new File[0]));
    }
    public static JSONArray capabilities() throws Exception {return capabilities(null);}
    public static JSONArray capabilities(Context context) throws Exception {
        final boolean fullBlender=hasFullBlender(context);
        JSONArray out = new JSONArray();
        for (String id : AgentPolicy.ACTIONS.keySet()) {
            JSONObject properties = new JSONObject();
            for (String field : AgentPolicy.ACTIONS.get(id)) {
                JSONObject prop=new JSONObject();
                if(field.equals("offset")||field.equals("limit")){
                    prop.put("type","integer").put("minimum",field.equals("offset")?0:1);
                    prop.put("maximum",field.equals("offset")?Integer.MAX_VALUE:200);
                }else if(field.equals("name")){
                    prop.put("type","string").put("pattern","^[A-Za-z][A-Za-z0-9_-]{0,63}$");
                }else if(field.equals("size")){
                    prop.put("type","number").put("minimum",0.001).put("maximum",10000);
                }else if(field.equals("frame")){
                    prop.put("type","integer").put("minimum",1).put("maximum",100000);
                }else if(field.equals("data_path")){
                    prop.put("type","string").put("enum",new JSONArray(
                        new String[]{"location","rotation_euler","scale"}));
                }else if(field.equals("kind")){
                    prop.put("type","string").put("enum",new JSONArray(new String[]{
                        "UV_SPHERE","ICO_SPHERE","CYLINDER","CONE","PLANE","TORUS"}));
                }else if(field.equals("light_type")){
                    prop.put("type","string").put("enum",new JSONArray(new String[]{
                        "POINT","SUN","SPOT","AREA"}));
                }else if(field.equals("modifier_type")){
                    prop.put("type","string").put("enum",new JSONArray(new String[]{
                        "SUBSURF","BEVEL","SOLIDIFY","MIRROR"}));
                }else if(field.equals("denoising")){
                    prop.put("type","boolean");
                }else if(field.equals("engine")){
                    prop.put("type","string").put("enum",new JSONArray(new String[]{
                        "CYCLES","BLENDER_EEVEE","BLENDER_EEVEE_NEXT","BLENDER_WORKBENCH"}));
                }else if(field.equals("material_name")){
                    prop.put("type","string").put("pattern","^[A-Za-z][A-Za-z0-9_-]{0,63}$");
                }else if(field.equals("resolution_x")||field.equals("resolution_y")){
                    prop.put("type","integer").put("minimum",16).put("maximum",16384);
                }else if(field.equals("samples")){
                    prop.put("type","integer").put("minimum",1).put("maximum",4096);
                }else if(field.equals("levels")){
                    prop.put("type","integer").put("minimum",0).put("maximum",6);
                }else if(field.equals("energy")){
                    prop.put("type","number").put("minimum",0).put("maximum",10000000);
                }else if(field.equals("metallic")||field.equals("roughness")){
                    prop.put("type","number").put("minimum",0).put("maximum",1);
                }else if(field.equals("width")){
                    prop.put("type","number").put("minimum",0).put("maximum",1000);
                }else if(field.equals("color")){
                    prop.put("type","array").put("minItems",3).put("maxItems",3)
                        .put("items",new JSONObject().put("type","number").put("minimum",0).put("maximum",1));
                }else if(field.equals("location") || field.equals("rotation_euler")
                        || field.equals("scale") || field.equals("value")){
                    double minimum = field.equals("scale") ? 0.001 :
                        field.equals("rotation_euler") ? -1000 : -100000;
                    double maximum = field.equals("scale") ? 10000 :
                        field.equals("rotation_euler") ? 1000 : 100000;
                    prop.put("type","array").put("minItems",3).put("maxItems",3)
                        .put("items",new JSONObject().put("type","number")
                        .put("minimum",minimum).put("maximum",maximum));
                }else prop.put("type","string").put("pattern","^[a-f0-9]{64}$");
                properties.put(field,prop);
            }
            String[] required = id.equals("projects.inspect") ? new String[]{"project_id"} :
                id.equals("blender.project.restore_scene") ? new String[]{"project_id"} :
                id.equals("blender.scene.set_frame") ? new String[]{"frame"} :
                id.equals("blender.object.set_transform") ? new String[]{"name"} :
                id.equals("blender.object.keyframe") ?
                    new String[]{"name","frame","data_path","value"} :
                id.equals("blender.object.modifier_add") ?
                    new String[]{"name","modifier_type"} :
                id.equals("blender.material.assign") ? new String[]{"name"} : new String[]{};
            JSONObject schema = new JSONObject().put("type","object").put("properties",properties)
                .put("additionalProperties",false).put("required",new JSONArray(required));
            if (id.equals("blender.scene.render_settings")) {
                JSONArray anyOf = new JSONArray();
                for (String field : new String[]{"resolution_x","resolution_y","samples","engine","denoising"})
                    anyOf.put(new JSONObject().put("required",new JSONArray(new String[]{field})));
                schema.put("anyOf",anyOf);
            }
            if (id.equals("blender.object.set_transform")) {
                JSONArray anyOf = new JSONArray();
                for (String field : new String[]{"location","rotation_euler","scale"})
                    anyOf.put(new JSONObject().put("required",new JSONArray(new String[]{field})));
                schema.put("anyOf",anyOf);
            }
            boolean bpy=id.startsWith("blender.");
            boolean available=!bpy||fullBlender;
            JSONObject descriptor=new JSONObject().put("id",id).put("available",available).put("api_version",1)
                .put("read_only",!bpy || id.equals("blender.scene.summary"))
                .put("cancellation","between_native_calls").put("input_schema",schema);
            if(bpy&&!available)descriptor.put("reason","Full native Blender editor not packaged in this Android build");
            if(bpy&&available)descriptor.put("requires","Open full Blender editor and wait for bpy timer startup");
            out.put(descriptor);
        }
        for (String id : new String[]{"scene.create","scene.save","mesh.edit","rig.animate","cycles.render","eevee.render"})
            out.put(new JSONObject().put("id",id).put("available",false).put("api_version",1)
                .put("reason","Not connected to native bpy action dispatcher yet"));
        return out;
    }
    private static void checkCancelled(AtomicBoolean cancelled) {
        if (cancelled.get()) throw new IllegalStateException("CANCELLED_BEFORE_NEXT_STEP");
    }
    public JSONObject execute(JSONObject command, AtomicBoolean cancelled) throws Exception {
        JSONObject args = command.getJSONObject("args");
        Set<String> fields = new HashSet<>(); args.keys().forEachRemaining(fields::add);
        String action = command.getString("action");
        AgentPolicy.validate(command.getString("request_id"),command.getInt("api_version"),action,fields);
        checkCancelled(cancelled);
        if (action.equals("engine.status")) {
            JSONObject result=new JSONObject().put("native_status",RenderNative.engineStatus())
                .put("engineIntegrated",false).put("fullBlenderEditorBundled",hasFullBlender(context))
                .put("executed_by","android-native");
            try {
                android.content.pm.PackageInfo installed=context.getPackageManager()
                    .getPackageInfo(context.getPackageName(),0);
                result.put("installedVersionName",installed.versionName);
                result.put("installedVersionCode",installed.getLongVersionCode());
            } catch(PackageManager.NameNotFoundException missing) {
                result.put("installedVersionName","unavailable");
            }
            // A recent Blender Python timer heartbeat proves that typed bpy
            // commands can be delivered; a bundled editor alone does not.
            File ready=new File(context.getFilesDir(),"render_bpy_jobs/ready");
            long age=System.currentTimeMillis()-ready.lastModified();
            result.put("editorCommandBridgeReady",
                ready.isFile() && age>=0 && age<15000);
            return result;
        }
        if (action.equals("gpu.info")) return new JSONObject().put("native_status",RenderNative.gpuInfo())
            .put("is_renderer",false).put("executed_by","android-native");
        if (action.startsWith("blender.")) {
            if (!hasFullBlender(context)) throw new IllegalStateException("BLENDER_ENGINE_NOT_INSTALLED");
            if (action.equals("blender.project.restore_scene")) {
                File saved = projects.find(args.getString("project_id"));
                File owned = new File(context.getFilesDir(),"Projects").getCanonicalFile();
                if (!owned.equals(saved.getCanonicalFile().getParentFile())
                        || !saved.getName().matches("Render_[a-f0-9]{32}\\.blend"))
                    throw new IllegalArgumentException("PROJECT_NOT_RENDER_CHECKPOINT");
                if (args.has("expected_sha256")) {
                    String expected=args.getString("expected_sha256");
                    if (!expected.matches("[a-f0-9]{64}"))
                        throw new IllegalArgumentException("INVALID_PROJECT_HASH");
                    MessageDigest md=MessageDigest.getInstance("SHA-256");
                    try(FileInputStream stream=new FileInputStream(saved)) {
                        byte[] buffer=new byte[65536]; int n;
                        while((n=stream.read(buffer))!=-1) {
                            checkCancelled(cancelled);
                            md.update(buffer,0,n);
                        }
                    }
                    if (!AgentPolicy.hex(md.digest()).equals(expected))
                        throw new IllegalArgumentException("PROJECT_REVISION_CONFLICT");
                }
                JSONObject internal=new JSONObject().put("filename",saved.getName());
                JSONObject restored=new BlenderSpool(context).execute(action,internal,cancelled);
                return restored.put("restored_project_id",args.getString("project_id"));
            }
            JSONObject result = new BlenderSpool(context).execute(action,args,cancelled);
            if (action.equals("blender.project.save_copy")) {
                for (ProjectScope.Entry entry : projects.entries()) {
                    if (entry.file.getName().equals(result.getString("filename"))) {
                        result.put("project_id",entry.id);
                        return result;
                    }
                }
                throw new IllegalStateException("SAVED_PROJECT_NOT_INDEXED");
            }
            if (action.equals("blender.scene.render_video")) {
                try { return RenderVideoExport.publish(context,result); }
                catch (Exception exportError) {
                    // The native MP4 still exists. Report export failure without
                    // lying about whether Blender rendered it.
                    return result.put("android_downloads_export_warning","DOWNLOAD_EXPORT_FAILED");
                }
            }
            return result;
        }
        if (action.equals("projects.list")) {
            int offset = args.has("offset") ? strictInt(args,"offset") : 0;
            int limit = args.has("limit") ? strictInt(args,"limit") : 50;
            if (offset < 0 || limit < 1 || limit > 200) throw new IllegalArgumentException("INVALID_PAGE");
            List<ProjectScope.Entry> all = projects.entries(); JSONArray page = new JSONArray();
            for (int i=offset; i<all.size() && i-offset<limit; i++) {
                checkCancelled(cancelled); ProjectScope.Entry e=all.get(i);
                page.put(new JSONObject().put("project_id",e.id).put("name",e.file.getName())
                    .put("bytes",e.file.length()).put("modified",e.file.lastModified()));
            }
            long next = (long)offset + page.length();
            return new JSONObject().put("projects",page).put("total",all.size())
                .put("next_offset",next < all.size() ? next : JSONObject.NULL);
        }
        Object projectId=args.get("project_id");
        if (!(projectId instanceof String)) throw new IllegalArgumentException("INVALID_PROJECT_ID");
        File file = projects.find((String)projectId);
        long initialSize=file.length(), initialModified=file.lastModified();
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        try(FileInputStream in=new FileInputStream(file)) {
            byte[] buffer=new byte[65536]; int n;
            while((n=in.read(buffer))!=-1) {checkCancelled(cancelled); md.update(buffer,0,n);}
        }
        String hash=AgentPolicy.hex(md.digest());
        if(args.has("expected_sha256") && (!(args.get("expected_sha256") instanceof String) || !hash.equals(args.getString("expected_sha256"))))
            throw new IllegalArgumentException("PROJECT_REVISION_CONFLICT");
        checkCancelled(cancelled);
        JSONObject nativeResult=new JSONObject(RenderNative.inspectProject(file.getAbsolutePath()));
        if(file.length()!=initialSize || file.lastModified()!=initialModified)
            throw new IllegalStateException("PROJECT_CHANGED_DURING_INSPECTION");
        return new JSONObject().put("project_id",projectId).put("sha256",hash)
            .put("native_result",nativeResult).put("executed_by","android-native");
    }
    private static int strictInt(JSONObject object,String key)throws Exception {
        Object value=object.get(key);
        if (!(value instanceof Integer)) throw new IllegalArgumentException("INVALID_INTEGER");
        return (Integer)value;
    }
}
