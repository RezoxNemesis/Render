package com.rezox.render.agent;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.shadows.ShadowSystemClock;
import java.io.File;
import java.io.FileOutputStream;
import java.time.Duration;
import static org.junit.Assert.*;

/** Pixel test of Render's own Android Canvas code under Robolectric/Skia.
 * Optional labeled PNGs are host UI fixtures, never Android-phone screenshots
 * or Blender scene/render evidence. No Blender engine runs in this test. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE,qualifiers="mdpi")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
public class StudioOverlayGraphicsTest {
    private Bitmap draw(View view){
        view.layout(0,0,250,92);
        Bitmap image=Bitmap.createBitmap(300,150,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(image);canvas.drawColor(Color.WHITE);view.draw(canvas);
        Paint label=new Paint(Paint.ANTI_ALIAS_FLAG);label.setColor(Color.DKGRAY);label.setTextSize(11);
        canvas.drawText("HOST UI TEST - NOT A PHONE CAPTURE",5,133,label);
        return image;
    }
    private void save(Bitmap bitmap,String name)throws Exception{
        String folder=System.getProperty("render.ui.artifactDir","");
        if(folder.isEmpty())return;
        File directory=new File(folder);if(!directory.isDirectory()&&!directory.mkdirs())throw new IllegalStateException("TEST_ARTIFACT_DIRECTORY_UNAVAILABLE");
        try(FileOutputStream out=new FileOutputStream(new File(directory,name))){
            assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG,100,out));
        }
    }
    @Test public void renderOwnOverlayPixelsForProgressPauseAndRealTouchArrow()throws Exception{
        ShadowSystemClock.advanceBy(Duration.ofSeconds(1));
        ActivityController<Activity> controller=Robolectric.buildActivity(Activity.class).setup();
        Activity activity=controller.get();StudioLiveHandOverlay.attach(activity);
        try{
            ViewGroup decor=(ViewGroup)activity.getWindow().getDecorView();
            View hand=decor.getChildAt(decor.getChildCount()-1),marker=decor.getChildAt(decor.getChildCount()-2);
            AgentWorkPresence.begin(activity,"render.batch","host UI fixture");
            AgentWorkPresence.stage(activity,"Rendering frame 104",60);
            Bitmap progress=draw(hand);
            try{
                assertEquals(0xff79b3ff,progress.getPixel(70,58));
                assertEquals(0xff45505c,progress.getPixel(180,58));
                save(progress,"render-progress-host-test.png");
            }finally{progress.recycle();}
            AgentWorkPresence.finish(activity,"succeeded",new JSONObject().put("paused",true)
                .put("reason","PAUSED_THERMAL_PRESSURE"));
            Bitmap paused=draw(hand);
            try{save(paused,"render-paused-host-test.png");}finally{paused.recycle();}
            MotionEvent touch=MotionEvent.obtain(SystemClock.uptimeMillis(),SystemClock.uptimeMillis(),
                MotionEvent.ACTION_DOWN,120,50,0);
            try{StudioLiveHandOverlay.onRealTouch(touch);}finally{touch.recycle();}
            Bitmap pointer=draw(marker);
            try{
                assertNotEquals(Color.WHITE,pointer.getPixel(120,50));
                save(pointer,"render-touch-arrow-host-test.png");
            }finally{pointer.recycle();}
        }finally{
            StudioLiveHandOverlay.detach(activity);controller.pause().stop().destroy();
        }
    }
}
