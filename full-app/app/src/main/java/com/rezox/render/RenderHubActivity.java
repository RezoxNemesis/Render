package com.rezox.render;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** One APK: real upstream Blender editor plus Render's native ChatGPT agent. */
public final class RenderHubActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(24 * getResources().getDisplayMetrics().density);
        content.setPadding(pad,pad,pad,pad);
        scroll.addView(content);
        setContentView(scroll);

        TextView title = label(content, "Render Studio", 28);
        title.setTypeface(null, Typeface.BOLD);
        label(content, "Full native Blender engine on Android — Experimental", 16);
        label(content, "Real modeling, sculpting, animation, Python and rendering use the GPL-licensed Blender Android full engine. Performance and feature support depend on Android GPU drivers and available memory.", 14);
        button(content, "Open full Blender editor", () ->
            startActivity(new Intent().setClassName(this,"org.blender.blender.BlenderActivity")));
        button(content, "ChatGPT × Render agent", () ->
            startActivity(new Intent(this,com.rezox.render.agent.AgentActivity.class)));
        button(content, "Project import and file inspection", () ->
            startActivity(new Intent(this,MainActivity.class)));
        label(content, "The agent can inspect Blender’s live scene and create a cube through its native bpy timer after the editor opens. More Blender actions will be added through the same typed bridge. Full rendering workflows still require integration and phone testing.", 14);
        label(content, "Back up projects before testing experimental APKs. This is not an official Blender Foundation product.", 13);
    }
    private TextView label(LinearLayout content,String value,int size) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(size); view.setPadding(0,10,0,16);
        content.addView(view); return view;
    }
    private void button(LinearLayout content,String label,Runnable action) {
        Button button = new Button(this);button.setText(label);
        content.addView(button,new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,ViewGroup.LayoutParams.WRAP_CONTENT));
        button.setOnClickListener(v -> action.run());
    }
}
