package com.rezox.render.agent;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.UriPermission;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.content.ContentResolver;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.util.List;

/** User-selectable Android DocumentsProvider export.
 * Google Drive can be a provider, but Google Drive storage does NOT render Blender.
 * No Google OAuth key or Gallery browsing is involved.
 */
public final class ProductionDriveStorage {
    private static final String PREFS="render_production_drive_v1";
    private static final String TREE="owned_tree_uri";
    public static final int REQUEST_PICK_FOLDER=701;
    private ProductionDriveStorage(){}

    public static void chooseFolder(Activity a){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION|
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION|
            Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
        a.startActivityForResult(intent,REQUEST_PICK_FOLDER);
    }
    public static boolean acceptFolderSelection(Context context,int resultCode,Intent returned)throws Exception{
        if(resultCode!=Activity.RESULT_OK || returned==null || returned.getData()==null)return false;
        Uri tree=returned.getData();
        if(!ContentResolver.SCHEME_CONTENT.equals(tree.getScheme())||
            !DocumentsContract.isTreeUri(tree))throw new IllegalArgumentException("INVALID_BACKUP_DOCUMENT_TREE");
        int permissions=Intent.FLAG_GRANT_READ_URI_PERMISSION|Intent.FLAG_GRANT_WRITE_URI_PERMISSION;
        context.getContentResolver().takePersistableUriPermission(tree,permissions);
        if(!permissionExists(context,tree))throw new IllegalStateException("DOCUMENT_PROVIDER_PERMISSION_NOT_PERSISTED");
        context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putString(TREE,tree.toString()).apply();
        return true;
    }
    static boolean permissionExists(Context c,Uri tree){
        for(UriPermission p:c.getContentResolver().getPersistedUriPermissions())
            if(p.getUri().equals(tree)&&p.isReadPermission()&&p.isWritePermission())return true;
        return false;
    }
    private static Uri selectedTree(Context context){
        String value=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getString(TREE,null);
        if(value==null)return null;
        Uri tree=Uri.parse(value);
        return ContentResolver.SCHEME_CONTENT.equals(tree.getScheme())&&permissionExists(context,tree)?tree:null;
    }
    public static JSONObject status(Context c)throws Exception{
        Uri tree=selectedTree(c);
        // Never assume every DocumentsProvider is Google Drive or cloud-backed.
        return new JSONObject().put("folder_granted",tree!=null)
            .put("provider_authority",tree==null?JSONObject.NULL:tree.getAuthority())
            .put("cloud_rendering",false).put("google_drive_cloud_rendering",false)
            .put("user_picked_document_provider",tree!=null)
            .put("requires_owner_folder_selection",tree==null)
            .put("remote_sync_verified",false)
            .put("note","Google Drive is optional output storage. Cloud upload is managed by the selected Android document provider, not a render GPU.");
    }

    private static String mime(String filename){
        if(filename.endsWith(".blend"))return "application/x-blender";
        if(filename.endsWith(".mp4"))return "video/mp4";
        if(filename.endsWith(".png"))return "image/png";
        return null;
    }

    public static JSONObject backup(Context c,JSONObject args)throws Exception{
        ProductionBridge.fields(args,"category,filename,expected_sha256");
        Uri tree=selectedTree(c);
        if(tree==null)throw new IllegalStateException("BACKUP_DOCUMENT_FOLDER_NOT_GRANTED");
        String category=args.getString("category"),filename=args.getString("filename");
        File source=ProductionFiles.file(c,category,filename);
        if(!source.isFile()||filename.contains(".partial")||filename.endsWith(".tmp"))
            throw new IllegalArgumentException("ARTIFACT_NOT_READY");
        String expected=args.getString("expected_sha256");
        if(!expected.matches("[a-f0-9]{64}")||!expected.equals(ProductionFiles.sha(source)))
            throw new IllegalStateException("ARTIFACT_CHECKSUM_MISMATCH");
        String type=mime(filename);
        if(type==null)throw new IllegalArgumentException("DOCUMENT_BACKUP_FILE_TYPE_UNSUPPORTED");
        Uri parent=DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree));
        Uri dest=null;long copied=0;
        try{
            String outputName=filename.substring(0,filename.lastIndexOf('.'))+"_"+expected.substring(0,10)+
                filename.substring(filename.lastIndexOf('.'));
            dest=DocumentsContract.createDocument(c.getContentResolver(),parent,type,outputName);
            if(dest==null)throw new IOException("BACKUP_PROVIDER_CANNOT_CREATE_FILE");
            try(FileInputStream input=new FileInputStream(source);
                OutputStream output=c.getContentResolver().openOutputStream(dest,"w")){
                if(output==null)throw new IOException("BACKUP_PROVIDER_CANNOT_WRITE");
                byte[] b=new byte[1024*1024];
                int n;while((n=input.read(b))!=-1){output.write(b,0,n);copied+=n;}
                output.flush();
            }
            if(copied!=source.length())throw new IOException("BACKUP_UPLOAD_LENGTH_MISMATCH");
            // SAF sync is provider-mediated, and does not guarantee Google's
            // remote data centre already has the bytes at this instant.
            return new JSONObject().put("provider_write_completed",true)
                .put("remote_sync_verified",false)
                .put("provider_authority",tree.getAuthority())
                .put("source_sha256",expected).put("bytes_written_to_provider",copied)
                .put("provider_filename",outputName)
                .put("source_project_unchanged",true)
                .put("cloud_rendering",false);
        }catch(Exception error){
            if(dest!=null)try{DocumentsContract.deleteDocument(c.getContentResolver(),dest);}catch(Exception ignored){}
            throw error;
        }
    }
}