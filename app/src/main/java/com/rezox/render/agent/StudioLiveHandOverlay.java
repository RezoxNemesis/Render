package com.rezox.render.agent;

import android.app.Activity;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import org.json.JSONObject;
import java.lang.ref.WeakReference;

/** Non-clickable, owner-visible hand: tracks REAL touch coordinates or the
 * confirmed native bpy command status. Never animates fictional menu taps.
 */
public final class StudioLiveHandOverlay {
    private static volatile WeakReference<Activity> owner=new WeakReference<>(null);
    private static volatile Overlay overlay;
    private static volatile float lastX=-1,lastY=-1;
    private static volatile long lastTouch=0L;
    private StudioLiveHandOverlay(){}

    public static void attach(Activity activity){
        if(Looper.myLooper()!=Looper.getMainLooper()){
            activity.runOnUiThread(()->attach(activity));return;
        }
        detachInternal();
        owner=new WeakReference<>(activity);
        View root=activity.getWindow().getDecorView();
        if(!(root instanceof ViewGroup))return;
        Overlay hand=new Overlay(activity);
        hand.setClickable(false);hand.setFocusable(false);
        hand.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        int width=(int)(230*activity.getResources().getDisplayMetrics().density);
        int height=(int)(75*activity.getResources().getDisplayMetrics().density);
        FrameLayout.LayoutParams params=new FrameLayout.LayoutParams(width,height,Gravity.TOP|Gravity.END);
        params.topMargin=(int)(15*activity.getResources().getDisplayMetrics().density);
        params.rightMargin=(int)(12*activity.getResources().getDisplayMetrics().density);
        ((ViewGroup)root).addView(hand,params);
        overlay=hand;hand.resume();
    }
    public static void detach(Activity activity){
        if(Looper.myLooper()!=Looper.getMainLooper()){activity.runOnUiThread(()->detach(activity));return;}
        if(owner.get()==activity)detachInternal();
    }
    private static void detachInternal(){
        Overlay previous=overlay;
        if(previous!=null){
            previous.stop();
            if(previous.getParent() instanceof ViewGroup)
                ((ViewGroup)previous.getParent()).removeView(previous);
        }
        overlay=null;owner=new WeakReference<>(null);
    }
    public static void onRealTouch(MotionEvent event){
        // Real owner touch only, already delivered to Blender's NativeActivity.
        if(event==null)return;
        int action=event.getActionMasked();
        if(action==MotionEvent.ACTION_DOWN||action==MotionEvent.ACTION_MOVE){
            lastX=event.getX();lastY=event.getY();
            lastTouch=android.os.SystemClock.elapsedRealtime();
            Overlay view=overlay;
            if(view!=null)view.post(view::invalidate);
        }
    }
    public static JSONObject snapshot(Context context)throws Exception{
        AgentWorkPresence.Snapshot state=AgentWorkPresence.snapshot(context);
        Activity active=owner.get();
        long age=android.os.SystemClock.elapsedRealtime()-lastTouch;
        boolean recent=lastTouch>0&&age>=0&&age<4000;
        return new JSONObject()
            .put("native_status",state.state)
            .put("native_action",state.action)
            .put("native_stage",state.stage)
            .put("progress",state.progress)
            .put("working",state.isWorking())
            .put("shown_in_native_editor",active!=null&&overlay!=null&&overlay.getParent()!=null)
            .put("hand_tracking_mode",recent?"actual_owner_touch":state.isWorking()?"native_bpy_status":"idle")
            .put("last_touch_is_real_user_event",recent)
            .put("last_owner_touch_x",recent?lastX:JSONObject.NULL)
            .put("last_owner_touch_y",recent?lastY:JSONObject.NULL)
            .put("fabricated_ui_taps",false)
            .put("native_api_command_not_equivalent_to_menu_click",true)
            .put("unrelated_apps_controlled",false);
    }
    private static final class Overlay extends View {
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Handler handler=new Handler(Looper.getMainLooper());
        private boolean active;
        private final Runnable refresh=new Runnable(){@Override public void run(){
            if(!active)return;
            invalidate();
            handler.postDelayed(this,650);
        }};
        Overlay(Context c){super(c);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
        void resume(){active=true;handler.post(refresh);}
        void stop(){active=false;handler.removeCallbacks(refresh);}
        @Override protected void onDraw(Canvas canvas){
            super.onDraw(canvas);
            AgentWorkPresence.Snapshot state=AgentWorkPresence.snapshot(getContext());
            long elapsed=android.os.SystemClock.elapsedRealtime()-lastTouch;
            boolean touched=lastTouch>0&&elapsed>=0&&elapsed<2500;
            if(!state.isWorking()&&!touched)return;
            float scale=getResources().getDisplayMetrics().density;
            paint.setColor(0xD9293037);paint.setStyle(Paint.Style.FILL);
            canvas.drawRoundRect(new RectF(0,0,getWidth(),getHeight()),14*scale,14*scale,paint);
            paint.setColor(Color.WHITE);paint.setTextSize(24*scale);
            canvas.drawText(touched?"☝":"✋",12*scale,36*scale,paint);
            paint.setTextSize(11*scale);
            String label=touched?"Real finger gesture":state.action;
            if(label.length()>28)label=label.substring(0,25)+"...";
            canvas.drawText(label,53*scale,27*scale,paint);
            paint.setColor(0xffa7d0ff);paint.setTextSize(10*scale);
            canvas.drawText(touched?"Owner touch, passed through": "Native bpy API • no fake taps",
                    53*scale,45*scale,paint);
            if(state.isWorking()&&state.progress>=0){
                paint.setColor(0xff79b3ff);
                canvas.drawRect(53*scale,57*scale,
                    (53+(160*state.progress/100f))*scale,60*scale,paint);
            }
        }
    }
}
