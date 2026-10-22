package com.rezox.render.agent;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;

/** Only app-owned Production files; never filesystem paths supplied by a remote client. */
public final class ProductionFiles {
    private ProductionFiles(){}
    public static File root(Context context)throws Exception {
        File root=new File(context.getFilesDir(),"Production");
        if(!root.isDirectory()&&!root.mkdirs())throw new IOException("PRODUCTION_STORAGE_UNAVAILABLE");
        return root.getCanonicalFile();
    }
    public static File folder(Context context,String category)throws Exception {
        if(category==null||!(category.matches("[a-f0-9]{32}")||category.equals("Assets")||category.equals("Captures")||category.equals("Projects")))
            throw new IllegalArgumentException("INVALID_ARTIFACT_CATEGORY");
        File root=root(context),dir=new File(root,category);
        if(Files.isSymbolicLink(dir.toPath())||!root.equals(dir.getCanonicalFile().getParentFile()))throw new IOException("ARTIFACT_OUTSIDE_SCOPE");
        if(!dir.isDirectory()&&!dir.mkdirs())throw new IOException("ARTIFACT_FOLDER_UNAVAILABLE");
        return dir;
    }
    public static File file(Context context,String category,String filename)throws Exception {
        if(filename==null||!filename.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")||filename.contains(".."))throw new IllegalArgumentException("INVALID_ARTIFACT_NAME");
        File dir=folder(context,category),f=new File(dir,filename);
        if(Files.isSymbolicLink(f.toPath())||!dir.getCanonicalFile().equals(f.getCanonicalFile().getParentFile()))throw new IOException("ARTIFACT_OUTSIDE_SCOPE");
        return f;
    }
    public static String sha(File file)throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        try(InputStream input=new FileInputStream(file)){byte[] b=new byte[1048576];int n;while((n=input.read(b))!=-1)digest.update(b,0,n);}
        return AgentPolicy.hex(digest.digest());
    }
    public static JSONObject receipt(File file,String category)throws Exception {
        if(!file.isFile())throw new IOException("ARTIFACT_NOT_FOUND");
        return new JSONObject().put("filename",file.getName()).put("category",category)
                .put("bytes",file.length()).put("sha256",sha(file));
    }
    public static JSONObject read(Context context,JSONObject p)throws Exception {
        ProductionBridge.fields(p,"category,filename,offset,length,expected_sha256");
        File f=file(context,p.getString("category"),p.getString("filename"));
        if(!f.isFile())throw new IOException("ARTIFACT_NOT_FOUND");
        long offset=ProductionBridge.integer(p,"offset",0,Long.MAX_VALUE,0);
        int length=(int)ProductionBridge.integer(p,"length",1,24576,24576);
        if(offset>f.length())throw new IllegalArgumentException("INVALID_ARTIFACT_OFFSET");
        String digest=sha(f);
        if(p.has("expected_sha256")&&!digest.equals(p.getString("expected_sha256")))throw new IOException("ARTIFACT_REVISION_CONFLICT");
        byte[] data=new byte[(int)Math.min(length,f.length()-offset)];
        try(RandomAccessFile input=new RandomAccessFile(f,"r")){input.seek(offset);input.readFully(data);}
        return new JSONObject().put("filename",f.getName()).put("offset",offset).put("next_offset",offset+data.length)
                .put("bytes",f.length()).put("sha256",digest).put("eof",offset+data.length==f.length())
                .put("base64",Base64.encodeToString(data,Base64.NO_WRAP));
    }
    public static JSONObject writeReference(Context context,JSONObject p)throws Exception {
        ProductionBridge.fields(p,"sha256,extension,offset,total_bytes,base64,finish");
        String digest=p.getString("sha256"),ext=p.getString("extension").toLowerCase(java.util.Locale.ROOT);
        if(!digest.matches("[a-f0-9]{64}")||!(ext.equals("png")||ext.equals("jpg")||ext.equals("jpeg")))throw new IllegalArgumentException("INVALID_REFERENCE_ID");
        long total=ProductionBridge.integer(p,"total_bytes",1,100L*1024*1024,-1),offset=ProductionBridge.integer(p,"offset",0,total,0);
        String encoded=p.getString("base64");if(encoded.length()>32768)throw new IllegalArgumentException("REFERENCE_CHUNK_TOO_LARGE");
        byte[] data=Base64.decode(encoded,Base64.DEFAULT);if(data.length>24576||offset+data.length>total)throw new IllegalArgumentException("REFERENCE_CHUNK_TOO_LARGE");
        File dest=file(context,"Assets",digest+"."+ext),part=file(context,"Assets",digest+"."+ext+".partial");
        if(dest.isFile()){
            if(dest.length()!=total||!sha(dest).equals(digest))throw new IOException("REFERENCE_REVISION_CONFLICT");
            return receipt(dest,"Assets").put("complete",true);
        }
        try(RandomAccessFile out=new RandomAccessFile(part,"rw")){
            if(out.length()>offset){
                if(offset+data.length>out.length())throw new IOException("REFERENCE_OFFSET_CONFLICT");
                byte[] previous=new byte[data.length];out.seek(offset);out.readFully(previous);
                if(!java.util.Arrays.equals(previous,data))throw new IOException("REFERENCE_REPLAY_CONFLICT");
            }else{
                if(out.length()!=offset)throw new IOException("REFERENCE_OFFSET_CONFLICT");out.seek(offset);out.write(data);out.getFD().sync();
            }
        }
        if(p.optBoolean("finish",false)){
            if(part.length()!=total||!sha(part).equals(digest))throw new IOException("REFERENCE_HASH_MISMATCH");
            Files.move(part.toPath(),dest.toPath(),StandardCopyOption.ATOMIC_MOVE);
            return receipt(dest,"Assets").put("complete",true);
        }
        return new JSONObject().put("complete",false).put("received_bytes",part.length()).put("total_bytes",total);
    }
    public static JSONObject export(Context context,JSONObject p)throws Exception {
        ProductionBridge.fields(p,"category,filename,expected_sha256");
        String category=p.getString("category");File file=file(context,category,p.getString("filename"));
        if(!file.isFile()||file.getName().contains("partial")||file.getName().endsWith(".tmp"))throw new IOException("ARTIFACT_INCOMPLETE");
        String expected=p.getString("expected_sha256");if(!sha(file).equals(expected))throw new IOException("ARTIFACT_REVISION_CONFLICT");
        String mime=file.getName().endsWith(".mp4")?"video/mp4":file.getName().endsWith(".png")?"image/png":file.getName().endsWith(".blend")?"application/x-blender":null;
        if(mime==null)throw new IllegalArgumentException("EXPORT_TYPE_UNAVAILABLE");
        ContentValues values=new ContentValues();values.put(MediaStore.Downloads.DISPLAY_NAME,file.getName());values.put(MediaStore.Downloads.MIME_TYPE,mime);
        values.put(MediaStore.Downloads.RELATIVE_PATH,Environment.DIRECTORY_DOWNLOADS+"/RenderStudio");values.put(MediaStore.Downloads.IS_PENDING,1);
        Uri uri=context.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
        if(uri==null)throw new IOException("DOWNLOADS_UNAVAILABLE");boolean done=false;
        try{
            try(InputStream in=new FileInputStream(file);OutputStream out=context.getContentResolver().openOutputStream(uri,"w")){
                if(out==null)throw new IOException("DOWNLOADS_UNAVAILABLE");byte[] b=new byte[1048576];int n;while((n=in.read(b))!=-1)out.write(b,0,n);
            }
            ContentValues publish=new ContentValues();publish.put(MediaStore.Downloads.IS_PENDING,0);
            if(context.getContentResolver().update(uri,publish,null,null)!=1)throw new IOException("EXPORT_COMMIT_FAILED");
            done=true;return receipt(file,category).put("downloads_uri",uri.toString()).put("downloads_directory","Download/RenderStudio");
        }finally{if(!done)context.getContentResolver().delete(uri,null,null);}
    }
}
