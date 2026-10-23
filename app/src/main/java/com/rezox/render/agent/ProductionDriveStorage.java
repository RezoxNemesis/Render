package com.rezox.render.agent;

import android.app.Activity;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.UriPermission;
import android.net.Uri;
import android.provider.DocumentsContract;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;

/**
 * Persisted owner-granted Storage Access Framework document tree.
 * It can be local phone storage or a third-party DocumentsProvider (including Drive).
 * SAF permission is granted by Android's system picker, never by the agent.
 *
 * Render always saves its original .blend/PNG/MP4 files to app-private storage
 * first. Publishing a copy cannot alter or destroy the original work.
 * No Gallery access, MANAGE_EXTERNAL_STORAGE or arbitrary filesystem paths.
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
        context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit().putString(TREE,tree.toString()).commit();
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
        return new JSONObject().put("folder_granted",tree!=null)
            .put("provider_authority",tree==null?JSONObject.NULL:tree.getAuthority())
            .put("cloud_rendering",false).put("google_drive_cloud_rendering",false)
            .put("user_picked_document_provider",tree!=null)
            .put("requires_owner_folder_selection",tree==null)
            .put("remote_sync_verified",false)
            .put("saved_project_export_supported",true)
            .put("note","Owner-approved local/Drive document folder. Downloads MP4 output is separate. Cloud storage does not render Blender.");
    }

    private static String mime(String filename){
        if(filename.endsWith(".blend"))return "application/x-blender";
        if(filename.endsWith(".mp4"))return "video/mp4";
        if(filename.endsWith(".png"))return "image/png";
        return null;
    }
    private static String sha(InputStream input)throws Exception{
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        byte[] buffer=new byte[1024*1024];int count;
        while((count=input.read(buffer))!=-1)if(count>0)digest.update(buffer,0,count);
        return AgentPolicy.hex(digest.digest());
    }
    private static boolean matchesProviderFile(Context c,Uri uri,String expected){
        try(InputStream input=c.getContentResolver().openInputStream(uri)){
            return input!=null&&expected.equals(sha(input));
        }catch(Exception ignored){return false;}
    }

    /**
     * Common verification path for app-owned immutable checkpoints and rendered outputs.
     * Destination is NEVER a raw file path from the owner/agent. Only an
     * Android-picked document tree is writable.
     */
    private static JSONObject publish(Context c,File source,String expected)throws Exception{
        Uri tree=selectedTree(c);
        if(tree==null)throw new IllegalStateException("BACKUP_DOCUMENT_FOLDER_NOT_GRANTED");
        if(!source.isFile()||Files.isSymbolicLink(source.toPath()))
            throw new IllegalArgumentException("ARTIFACT_NOT_READY");
        String filename=source.getName(), type=mime(filename);
        if(type==null)throw new IllegalArgumentException("DOCUMENT_BACKUP_FILE_TYPE_UNSUPPORTED");
        if(!expected.matches("[a-f0-9]{64}")||!expected.equals(ProductionFiles.sha(source)))
            throw new IllegalStateException("ARTIFACT_CHECKSUM_MISMATCH");
        int ext=filename.lastIndexOf('.');
        String outputName=filename.substring(0,ext)+"_"+expected.substring(0,12)+filename.substring(ext);
        String receiptKey="verified_"+AgentPolicy.sha256(tree.toString()+"|"+outputName+"|"+expected);
        android.content.SharedPreferences preferences=c.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
        String previous=preferences.getString(receiptKey,null);
        if(previous!=null&&matchesProviderFile(c,Uri.parse(previous),expected)){
            return new JSONObject().put("provider_write_completed",true)
                .put("provider_readback_sha256_verified",true)
                .put("already_exported",true)
                .put("provider_authority",tree.getAuthority())
                .put("document_uri",previous).put("provider_filename",outputName)
                .put("source_sha256",expected).put("bytes_written_to_provider",source.length())
                .put("source_project_unchanged",true).put("remote_sync_verified",false);
        }
        Uri parent=DocumentsContract.buildDocumentUriUsingTree(tree,DocumentsContract.getTreeDocumentId(tree));
        Uri dest=null;long copied=0;
        try{
            dest=DocumentsContract.createDocument(c.getContentResolver(),parent,type,outputName);
            if(dest==null)throw new IOException("BACKUP_PROVIDER_CANNOT_CREATE_FILE");
            try(InputStream input=new FileInputStream(source);
                OutputStream output=c.getContentResolver().openOutputStream(dest,"w")){
                if(output==null)throw new IOException("BACKUP_PROVIDER_CANNOT_WRITE");
                byte[] buffer=new byte[1024*1024];int n;
                while((n=input.read(buffer))!=-1){
                    if(n>0){output.write(buffer,0,n);copied+=n;}
                }
                output.flush();
            }
            if(copied!=source.length())throw new IOException("BACKUP_UPLOAD_LENGTH_MISMATCH");
            // A provider success is not durable until we independently read
            // back and hash the exact document. Cloud remote sync is separate.
            if(!matchesProviderFile(c,dest,expected))
                throw new IOException("BACKUP_PROVIDER_READBACK_SHA256_MISMATCH");
            preferences.edit().putString(receiptKey,dest.toString()).commit();
            return new JSONObject().put("provider_write_completed",true)
                .put("provider_readback_sha256_verified",true)
                .put("already_exported",false)
                .put("provider_authority",tree.getAuthority())
                .put("document_uri",dest.toString())
                .put("source_sha256",expected).put("bytes_written_to_provider",copied)
                .put("provider_filename",outputName)
                .put("source_project_unchanged",true)
                .put("remote_sync_verified",false).put("cloud_rendering",false);
        }catch(Exception error){
            if(dest!=null)try{DocumentsContract.deleteDocument(c.getContentResolver(),dest);}
                catch(Exception ignored){}
            throw error;
        }
    }

    /**
     * True only for a .blend file immediately within one of Render's explicit
     * app-owned project folders. Rejects traversal and symbolic links.
     */
    public static boolean isOwnedBlend(Context c,File source)throws Exception{
        if(source==null||!source.getName().matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")||
           !source.getName().endsWith(".blend")||source.getName().contains("..")||
           Files.isSymbolicLink(source.toPath())||!source.isFile())return false;
        File parent=source.getCanonicalFile().getParentFile();
        if(parent.equals(ProductionFiles.folder(c,"Projects").getCanonicalFile())||
           parent.equals(new File(c.getFilesDir(),"Projects").getCanonicalFile()))
            return true;
        File ext=c.getExternalFilesDir(null);
        return ext!=null&&parent.equals(new File(ext,"Projects").getCanonicalFile());
    }

    public static JSONObject exportOwnedBlend(Context c,File file)throws Exception{
        // Permission is checked first, including revoked Android grants.
        if(selectedTree(c)==null)throw new IllegalStateException("BACKUP_DOCUMENT_FOLDER_NOT_GRANTED");
        if(!isOwnedBlend(c,file))throw new IllegalArgumentException("PROJECT_FILE_OUTSIDE_SCOPE");
        return publish(c,file,ProductionFiles.sha(file));
    }

    /** Owner-visible project library sync; does NOT scan device storage. */
    public static JSONObject exportSavedProjects(Context c)throws Exception{
        if(selectedTree(c)==null)throw new IllegalStateException("BACKUP_DOCUMENT_FOLDER_NOT_GRANTED");
        ArrayList<File> folders=new ArrayList<>();
        folders.add(ProductionFiles.folder(c,"Projects"));
        folders.add(new File(c.getFilesDir(),"Projects"));
        File external=c.getExternalFilesDir(null);
        if(external!=null)folders.add(new File(external,"Projects"));
        JSONArray receipts=new JSONArray();
        Set<String> paths=new HashSet<>();
        int exported=0;
        for(File folder:folders){
            File[] projects=folder.listFiles();
            if(projects==null)continue;
            for(File source:projects){
                if(!isOwnedBlend(c,source)||!paths.add(source.getCanonicalPath()))continue;
                receipts.put(exportOwnedBlend(c,source));
                exported++;
            }
        }
        return new JSONObject().put("saved_projects_exported",exported)
            .put("folder_granted",true).put("all_readbacks_verified",true)
            .put("receipts",receipts).put("source_projects_preserved",true);
    }

    /** Typed native artifact backup for owner-authorized production operations. */
    public static JSONObject backup(Context c,JSONObject args)throws Exception{
        ProductionBridge.fields(args,"category,filename,expected_sha256");
        String category=args.getString("category"),filename=args.getString("filename");
        File source=ProductionFiles.file(c,category,filename);
        if(source.getName().contains(".partial")||source.getName().endsWith(".tmp"))
            throw new IllegalArgumentException("ARTIFACT_NOT_READY");
        return publish(c,source,args.getString("expected_sha256"));
    }
}
