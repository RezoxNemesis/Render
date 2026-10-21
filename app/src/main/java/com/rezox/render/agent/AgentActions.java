package com.rezox.render.agent;

import android.content.Context;
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
    public AgentActions(Context context) throws Exception {
        List<File> roots = new ArrayList<>();
        File external = context.getExternalFilesDir(null);
        if (external != null) roots.add(new File(external,"Projects"));
        roots.add(new File(context.getFilesDir(),"Projects"));
        projects = new ProjectScope(roots.toArray(new File[0]));
    }
    public static JSONArray capabilities() throws Exception {
        JSONArray out = new JSONArray();
        for (String id : AgentPolicy.ACTIONS.keySet()) {
            JSONObject properties = new JSONObject();
            for (String field : AgentPolicy.ACTIONS.get(id)) {
                JSONObject prop=new JSONObject();
                if(field.equals("offset")||field.equals("limit")){
                    prop.put("type","integer").put("minimum",field.equals("offset")?0:1);
                    prop.put("maximum",field.equals("offset")?Integer.MAX_VALUE:200);
                }else prop.put("type","string").put("pattern","^[a-f0-9]{64}$");
                properties.put(field,prop);
            }
            JSONObject schema = new JSONObject().put("type","object").put("properties",properties)
                .put("additionalProperties",false).put("required",new JSONArray(
                    id.equals("projects.inspect") ? new String[]{"project_id"} : new String[]{}));
            out.put(new JSONObject().put("id",id).put("available",true).put("api_version",1)
                .put("read_only",true).put("cancellation","between_native_calls").put("input_schema",schema));
        }
        for (String id : new String[]{"scene.create","scene.save","mesh.edit","rig.animate","cycles.render","eevee.render"})
            out.put(new JSONObject().put("id",id).put("available",false).put("api_version",1)
                .put("reason","Blender scene/evaluation/render module is not integrated yet"));
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
        if (action.equals("engine.status")) return new JSONObject().put("native_status",RenderNative.engineStatus())
            .put("engineIntegrated",false).put("executed_by","android-native");
        if (action.equals("gpu.info")) return new JSONObject().put("native_status",RenderNative.gpuInfo())
            .put("is_renderer",false).put("executed_by","android-native");
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
