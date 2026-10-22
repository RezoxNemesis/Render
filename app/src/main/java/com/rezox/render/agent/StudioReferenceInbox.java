package com.rezox.render.agent;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.ExifInterface;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.os.SystemClock;
import android.provider.OpenableColumns;
import android.database.Cursor;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

/** Only explicitly granted image/video URIs from owner share and document picker.
 * Does not enumerate media storage, Gallery, Downloads or Google Drive.
 */
public final class StudioReferenceInbox {
    public static final int PICK_REFERENCE=714;
    private static final long MAX_IMAGE=80L*1024*1024;
    private static final long MAX_VIDEO=512L*1024*1024;
    private static final long MAX_IMAGE_PIXELS=80_000_000L;
    private StudioReferenceInbox(){}

    public static void openPicker(Activity activity){
        Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{
                "image/jpeg","image/png","image/webp","video/mp4"});
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        activity.startActivityForResult(intent,PICK_REFERENCE);
    }
    public static boolean isExplicitOwnerMediaIntent(Intent intent){
        if(intent==null)return false;
        String action=intent.getAction();
        return Intent.ACTION_SEND.equals(action)||Intent.ACTION_SEND_MULTIPLE.equals(action)
                ||Intent.ACTION_OPEN_DOCUMENT.equals(action);
    }
    private static List<Uri> selected(Intent intent){
        if(!isExplicitOwnerMediaIntent(intent))return Collections.emptyList();
        ArrayList<Uri> result=new ArrayList<>();
        if(intent.getData()!=null)result.add(intent.getData());
        ClipData clip=intent.getClipData();
        if(clip!=null)for(int i=0;i<clip.getItemCount();i++){
            Uri uri=clip.getItemAt(i).getUri();
            if(uri!=null&&!result.contains(uri))result.add(uri);
        }
        Object extra=intent.getParcelableExtra(Intent.EXTRA_STREAM);
        if(extra instanceof Uri && !result.contains(extra))result.add((Uri)extra);
        if(Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())){
            ArrayList<Uri> list=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if(list!=null)for(Uri uri:list)if(uri!=null&&!result.contains(uri))result.add(uri);
        }
        if(result.size()>12)throw new IllegalArgumentException("REFERENCE_BULK_LIMIT");
        return result;
    }
    private static String fileType(File file)throws Exception{
        byte[] data=new byte[16];
        try(InputStream input=new FileInputStream(file)){
            int len=input.read(data);
            if(len<12)throw new IllegalArgumentException("REFERENCE_FILE_INVALID");
        }
        if((data[0]&255)==0xff&&(data[1]&255)==0xd8&&(data[2]&255)==0xff)return "jpg";
        if((data[0]&255)==0x89&&data[1]==0x50&&data[2]==0x4e&&data[3]==0x47)return "png";
        if(new String(data,0,4,java.nio.charset.StandardCharsets.US_ASCII).equals("RIFF") &&
                new String(data,8,4,java.nio.charset.StandardCharsets.US_ASCII).equals("WEBP"))return "webp";
        if(new String(data,4,4,java.nio.charset.StandardCharsets.US_ASCII).equals("ftyp"))return "mp4";
        throw new IllegalArgumentException("REFERENCE_MEDIA_UNSUPPORTED");
    }
    private static File store(Context context,Uri uri)throws Exception{
        if(uri==null||!ContentResolver.SCHEME_CONTENT.equals(uri.getScheme()))
            throw new IllegalArgumentException("REFERENCE_CONTENT_URI_REQUIRED");
        File dir=ProductionFiles.folder(context,"Assets");
        File temp=ProductionFiles.file(context,"Assets","Reference_"+UUID.randomUUID().toString().replace("-","")+".partial");
        byte[] buf=new byte[256*1024];long total=0;
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        try(InputStream input=context.getContentResolver().openInputStream(uri);
            OutputStream output=new FileOutputStream(temp)){
            if(input==null)throw new IllegalArgumentException("REFERENCE_GRANT_EXPIRED");
            int n;
            while((n=input.read(buf))!=-1){
                total+=n;if(total>MAX_VIDEO)throw new IllegalArgumentException("REFERENCE_FILE_TOO_LARGE");
                md.update(buf,0,n);output.write(buf,0,n);
            }
            output.flush();
            ((FileOutputStream)output).getFD().sync();
        }catch(Exception error){temp.delete();throw error;}
        String ext;
        try{ext=fileType(temp);}catch(Exception error){temp.delete();throw error;}
        if(!ext.equals("mp4") && total>MAX_IMAGE){temp.delete();throw new IllegalArgumentException("REFERENCE_IMAGE_TOO_LARGE");}
        String hash=AgentPolicy.hex(md.digest()),name=hash+"."+ext;
        File destination=ProductionFiles.file(context,"Assets",name);
        if(destination.isFile()){
            if(destination.length()!=total||!hash.equals(ProductionFiles.sha(destination))){
                temp.delete();throw new IllegalStateException("REFERENCE_HASH_CONFLICT");
            }
            temp.delete();
        }else{
            try{Files.move(temp.toPath(),destination.toPath(),StandardCopyOption.ATOMIC_MOVE);}
            catch(java.nio.file.AtomicMoveNotSupportedException e){
                Files.move(temp.toPath(),destination.toPath());
            }
        }
        return destination;
    }
    private static JSONObject metadata(Context context,File file)throws Exception{
        String name=file.getName();String hash=name.substring(0,64),ext=name.substring(65);
        JSONObject data=new JSONObject().put("asset",name).put("sha256",hash)
            .put("bytes",file.length()).put("extension",ext).put("native_import_verified",true)
            .put("gallery_browsed",false).put("original_bytes_preserved",true);
        if(ext.equals("mp4")){
            MediaMetadataRetriever retriever=new MediaMetadataRetriever();
            try{
                retriever.setDataSource(file.getAbsolutePath());
                long dur=Long.parseLong(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
                if(dur<0||dur>24L*3600*1000)throw new IllegalArgumentException("REFERENCE_VIDEO_DURATION_INVALID");
                data.put("duration_ms",dur).put("width",Integer.parseInt(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)))
                    .put("height",Integer.parseInt(retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)))
                    .put("kind","video");
            }finally{retriever.release();}
        }else{
            BitmapFactory.Options options=new BitmapFactory.Options();options.inJustDecodeBounds=true;
            BitmapFactory.decodeFile(file.getAbsolutePath(),options);
            if(options.outWidth<1||options.outHeight<1||(long)options.outWidth*options.outHeight>MAX_IMAGE_PIXELS)
                throw new IllegalArgumentException("REFERENCE_DIMENSIONS_UNSAFE");
            data.put("kind","image").put("width",options.outWidth).put("height",options.outHeight);
            if(ext.equals("jpg")){
                try(FileInputStream in=new FileInputStream(file)){
                    ExifInterface exif=new ExifInterface(in);
                    data.put("exif_orientation",exif.getAttributeInt(ExifInterface.TAG_ORIENTATION,ExifInterface.ORIENTATION_NORMAL));
                }
            }else data.put("exif_orientation",ExifInterface.ORIENTATION_NORMAL);
        }
        return data;
    }
    private static void writeMetadata(Context c,JSONObject data)throws Exception{
        File file=ProductionFiles.file(c,"Assets",data.getString("sha256")+".meta.json");
        File tmp=ProductionFiles.file(c,"Assets",data.getString("sha256")+".meta.tmp");
        try(FileOutputStream output=new FileOutputStream(tmp)){
            byte[] bytes=data.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8);
            output.write(bytes);output.getFD().sync();
        }
        try{Files.move(tmp.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);}
        catch(java.nio.file.AtomicMoveNotSupportedException e){Files.move(tmp.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING);}
    }
    public static JSONObject receive(Context context,Intent intent)throws Exception{
        List<Uri> sources=selected(intent);
        if(sources.isEmpty())throw new IllegalArgumentException("NO_OWNER_SELECTED_REFERENCE");
        JSONArray results=new JSONArray();
        for(Uri uri:sources){
            File file=store(context,uri);
            JSONObject meta=metadata(context,file);
            writeMetadata(context,meta);
            results.put(meta);
        }
        return new JSONObject().put("imported",results.length()).put("assets",results)
                .put("gallery_browsed",false).put("cloud_rendering",false);
    }
    public static JSONObject list(Context context,JSONObject p)throws Exception{
        ProductionBridge.fields(p,"offset,limit");
        int offset=(int)ProductionBridge.integer(p,"offset",0,1000000,0);
        int limit=(int)ProductionBridge.integer(p,"limit",1,50,20);
        File[] found=ProductionFiles.folder(context,"Assets").listFiles((dir,name)->name.matches("[a-f0-9]{64}\\.meta\\.json"));
        if(found==null)found=new File[0];
        java.util.Arrays.sort(found,(a,b)->a.getName().compareTo(b.getName()));
        JSONArray assets=new JSONArray();
        for(int i=offset;i<Math.min(found.length,offset+limit);i++){
            String raw=new String(Files.readAllBytes(found[i].toPath()),java.nio.charset.StandardCharsets.UTF_8);
            if(raw.length()>8192)throw new IllegalArgumentException("REFERENCE_METADATA_OVERSIZED");
            assets.put(new JSONObject(raw));
        }
        return new JSONObject().put("total",found.length).put("assets",assets)
            .put("next_offset",offset+limit<found.length?offset+limit:JSONObject.NULL);
    }
    public static JSONObject details(Context context,JSONObject p)throws Exception{
        ProductionBridge.fields(p,"asset");
        String asset=p.getString("asset");
        if(!asset.matches("[a-f0-9]{64}\\\\.(png|jpg|jpeg|webp|mp4)"))
            throw new IllegalArgumentException("INVALID_IMPORTED_ASSET_NAME");
        String hash=asset.substring(0,64);
        File meta=ProductionFiles.file(context,"Assets",hash+".meta.json");
        File original=ProductionFiles.file(context,"Assets",asset);
        if(!meta.isFile()||!original.isFile()||meta.length()>8192)
            throw new IllegalArgumentException("IMPORTED_REFERENCE_NOT_FOUND");
        JSONObject result=new JSONObject(new String(Files.readAllBytes(meta.toPath()),java.nio.charset.StandardCharsets.UTF_8));
        if(!asset.equals(result.optString("asset"))||!hash.equals(ProductionFiles.sha(original)))
            throw new IllegalArgumentException("IMPORTED_REFERENCE_HASH_MISMATCH");
        return result;
    }
    public static JSONObject sample(Context context,JSONObject p)throws Exception{
        ProductionBridge.fields(p,"asset,time_ms,width,height");
        String asset=p.getString("asset");
        if(!asset.matches("[a-f0-9]{64}\\.mp4"))throw new IllegalArgumentException("VIDEO_ASSET_NAME_REQUIRED");
        File source=ProductionFiles.file(context,"Assets",asset);
        if(!source.isFile())throw new IllegalArgumentException("VIDEO_REFERENCE_NOT_IMPORTED");
        int width=(int)ProductionBridge.integer(p,"width",64,1280,640);
        int height=(int)ProductionBridge.integer(p,"height",64,1280,640);
        if((long)width*height>1280L*1280L)throw new IllegalArgumentException("FRAME_SAMPLE_TOO_LARGE");
        long at=ProductionBridge.integer(p,"time_ms",0,24L*3600*1000,0);
        MediaMetadataRetriever r=new MediaMetadataRetriever();
        Bitmap b=null;
        try{
            r.setDataSource(source.getAbsolutePath());
            long duration=Long.parseLong(r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
            if(at>duration)throw new IllegalArgumentException("VIDEO_SAMPLE_OUTSIDE_DURATION");
            b=r.getScaledFrameAtTime(at*1000,MediaMetadataRetriever.OPTION_CLOSEST_SYNC,width,height);
            if(b==null)throw new IllegalStateException("VIDEO_FRAME_DECODE_FAILED");
            File file=ProductionFiles.file(context,"Assets",asset.substring(0,64)+"_frame_"+at+".png");
            try(FileOutputStream output=new FileOutputStream(file)){
                if(!b.compress(Bitmap.CompressFormat.PNG,100,output))throw new IllegalStateException("VIDEO_FRAME_ENCODE_FAILED");
                output.getFD().sync();
            }
            JSONObject out=ProductionFiles.receipt(file,"Assets");
            out.put("sample_time_ms",at).put("video_source_hash",asset.substring(0,64))
                .put("sample_is_full_resolution",false).put("original_video_untouched",true);
            return out;
        }finally{if(b!=null)b.recycle();r.release();}
    }
}
