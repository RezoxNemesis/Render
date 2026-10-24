package com.rezox.render.agent;

import android.content.Context;
import android.content.ContentResolver;
import android.content.UriPermission;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.webkit.MimeTypeMap;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;

/** Opaque handles to Render's workspace or explicit Android SAF grants. Never Gallery or raw client paths. */
public final class StorageDocuments {
    private static final String PREF="render_storage_documents_v1";
    public static final int PICK_FILE=702;
    private StorageDocuments(){}
    public static File workspace(Context c)throws IOException{
        File root=new File(c.getFilesDir(),"Workspace");
        if(Files.isSymbolicLink(root.toPath())||(!root.isDirectory()&&!root.mkdirs()))
            throw new IOException("WORKSPACE_UNAVAILABLE");
        return root.getCanonicalFile();
    }
    public static String name(String name){
        if(name==null||name.isEmpty()||name.length()>120||!name.equals(name.trim())||name.equals(".")||name.equals("..")
                ||name.contains("/")||name.contains("\\"))throw new IllegalArgumentException("INVALID_DOCUMENT_NAME");
        for(int i=0;i<name.length();i++)if(Character.isISOControl(name.charAt(i)))throw new IllegalArgumentException("INVALID_DOCUMENT_NAME");
        return name;
    }
    public static final class Node {
        public final String location,id,name,mime;
        public final long bytes,modified;
        final File file;
        final Uri uri;
        Node(String location,String id,String name,String mime,long bytes,long modified,File file,Uri uri){
            this.location=location;this.id=id;this.name=name;this.mime=mime;this.bytes=bytes;this.modified=modified;this.file=file;this.uri=uri;
        }
        public boolean directory(){return DocumentsContract.Document.MIME_TYPE_DIR.equals(mime);}
        public JSONObject json()throws Exception{return new JSONObject().put("location_id",location).put("document_id",id)
            .put("name",name).put("mime_type",mime).put("directory",directory()).put("bytes",bytes).put("modified_at_ms",modified);}
    }
    private static Uri tree(Context c,String location,boolean write)throws Exception{
        if(location==null||!location.matches("[a-f0-9]{32}"))throw new IllegalArgumentException("UNKNOWN_STORAGE_LOCATION");
        for(UriPermission grant:c.getContentResolver().getPersistedUriPermissions()){
            Uri uri=grant.getUri();
            if((DocumentsContract.isTreeUri(uri)||DocumentsContract.isDocumentUri(c,uri))&&location.equals(locationId(uri))&&grant.isReadPermission()){
                if(write&&!grant.isWritePermission())throw new IOException("STORAGE_LOCATION_READ_ONLY");
                return uri;
            }
        }
        throw new IOException("STORAGE_GRANT_MISSING_OR_REVOKED");
    }
    private static String locationId(Uri uri){return AgentPolicy.sha256(uri.toString()).substring(0,32);}
    private static String bind(Context c,String location,String value)throws Exception{
        String id=AgentPolicy.sha256(location+"|"+value).substring(0,32);
        JSONObject row=new JSONObject().put("location",location).put("value",value);
        android.content.SharedPreferences prefs=c.getSharedPreferences(PREF,Context.MODE_PRIVATE);
        if(row.toString().equals(prefs.getString(id,null)))return id;
        if(!prefs.edit().putString(id,row.toString()).commit())
            throw new IOException("STORAGE_HANDLE_NOT_PERSISTED");
        return id;
    }
    private static String value(Context c,String location,String id)throws Exception{
        if(id==null||!id.matches("[a-f0-9]{32}"))throw new IllegalArgumentException("UNKNOWN_DOCUMENT_HANDLE");
        String raw=c.getSharedPreferences(PREF,Context.MODE_PRIVATE).getString(id,null);
        if(raw==null)throw new IllegalArgumentException("UNKNOWN_DOCUMENT_HANDLE");
        JSONObject row=new JSONObject(raw);
        if(!location.equals(row.getString("location")))throw new IllegalArgumentException("DOCUMENT_LOCATION_MISMATCH");
        return row.getString("value");
    }
    private static File local(Context c,File file)throws IOException{
        File root=workspace(c),canonical=file.getCanonicalFile();
        if(Files.isSymbolicLink(file.toPath())||(!canonical.equals(root)&&!canonical.toPath().startsWith(root.toPath())))
            throw new IOException("DOCUMENT_OUTSIDE_WORKSPACE");
        return canonical;
    }
    public static String mime(String filename){
        int dot=filename.lastIndexOf('.');String extension=dot<0?"":filename.substring(dot+1).toLowerCase(java.util.Locale.ROOT);
        if(extension.equals("blend"))return "application/x-blender";
        if(extension.equals("glb"))return "model/gltf-binary";
        if(extension.equals("gltf"))return "model/gltf+json";
        String result=MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension);
        return result==null?"application/octet-stream":result;
    }
    private static Node localNode(Context c,File file)throws Exception{
        file=local(c,file);if(!file.exists())throw new IOException("DOCUMENT_NOT_FOUND");
        String id=file.equals(workspace(c))?"root":bind(c,"workspace",file.getPath());
        return new Node("workspace",id,file.getName(),file.isDirectory()?DocumentsContract.Document.MIME_TYPE_DIR:mime(file.getName()),
            file.isFile()?file.length():0,file.lastModified(),file,null);
    }
    private static Node providerNode(Context c,String location,Uri uri)throws Exception{
        Uri root=tree(c,location,false);
        if(!root.getAuthority().equals(uri.getAuthority()))throw new IOException("DOCUMENT_PROVIDER_MISMATCH");
        if(DocumentsContract.isTreeUri(root))uri=DocumentsContract.buildDocumentUriUsingTree(root,DocumentsContract.getDocumentId(uri));
        else if(!root.equals(uri))throw new IOException("DOCUMENT_OUTSIDE_EXPLICIT_FILE_GRANT");
        String[] fields={DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE,DocumentsContract.Document.COLUMN_LAST_MODIFIED};
        try(Cursor cursor=c.getContentResolver().query(uri,fields,null,null,null)){
            if(cursor==null||!cursor.moveToFirst())throw new IOException("DOCUMENT_NOT_FOUND");
            String id=bind(c,location,uri.toString());
            return new Node(location,id,cursor.getString(0),cursor.getString(1),cursor.isNull(2)?-1:cursor.getLong(2),cursor.isNull(3)?0:cursor.getLong(3),null,uri);
        }
    }
    public static Node resolve(Context c,String location,String id,boolean write)throws Exception{
        if("workspace".equals(location))return localNode(c,"root".equals(id)?workspace(c):new File(value(c,location,id)));
        Uri root=tree(c,location,write);
        Uri uri="root".equals(id)?(DocumentsContract.isTreeUri(root)?DocumentsContract.buildDocumentUriUsingTree(root,DocumentsContract.getTreeDocumentId(root)):root):
            Uri.parse(value(c,location,id));
        return providerNode(c,location,uri);
    }
    public static JSONObject locations(Context c)throws Exception{
        JSONArray items=new JSONArray().put(new JSONObject().put("location_id","workspace").put("name","Render Workspace")
            .put("kind","app_workspace").put("root_document_id","root").put("readable",true).put("writable",true)
            .put("device_path",workspace(c).getPath()).put("requires_picker",false));
        for(UriPermission grant:c.getContentResolver().getPersistedUriPermissions()){
            Uri uri=grant.getUri();if((!DocumentsContract.isTreeUri(uri)&&!DocumentsContract.isDocumentUri(c,uri))||!grant.isReadPermission())continue;
            String id=locationId(uri);JSONObject item=new JSONObject().put("location_id",id)
                .put("provider_authority",uri.getAuthority()).put("kind",DocumentsContract.isTreeUri(uri)?"granted_document_tree":"explicitly_picked_file")
                .put("root_document_id","root").put("readable",true).put("writable",grant.isWritePermission());
            try{item.put("name",resolve(c,id,"root",false).name);}
            catch(Exception unavailable){item.put("name","Granted folder").put("provider_unavailable",true);}
            items.put(item);
        }
        return new JSONObject().put("locations",items).put("gallery_browsed",false).put("native_editor_required",false)
            .put("external_folder_selection_operation","storage.pick");
    }
    public static void pickFile(android.app.Activity activity){
        android.content.Intent intent=new android.content.Intent(android.content.Intent.ACTION_OPEN_DOCUMENT)
            .addCategory(android.content.Intent.CATEGORY_OPENABLE).setType("*/*")
            .addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION|android.content.Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        activity.startActivityForResult(intent,PICK_FILE);
    }
    public static JSONObject acceptFile(Context c,int resultCode,android.content.Intent data)throws Exception{
        if(resultCode!=android.app.Activity.RESULT_OK||data==null||data.getData()==null)return new JSONObject().put("cancelled",true);
        Uri uri=data.getData();
        if(!"content".equals(uri.getScheme())||!DocumentsContract.isDocumentUri(c,uri))throw new IOException("PICKED_FILE_REQUIRES_DOCUMENT_PROVIDER");
        c.getContentResolver().takePersistableUriPermission(uri,android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION);
        Node source=resolve(c,locationId(uri),"root",false);
        JSONObject task=FileTransfers.enqueue(c,"import",new JSONObject().put("request_id","owner-file-"+java.util.UUID.randomUUID())
            .put("location_id",source.location).put("document_id",source.id));
        return FileTransferService.request(c,task.getString("transfer_id"));
    }
    public static JSONObject list(Context c,String location,String parent,int offset,int limit)throws Exception{
        if(offset<0||offset>100000||limit<1||limit>100)throw new IllegalArgumentException("INVALID_STORAGE_PAGE");
        Node directory=resolve(c,location,parent,false);if(!directory.directory())throw new IOException("DOCUMENT_IS_NOT_FOLDER");
        JSONArray items=new JSONArray();boolean more=false;
        if(directory.file!=null){
            File[] files=directory.file.listFiles();if(files==null)throw new IOException("WORKSPACE_LIST_FAILED");
            Arrays.sort(files,Comparator.comparing(File::getName));
            int seen=0;
            for(File file:files){
                if(Files.isSymbolicLink(file.toPath()))continue;
                if(seen++<offset)continue;
                if(items.length()==limit){more=true;break;}
                items.put(localNode(c,file).json());
            }
        }else{
            Uri root=tree(c,location,false);
            Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(root,DocumentsContract.getDocumentId(directory.uri));
            String[] columns={DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE,DocumentsContract.Document.COLUMN_SIZE,DocumentsContract.Document.COLUMN_LAST_MODIFIED};
            try(Cursor cursor=c.getContentResolver().query(children,columns,null,null,null)){
                if(cursor==null)throw new IOException("DOCUMENT_PROVIDER_LIST_FAILED");
                int seen=0;
                while(cursor.moveToNext()){
                    if(seen++<offset)continue;
                    if(items.length()==limit){more=true;break;}
                    Uri child=DocumentsContract.buildDocumentUriUsingTree(root,cursor.getString(0));
                    items.put(new Node(location,bind(c,location,child.toString()),cursor.getString(1),cursor.getString(2),
                        cursor.isNull(3)?-1:cursor.getLong(3),cursor.isNull(4)?0:cursor.getLong(4),null,child).json());
                }
            }
        }
        return new JSONObject().put("location_id",location).put("parent_document_id",parent).put("documents",items)
            .put("next_offset",more?offset+items.length():JSONObject.NULL).put("gallery_browsed",false);
    }
    public static Node find(Context c,String location,String parent,String name)throws Exception{
        name(name);
        Node directory=resolve(c,location,parent,false);
        if(!directory.directory())throw new IOException("DOCUMENT_IS_NOT_FOLDER");
        if(directory.file!=null){
            File candidate=local(c,new File(directory.file,name));
            return candidate.exists()?localNode(c,candidate):null;
        }
        Node found=null;
        for(int offset=0;offset<=100000;){
            JSONObject page=list(c,location,parent,offset,100);JSONArray rows=page.getJSONArray("documents");
            for(int i=0;i<rows.length();i++){
                JSONObject row=rows.getJSONObject(i);
                if(name.equals(row.getString("name"))){
                    if(found!=null)throw new IOException("DOCUMENT_NAME_AMBIGUOUS");
                    found=resolve(c,location,row.getString("document_id"),false);
                }
            }
            if(page.isNull("next_offset"))return found;
            offset=page.getInt("next_offset");
        }
        throw new IOException("DOCUMENT_FOLDER_TOO_LARGE_USE_EXACT_HANDLE");
    }
    public static synchronized JSONObject createFolder(Context c,String location,String parent,String name)throws Exception{
        name(name);Node directory=resolve(c,location,parent,true);
        if(!directory.directory())throw new IOException("DOCUMENT_IS_NOT_FOLDER");
        Node found;
        if(directory.file!=null){
            File target=local(c,new File(directory.file,name));
            boolean existed=target.exists();
            if(existed&&!target.isDirectory())throw new IOException("DOCUMENT_NAME_CONFLICT");
            if(!existed&&!target.mkdir())throw new IOException("WORKSPACE_FOLDER_CREATE_FAILED");
            return localNode(c,target).json().put("already_exists",existed).put("native_editor_required",false);
        }
        found=find(c,location,parent,name);
        if(found!=null){if(!found.directory())throw new IOException("DOCUMENT_NAME_CONFLICT");
            return found.json().put("already_exists",true).put("native_editor_required",false);}
        Uri made=DocumentsContract.createDocument(c.getContentResolver(),directory.uri,DocumentsContract.Document.MIME_TYPE_DIR,name);
        if(made==null)throw new IOException("DOCUMENT_PROVIDER_CANNOT_CREATE_FOLDER");
        return providerNode(c,location,made).json().put("already_exists",false).put("native_editor_required",false);
    }
    public static synchronized Node createFile(Context c,String location,String parent,String name,String mime)throws Exception{
        name(name);Node directory=resolve(c,location,parent,true);
        if(!directory.directory())throw new IOException("DOCUMENT_IS_NOT_FOLDER");
        if(find(c,location,parent,name)!=null)throw new IOException("DOCUMENT_NAME_CONFLICT");
        if(directory.file!=null){
            File target=local(c,new File(directory.file,name));
            if(!target.createNewFile())throw new IOException("DOCUMENT_NAME_CONFLICT");
            return localNode(c,target);
        }
        Uri created=DocumentsContract.createDocument(c.getContentResolver(),directory.uri,mime,name);
        if(created==null)throw new IOException("DOCUMENT_PROVIDER_CANNOT_CREATE_FILE");
        return providerNode(c,location,created);
    }
    public static InputStream read(Context c,Node node)throws Exception{
        if(node.directory())throw new IOException("DOCUMENT_IS_FOLDER");
        InputStream result=node.file!=null?new FileInputStream(local(c,node.file)):c.getContentResolver().openInputStream(node.uri);
        if(result==null)throw new IOException("DOCUMENT_PROVIDER_CANNOT_READ");return result;
    }
    public static OutputStream write(Context c,Node node)throws Exception{
        resolve(c,node.location,node.id,true);
        OutputStream result=node.file!=null?new FileOutputStream(local(c,node.file)):c.getContentResolver().openOutputStream(node.uri,"wt");
        if(result==null)throw new IOException("DOCUMENT_PROVIDER_CANNOT_WRITE");return result;
    }
}
