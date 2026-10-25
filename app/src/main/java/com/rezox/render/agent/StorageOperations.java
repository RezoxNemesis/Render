package com.rezox.render.agent;

import android.content.Context;
import android.content.Intent;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Arrays;

/** Typed file operations on the existing authenticated Render/VideoStudio channel. */
public final class StorageOperations {
    public static final String[] NAMES={"storage.capabilities","storage.locations","storage.pick",
        "storage.folder.list","storage.folder.create","storage.document.inspect","storage.import","storage.export","storage.fetch",
        "storage.task.status","storage.task.list","storage.task.pause","storage.task.resume","storage.task.cancel","storage.task.refresh","storage.file.pick","storage.unpack","asset.providers"};
    private StorageOperations(){}
    static boolean supports(String operation){return Arrays.asList(NAMES).contains(operation);}
    public static JSONObject execute(Context c,String operation,JSONObject p)throws Exception{
        if(operation.equals("asset.providers")){
            ProductionBridge.fields(p,"");
            return new JSONObject().put("providers",new JSONArray()
                .put(new JSONObject().put("id","polyhaven").put("name","Poly Haven").put("license","CC0-1.0")
                    .put("license_url","https://polyhaven.com/license").put("kinds",new JSONArray(new String[]{"models","textures","hdris"})))
                .put(new JSONObject().put("id","ambientcg").put("name","AmbientCG").put("license","CC0-1.0")
                    .put("license_url","https://docs.ambientcg.com/license/").put("native_import_kinds",new JSONArray(new String[]{"textures","hdris"}))
                    .put("model_catalog_limit","Upstream model filtering may be unavailable; mismatched materials are excluded"))
                .put(new JSONObject().put("id","owner_files").put("name","Device / connected Drive originals")
                    .put("license","supplied by original source; never assume free licensing")
                    .put("discovery_operation","storage.locations").put("importer_discovery_operation","file.importers")))
                .put("catalogs_are_finite",true).put("varieties","Search query and kind; availability depends on each source")
                .put("metadata_operations",new JSONArray(new String[]{"asset.search","asset.details","asset.preview"}))
                .put("download_operations",new JSONArray(new String[]{"asset.download","asset.download.status","asset.download.pause"}))
                .put("explicit_original_workflow",new JSONArray(new String[]{"storage.import or storage.fetch","storage.unpack for ZIP dependencies","file.inspect","file.import"}))
                .put("native_editor_required_for_this_discovery",false).put("unrestricted_web_or_generative_asset_source",false);
        }
        if(operation.equals("storage.capabilities")){
            ProductionBridge.fields(p,"");JSONArray operations=new JSONArray();
            String[] fields={"","","","location_id,parent_id,offset,limit","location_id,parent_id,name",
                "location_id,document_id","request_id,location_id,document_id,expected_sha256,expected_bytes",
                "request_id,location_id,parent_id,name,category,filename,expected_sha256",
                "request_id,url,name,expected_sha256,expected_bytes,license,license_url",
                "transfer_id","","transfer_id","transfer_id","transfer_id","transfer_id,url","","request_id,filename,expected_sha256",""};
            String[] required={"","","","location_id","location_id,name","location_id,document_id",
                "request_id,location_id,document_id","request_id,location_id,parent_id,name,category,filename,expected_sha256",
                "request_id,url,name,expected_sha256,expected_bytes","transfer_id","","transfer_id","transfer_id","transfer_id",
                "transfer_id,url","","request_id,filename,expected_sha256",""};
            for(int i=0;i<NAMES.length;i++){
                String[] names=fields[i].isEmpty()?new String[0]:fields[i].split(",");JSONObject properties=new JSONObject();
                for(String name:names){
                    JSONObject field=new JSONObject().put("type",Arrays.asList("offset","limit","expected_bytes").contains(name)?"integer":"string");
                    if(name.equals("offset"))field.put("minimum",0).put("maximum",100000);
                    if(name.equals("limit"))field.put("minimum",1).put("maximum",100);
                    if(name.equals("expected_bytes"))field.put("minimum",1).put("maximum",FileTransfers.MAX_BYTES);
                    if(name.equals("expected_sha256"))field.put("pattern","^[a-f0-9]{64}$");
                    if(name.equals("request_id"))field.put("pattern","^[A-Za-z0-9_-]{8,128}$");
                    properties.put(name,field);
                }
                operations.put(new JSONObject().put("operation",NAMES[i]).put("fields",new JSONArray(names))
                    .put("input_schema",new JSONObject().put("type","object").put("properties",properties).put("additionalProperties",false)
                        .put("required",new JSONArray(required[i].isEmpty()?new String[0]:required[i].split(",")))));
            }
            return new JSONObject().put("operations",operations).put("native_editor_required",false)
                .put("workspace_location_id","workspace").put("root_document_id","root")
                .put("external_access","persisted Android system folder grants; storage.pick")
                .put("google_drive","Android document provider if available; or original HTTPS file reference via storage.fetch")
                .put("connector_oauth_is_android_storage_grant",false).put("gallery_browsed",false)
                .put("maximum_file_bytes",FileTransfers.MAX_BYTES).put("maximum_retained_transfers",512)
                .put("import_workflow",new JSONArray(new String[]{"storage.locations","storage.folder.list","storage.import","storage.task.status","file.inspect","file.import"}))
                .put("export_workflow",new JSONArray(new String[]{"project.checkpoint","storage.folder.create","storage.export","storage.task.status"}))
                .put("task_idempotency","reuse request_id with identical payload; poll transfer_id before retry")
                .put("expired_file_reference","storage.task.refresh with same transfer_id and refreshed URL; content digest and size remain fixed")
                .put("final_render_quality_changed",false).put("cloud_rendering",false);
        }
        if(operation.equals("storage.locations")){ProductionBridge.fields(p,"");return StorageDocuments.locations(c);}
        if(operation.equals("storage.pick")||operation.equals("storage.file.pick")){
            ProductionBridge.fields(p,"");c.startActivity(new Intent(c,AgentActivity.class)
                .setAction(operation.equals("storage.pick")?"com.rezox.render.agent.PICK_STORAGE":"com.rezox.render.agent.PICK_FILE").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            return new JSONObject().put("picker_launch_requested",true).put("owner_ui_needed",true)
                .put("storage_grant_completed",false);
        }
        if(operation.equals("storage.folder.list")){
            ProductionBridge.fields(p,"location_id,parent_id,offset,limit");
            return StorageDocuments.list(c,p.getString("location_id"),p.optString("parent_id","root"),
                (int)ProductionBridge.integer(p,"offset",0,100000,0),(int)ProductionBridge.integer(p,"limit",1,100,40));
        }
        if(operation.equals("storage.folder.create")){
            ProductionBridge.fields(p,"location_id,parent_id,name");
            return StorageDocuments.createFolder(c,p.getString("location_id"),p.optString("parent_id","root"),p.getString("name"));
        }
        if(operation.equals("storage.document.inspect")){
            ProductionBridge.fields(p,"location_id,document_id");
            return StorageDocuments.resolve(c,p.getString("location_id"),p.getString("document_id"),false).json();
        }
        if(operation.equals("storage.import")||operation.equals("storage.export")||operation.equals("storage.fetch")||operation.equals("storage.unpack")){
            JSONObject task=FileTransfers.enqueue(c,operation.substring(8),p);
            // A repeated request only observes the retained result; it cannot restart a paused/uncertain transfer.
            return task.optBoolean("already_requested")?task:FileTransferService.request(c,task.getString("transfer_id"));
        }
        if(operation.equals("storage.task.list")){ProductionBridge.fields(p,"");return FileTransfers.list(c);}
        if(operation.equals("storage.task.refresh")){
            ProductionBridge.fields(p,"transfer_id,url");return FileTransfers.refresh(c,p.getString("transfer_id"),p.getString("url"));
        }
        ProductionBridge.fields(p,"transfer_id");String id=p.getString("transfer_id");
        if(operation.equals("storage.task.status"))return FileTransfers.status(c,id);
        String action=operation.substring("storage.task.".length());JSONObject status=FileTransfers.control(c,id,action);
        return action.equals("resume")?FileTransferService.request(c,id):status;
    }
}
