package com.rezox.render.agent;

import android.app.Activity;
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
import java.util.concurrent.atomic.AtomicReference;

/** Captures Render's own native window only, including its Vulkan surface. */
public final class ProductionCapture {
    private static volatile WeakReference<Activity> active=new WeakReference<>(null);
    private ProductionCapture(){}
    public static void attach(Activity activity){active=new WeakReference<>(activity);}
    public static boolean available(){Activity a=active.get();return a!=null&&!a.isDestroyed()&&!a.isFinishing()&&a.hasWindowFocus();}
    public static JSONObject capture(Context context)throws Exception {
        if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("CAPTURE_WORKER_REQUIRED");
        Activity activity=active.get();
        if(activity==null||activity.isDestroyed()||activity.isFinishing()||!activity.hasWindowFocus())throw new IllegalStateException("RENDER_WINDOW_NOT_VISIBLE");
        CountDownLatch latch=new CountDownLatch(1);AtomicReference<Bitmap> copied=new AtomicReference<>();AtomicReference<Exception> error=new AtomicReference<>();
        new Handler(Looper.getMainLooper()).post(()->{
            Bitmap bitmap=null;
            try{
                View view=activity.getWindow().getDecorView();int width=view.getWidth(),height=view.getHeight();
                if(width<1||height<1||(long)width*height>16_000_000L)throw new IllegalStateException("CAPTURE_SIZE_UNAVAILABLE");
                bitmap=Bitmap.createBitmap(width,height,Bitmap.Config.ARGB_8888);final Bitmap target=bitmap;
                PixelCopy.request(activity.getWindow(),target,status->{
                    if(status==PixelCopy.SUCCESS)copied.set(target);
                    else{target.recycle();error.set(new IllegalStateException("NATIVE_WINDOW_CAPTURE_FAILED_"+status));}
                    latch.countDown();
                },new Handler(Looper.getMainLooper()));
            }catch(Exception failure){if(bitmap!=null)bitmap.recycle();error.set(failure);latch.countDown();}
        });
        if(!latch.await(12,TimeUnit.SECONDS))throw new IllegalStateException("NATIVE_WINDOW_CAPTURE_TIMEOUT");
        if(error.get()!=null)throw error.get();Bitmap bitmap=copied.get();
        if(bitmap==null)throw new IllegalStateException("NATIVE_WINDOW_CAPTURE_EMPTY");
        File file=ProductionFiles.file(context,"Captures","Capture_"+UUID.randomUUID().toString().replace("-","")+".png");
        int width=bitmap.getWidth(),height=bitmap.getHeight();
        try(FileOutputStream out=new FileOutputStream(file)){
            if(!bitmap.compress(Bitmap.CompressFormat.PNG,100,out))throw new IllegalStateException("CAPTURE_ENCODE_FAILED");out.getFD().sync();
        }finally{bitmap.recycle();}
        return ProductionFiles.receipt(file,"Captures").put("width",width).put("height",height).put("captured_surface","Render native Android window").put("quality_reduced",false);
    }
}
