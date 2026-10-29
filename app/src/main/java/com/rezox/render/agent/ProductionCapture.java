package com.rezox.render.agent;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.os.Handler;
import android.os.Looper;
import android.view.PixelCopy;
import android.view.View;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.lang.ref.WeakReference;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Captures only the owner-visible Render native window; never another app or Gallery. */
public final class ProductionCapture {
    private static volatile WeakReference<Activity> active=new WeakReference<>(null);
    private ProductionCapture(){}
    public static void attach(Activity activity){active=new WeakReference<>(activity);}
    public static boolean available(){Activity a=active.get();return a!=null&&!a.isDestroyed()&&!a.isFinishing()&&a.getWindow().getDecorView().isAttachedToWindow()&&a.getWindow().getDecorView().isShown();}
    private static final class Pending {
        boolean abandoned;Bitmap bitmap;Exception error;
        synchronized void complete(Bitmap value,Exception failure){
            if(abandoned){if(value!=null&&!value.isRecycled())value.recycle();return;}
            bitmap=value;error=failure;
        }
        synchronized void abandon(){abandoned=true;if(bitmap!=null&&!bitmap.isRecycled())bitmap.recycle();bitmap=null;}
        synchronized boolean cancelled(){return abandoned;}
    }
    public static JSONObject capture(Context context)throws Exception {
        return captureInternal(context,false,0);
    }
    /** A lightweight preview from the exact same PixelCopy path as the full PNG. */
    public static JSONObject preview(Context context,JSONObject options)throws Exception {
        ProductionBridge.fields(options,"max_width");
        int maxWidth=(int)ProductionBridge.integer(options,"max_width",320,1280,960);
        return captureInternal(context,true,maxWidth);
    }
    private static JSONObject captureInternal(Context context,boolean preview,int maxWidth)throws Exception {
        if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("CAPTURE_WORKER_REQUIRED");
        Activity activity=active.get();
        if(activity==null||activity.isDestroyed()||activity.isFinishing()||!activity.getWindow().getDecorView().isAttachedToWindow()||!activity.getWindow().getDecorView().isShown())throw new IllegalStateException("RENDER_WINDOW_NOT_VISIBLE");
        CountDownLatch latch=new CountDownLatch(1);Pending pending=new Pending();
        new Handler(Looper.getMainLooper()).post(()->{
            if(pending.cancelled()){latch.countDown();return;}
            Bitmap bitmap=null;
            try{
                View view=activity.getWindow().getDecorView();int width=view.getWidth(),height=view.getHeight();
                if(width<1||height<1||(long)width*height>16_000_000L)throw new IllegalStateException("CAPTURE_SIZE_UNAVAILABLE");
                ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();ActivityManager manager=context.getSystemService(ActivityManager.class);
                if(manager!=null){manager.getMemoryInfo(memory);if(memory.lowMemory||memory.availMem<(long)width*height*8+64L*1024*1024)throw new IllegalStateException("PAUSED_MEMORY_PRESSURE");}
                bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);final Bitmap target=bitmap;
                PixelCopy.request(activity.getWindow(),target,status->{
                    if(status==PixelCopy.SUCCESS)pending.complete(target,null);
                    else{target.recycle();pending.complete(null,new IllegalStateException("NATIVE_WINDOW_CAPTURE_FAILED_"+status));}
                    latch.countDown();
                },new Handler(Looper.getMainLooper()));
            }catch(Exception failure){if(bitmap!=null&&!bitmap.isRecycled())bitmap.recycle();pending.complete(null,failure);latch.countDown();}
            catch(OutOfMemoryError failure){if(bitmap!=null&&!bitmap.isRecycled())bitmap.recycle();pending.complete(null,new IllegalStateException("PAUSED_MEMORY_PRESSURE"));latch.countDown();}
        });
        try{if(!latch.await(12,TimeUnit.SECONDS)){pending.abandon();throw new IllegalStateException("NATIVE_WINDOW_CAPTURE_TIMEOUT");}}
        catch(InterruptedException interrupted){pending.abandon();Thread.currentThread().interrupt();throw interrupted;}
        Bitmap bitmap;
        synchronized(pending){if(pending.error!=null)throw pending.error;bitmap=pending.bitmap;pending.bitmap=null;}
        if(bitmap==null)throw new IllegalStateException("NATIVE_WINDOW_CAPTURE_EMPTY");
        int sourceWidth=bitmap.getWidth(),sourceHeight=bitmap.getHeight();
        Bitmap encoded=bitmap;
        File file=null;
        boolean saved=false;
        try{
            if(preview && sourceWidth>maxWidth){
                int targetHeight=Math.max(1,(int)Math.round((double)sourceHeight*maxWidth/sourceWidth));
                encoded=Bitmap.createScaledBitmap(bitmap,maxWidth,targetHeight,true);
                if(encoded==null)throw new IllegalStateException("PREVIEW_SCALE_FAILED");
            }
            file=ProductionFiles.file(context,"Captures",
                (preview?"Preview_":"Capture_")+UUID.randomUUID().toString().replace("-","")+
                (preview?".jpg":".png"));
            try(FileOutputStream out=new FileOutputStream(file)){
                if(!encoded.compress(preview?Bitmap.CompressFormat.JPEG:Bitmap.CompressFormat.PNG,
                                     preview?74:100,out))
                    throw new IllegalStateException("CAPTURE_ENCODE_FAILED");
                out.getFD().sync();saved=true;
            }
            return ProductionFiles.receipt(file,"Captures")
                .put("width",encoded.getWidth()).put("height",encoded.getHeight())
                .put("source_width",sourceWidth).put("source_height",sourceHeight)
                .put("captured_surface","Render native Android window")
                .put("preview_only",preview).put("preview_lossy",preview)
                .put("preview_downscaled",preview && sourceWidth>maxWidth)
                .put("final_render_quality_unchanged",true).put("quality_reduced",false);
        }finally{
            if(encoded!=bitmap && !encoded.isRecycled())encoded.recycle();
            if(!bitmap.isRecycled())bitmap.recycle();
            if(!saved && file!=null)file.delete();
        }
    }
}
