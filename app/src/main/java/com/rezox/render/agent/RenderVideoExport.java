package com.rezox.render.agent;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.util.Locale;

/** Publish only the exact Android-native Blender MP4, never Gallery contents. */
public final class RenderVideoExport {
    private RenderVideoExport() {}

    public static boolean isRenderVideoName(String name) {
        return name != null && name.matches("RenderVideo_[a-f0-9]{32}[0-9-]*\\.mp4");
    }

    public static JSONObject publish(Context context, JSONObject result) throws Exception {
        String name=result.getString("filename");
        if (!isRenderVideoName(name))
            throw new IllegalArgumentException("UNSAFE_RENDER_VIDEO_FILENAME");
        File parent=new File(context.getFilesDir(),"Renders").getCanonicalFile();
        File output=new File(parent,name).getCanonicalFile();
        if (!parent.equals(output.getParentFile()) ||
                !output.isFile() || java.nio.file.Files.isSymbolicLink(output.toPath()))
            throw new IllegalArgumentException("NATIVE_VIDEO_NOT_OWNED");
        if (output.length()<1000 || output.length()!=result.getLong("bytes"))
            throw new IllegalStateException("NATIVE_VIDEO_SIZE_MISMATCH");
        MessageDigest hash=MessageDigest.getInstance("SHA-256");
        try(InputStream input=new FileInputStream(output)){
            byte[] buf=new byte[1048576]; int count;
            while((count=input.read(buf))!=-1)hash.update(buf,0,count);
        }
        if(!AgentPolicy.hex(hash.digest()).equals(result.getString("sha256")))
            throw new IllegalStateException("NATIVE_VIDEO_HASH_MISMATCH");

        ContentResolver resolver=context.getContentResolver();
        ContentValues values=new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME,name);
        values.put(MediaStore.Downloads.MIME_TYPE,"video/mp4");
        values.put(MediaStore.Downloads.RELATIVE_PATH,
                   Environment.DIRECTORY_DOWNLOADS+"/RenderStudio");
        values.put(MediaStore.Downloads.IS_PENDING,1);
        Uri uri=resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
        if(uri==null)throw new IllegalStateException("NATIVE_VIDEO_EXPORT_NOT_AVAILABLE");
        boolean published=false;
        try {
            try(InputStream input=new FileInputStream(output);
                OutputStream target=resolver.openOutputStream(uri,"w")){
                if(target==null)throw new IllegalStateException("DOWNLOADS_OPEN_FAILED");
                byte[] buf=new byte[1048576];int count;
                while((count=input.read(buf))!=-1)target.write(buf,0,count);
                target.flush();
            }
            ContentValues done=new ContentValues();
            done.put(MediaStore.Downloads.IS_PENDING,0);
            if(resolver.update(uri,done,null,null)!=1)
                throw new IllegalStateException("NATIVE_VIDEO_EXPORT_COMMIT_FAILED");
            published=true;
            return result.put("android_downloads_uri",uri.toString())
                .put("android_downloads_location","Download/RenderStudio/"+name);
        } finally {
            if(!published)resolver.delete(uri,null,null);
        }
    }
}
