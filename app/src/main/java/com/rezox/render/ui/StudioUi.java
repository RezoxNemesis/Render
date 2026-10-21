package com.rezox.render.ui;

import android.app.Activity;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Render Studio UI primitives. No network UI toolkit or non-native dependencies. */
public final class StudioUi {
    public static final int BG=Color.rgb(9,12,17);
    public static final int SURFACE=Color.rgb(23,27,36);
    public static final int SURFACE2=Color.rgb(32,37,47);
    public static final int BORDER=Color.rgb(51,57,69);
    public static final int WHITE=Color.rgb(246,248,251);
    public static final int MUTED=Color.rgb(158,166,181);
    public static final int ORANGE=Color.rgb(255,143,71);
    public static final int VIOLET=Color.rgb(174,151,255);
    public static final int GREEN=Color.rgb(118,224,181);
    public static final int NEGATIVE=Color.rgb(249,137,141);

    public static final int PRIMARY=1, SECONDARY=2, PURPLE=3, DANGER=4;
    private StudioUi() {}

    public static int dp(Context c,float value) {
        return Math.round(value*c.getResources().getDisplayMetrics().density);
    }
    public static void window(Activity activity) {
        Window w=activity.getWindow();
        w.setStatusBarColor(BG);
        w.setNavigationBarColor(BG);
        w.getDecorView().setSystemUiVisibility(0); // light icons on dark bars
        w.setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
    }
    public static GradientDrawable shape(Context ctx,int fill,int stroke,int radius) {
        GradientDrawable d=new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(ctx,radius));
        if(stroke!=0)d.setStroke(dp(ctx,1),stroke);
        return d;
    }
    public static GradientDrawable gradient(Context ctx,int from,int to,int stroke,int radius) {
        GradientDrawable d=new GradientDrawable(GradientDrawable.Orientation.TL_BR,
            new int[]{from,to});
        d.setCornerRadius(dp(ctx,radius));
        if(stroke!=0)d.setStroke(dp(ctx,1),stroke);
        return d;
    }
    public static LinearLayout column(Context c) {
        LinearLayout view=new LinearLayout(c);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }
    public static LinearLayout row(Context c) {
        LinearLayout view=new LinearLayout(c);
        view.setOrientation(LinearLayout.HORIZONTAL);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }
    public static LinearLayout page(Activity activity) {
        window(activity);
        ScrollView scroll=new ScrollView(activity);
        scroll.setFillViewport(true);
        scroll.setClipToPadding(false);
        scroll.setBackgroundColor(BG);
        LinearLayout body=column(activity);
        body.setPadding(dp(activity,20),dp(activity,24),dp(activity,20),dp(activity,32));
        scroll.addView(body,new ScrollView.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
        activity.setContentView(scroll);
        return body;
    }
    public static TextView text(Context c,String value,int size,int color,boolean bold) {
        TextView v=new TextView(c);
        v.setText(value);
        v.setTextColor(color);
        v.setTextSize(size);
        v.setIncludeFontPadding(true);
        if(bold)v.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        v.setLineSpacing(dp(c,2),1.05f);
        return v;
    }
    public static TextView label(Context c,String value) {
        TextView view=text(c,value.toUpperCase(java.util.Locale.ROOT),11,MUTED,true);
        view.setLetterSpacing(.13f);
        return view;
    }
    public static TextView chip(Context c,String value,int color) {
        TextView view=text(c,value,11,color,true);
        view.setGravity(Gravity.CENTER);
        view.setPadding(dp(c,12),dp(c,7),dp(c,12),dp(c,7));
        view.setBackground(shape(c,SURFACE2,0,99));
        return view;
    }
    public static void space(LinearLayout host,int size) {
        View blank=new View(host.getContext());
        host.addView(blank,new LinearLayout.LayoutParams(1,dp(host.getContext(),size)));
    }
    public static void add(LinearLayout host,View child) {
        host.addView(child,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT));
    }
    public static LinearLayout card(Context c) {
        LinearLayout panel=column(c);
        panel.setBackground(shape(c,SURFACE,BORDER,22));
        panel.setPadding(dp(c,18),dp(c,18),dp(c,18),dp(c,18));
        return panel;
    }
    public static LinearLayout violetCard(Context c) {
        LinearLayout panel=column(c);
        panel.setBackground(gradient(c,Color.rgb(42,34,65),Color.rgb(25,26,43),
            Color.rgb(73,61,101),22));
        panel.setPadding(dp(c,18),dp(c,18),dp(c,18),dp(c,18));
        return panel;
    }
    public static TextView action(Context c,String value,int type) {
        int bg=type==PRIMARY?ORANGE:type==PURPLE?Color.rgb(107,82,179):
               type==DANGER?Color.rgb(61,34,42):SURFACE2;
        int border=type==SECONDARY?BORDER:type==DANGER?Color.rgb(110,55,64):0;
        int fg=type==PRIMARY?Color.rgb(20,18,20):type==DANGER?Color.rgb(255,183,183):WHITE;
        TextView control=text(c,value,14,fg,true);
        control.setGravity(Gravity.CENTER);
        control.setMinHeight(dp(c,50));
        control.setPadding(dp(c,16),dp(c,13),dp(c,16),dp(c,13));
        control.setClickable(true);
        control.setFocusable(true);
        control.setBackground(new RippleDrawable(
                ColorStateList.valueOf(0x55FFFFFF),
                shape(c,bg,border,14),shape(c,Color.WHITE,0,14)));
        return control;
    }
    public static EditText field(Context c,String hint,boolean password) {
        EditText view=new EditText(c);
        view.setSingleLine(true);
        view.setTextSize(14);
        view.setTextColor(WHITE);
        view.setHintTextColor(MUTED);
        view.setHint(hint);
        view.setPadding(dp(c,14),dp(c,12),dp(c,14),dp(c,12));
        view.setMinHeight(dp(c,52));
        view.setBackground(shape(c,Color.rgb(17,20,28),BORDER,14));
        view.setInputType(password?
            InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD:
            InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
        if(password){
            view.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
            view.setTransformationMethod(android.text.method.PasswordTransformationMethod.getInstance());
        }
        return view;
    }
}
