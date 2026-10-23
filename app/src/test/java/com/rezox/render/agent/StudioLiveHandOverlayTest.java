package com.rezox.render.agent;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import org.json.JSONObject;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.Robolectric;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.android.controller.ActivityController;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.GraphicsMode;
import org.robolectric.shadows.ShadowCanvas;
import org.robolectric.shadows.ShadowSystemClock;
import java.time.Duration;
import static org.junit.Assert.*;
import static org.robolectric.Shadows.shadowOf;

/** Exercises Render's actual View drawing and lifecycle code. Recorded Canvas
 * operations are host UI evidence, not screenshots of the phone or Blender. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
@GraphicsMode(GraphicsMode.Mode.LEGACY)
public class StudioLiveHandOverlayTest {
    private ActivityController<Activity> controller;
    private Activity activity;
    private ViewGroup decor;
    private int originalChildren;
    @Before public void setUp(){
        ShadowSystemClock.advanceBy(Duration.ofSeconds(1));
        controller=Robolectric.buildActivity(Activity.class).setup();
        activity=controller.get();decor=(ViewGroup)activity.getWindow().getDecorView();
        originalChildren=decor.getChildCount();
        StudioLiveHandOverlay.attach(activity);
    }
    @After public void tearDown(){
        StudioLiveHandOverlay.detach(activity);controller.pause().stop().destroy();
    }
    private View hand(){return decor.getChildAt(decor.getChildCount()-1);}
    private View marker(){return decor.getChildAt(decor.getChildCount()-2);}
    private ShadowCanvas draw(View view){
        view.layout(0,0,750,300);
        Canvas canvas=new Canvas(Bitmap.createBitmap(750,300,Bitmap.Config.ARGB_8888));
        view.draw(canvas);return shadowOf(canvas);
    }
    private static String text(ShadowCanvas canvas){
        StringBuilder result=new StringBuilder();
        for(int i=0;i<canvas.getTextHistoryCount();i++)result.append(canvas.getDrawnTextEvent(i).text).append('\n');
        return result.toString();
    }
    private void touch(float x,float y){
        MotionEvent event=MotionEvent.obtain(SystemClock.uptimeMillis(),SystemClock.uptimeMillis(),
            MotionEvent.ACTION_DOWN,x,y,0);
        try{StudioLiveHandOverlay.onRealTouch(event);}finally{event.recycle();}
    }
    @Test public void overlayPassesInputThroughAndReattachesWithoutDuplicateViews()throws Exception{
        assertEquals(originalChildren+2,decor.getChildCount());
        assertFalse(hand().isClickable());assertFalse(hand().isFocusable());
        assertFalse(marker().isClickable());assertFalse(marker().isFocusable());
        MotionEvent event=MotionEvent.obtain(1,1,MotionEvent.ACTION_DOWN,10,10,0);
        try{assertFalse(hand().onTouchEvent(event));assertFalse(marker().onTouchEvent(event));}
        finally{event.recycle();}
        StudioLiveHandOverlay.attach(activity);
        assertEquals(originalChildren+2,decor.getChildCount());
        assertTrue(StudioLiveHandOverlay.snapshot(activity).getBoolean("shown_in_native_editor"));
        StudioLiveHandOverlay.detach(activity);assertEquals(originalChildren,decor.getChildCount());
    }
    @Test public void progressBarDrawsActualReportedFractionAndStage(){
        AgentWorkPresence.begin(activity,"render.batch","host UI fixture");
        AgentWorkPresence.stage(activity,"Rendering frame 104",60);
        ShadowCanvas canvas=draw(hand());
        assertTrue(text(canvas).contains("Rendering frame 104"));
        assertTrue(text(canvas).contains("60%"));
        assertEquals(2,canvas.getRectPaintHistoryCount());
        ShadowCanvas.RectPaintHistoryEvent track=canvas.getDrawnRect(0),fill=canvas.getDrawnRect(1);
        assertEquals(0.6f,(fill.right-fill.left)/(track.right-track.left),0.001f);
    }
    @Test public void unavailableProgressNeverDrawsACompletionPercentage(){
        AgentWorkPresence.begin(activity,"render.batch","host UI fixture");
        AgentWorkPresence.stage(activity,"Waiting for Blender receipt",-1);
        ShadowCanvas canvas=draw(hand());
        assertEquals(0,canvas.getRectPaintHistoryCount());
        assertFalse(text(canvas).contains("%"));
        assertTrue(text(canvas).contains("Waiting for native progress"));
    }
    @Test public void pausedThermalNoticeStaysVisibleAfterCommandReceipt()throws Exception{
        AgentWorkPresence.begin(activity,"render.batch","host UI fixture");
        AgentWorkPresence.stage(activity,"Rendering frame 104",60);
        AgentWorkPresence.finish(activity,"succeeded",new JSONObject().put("paused",true)
            .put("reason","PAUSED_THERMAL_PRESSURE"));
        String labels=text(draw(hand()));
        assertTrue(labels.contains("Render paused"));assertTrue(labels.contains("Waiting for Android to cool"));
        assertFalse(labels.contains("Native action confirmed"));
    }
    @Test public void arrowTracksExactTouchCoordinatesAndExpires()throws Exception{
        touch(2,3);ShadowCanvas canvas=draw(marker());
        assertTrue(canvas.hasDrawnPath());assertTrue(canvas.hasDrawnCircle());
        assertEquals(2,canvas.getDrawnCircle(0).centerX,0.01);
        assertEquals(3,canvas.getDrawnCircle(0).centerY,0.01);
        JSONObject status=StudioLiveHandOverlay.snapshot(activity);
        assertEquals(2,status.getDouble("last_owner_touch_x"),0.01);
        assertEquals(3,status.getDouble("last_owner_touch_y"),0.01);
        assertEquals("actual_owner_touch",status.getString("hand_tracking_mode"));
        ShadowSystemClock.advanceBy(Duration.ofSeconds(1));
        assertFalse(draw(marker()).hasDrawnPath());
    }
    @Test public void nativeApiActionDoesNotFabricatePointerCoordinates()throws Exception{
        AgentWorkPresence.begin(activity,"mesh.create","host UI fixture");
        StudioLiveHandOverlay.recordConfirmedResult("mesh.create",new JSONObject().put("object","TestCube"));
        assertFalse(draw(marker()).hasDrawnPath());
        JSONObject status=StudioLiveHandOverlay.snapshot(activity);
        assertTrue(status.isNull("last_owner_touch_x"));
        assertFalse(status.getBoolean("fabricated_ui_taps"));
    }
    @Test public void activityChangeClearsCoordinatesFromPreviousOrientation()throws Exception{
        touch(200,100);StudioLiveHandOverlay.attach(activity);
        assertTrue(StudioLiveHandOverlay.snapshot(activity).isNull("last_owner_touch_x"));
        assertFalse(draw(marker()).hasDrawnPath());
    }
}
