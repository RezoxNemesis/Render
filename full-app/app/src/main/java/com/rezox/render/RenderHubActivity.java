package com.rezox.render;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.rezox.render.ui.StudioUi;
import com.rezox.render.ui.StudioViewportArt;

/**
 * Render Studio's native mobile dashboard. Every CTA opens a real installed
 * Android Activity; no inert promotional tiles or unsupported capabilities.
 */
public final class RenderHubActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout page=StudioUi.page(this);
        LinearLayout brand=StudioUi.row(this);
        TextView mark=StudioUi.text(this,"R",20,0xFF191218,true);
        mark.setGravity(Gravity.CENTER);
        mark.setBackground(StudioUi.gradient(this,0xFFFFAF73,StudioUi.ORANGE,0,15));
        brand.addView(mark,new LinearLayout.LayoutParams(StudioUi.dp(this,48),StudioUi.dp(this,48)));
        LinearLayout wordmark=StudioUi.column(this);
        wordmark.setPadding(StudioUi.dp(this,12),0,0,0);
        StudioUi.add(wordmark,StudioUi.text(this,"RENDER",18,StudioUi.WHITE,true));
        StudioUi.add(wordmark,StudioUi.label(this,"Studio / Native Android"));
        brand.addView(wordmark,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        brand.addView(StudioUi.chip(this,"●  LOCAL",StudioUi.GREEN));
        StudioUi.add(page,brand);
        StudioUi.space(page,30);

        StudioUi.add(page,StudioUi.label(this,"CREATION SPACE  /  V 0.15"));
        StudioUi.space(page,10);
        StudioUi.add(page,StudioUi.text(this,"Your 3D studio.\nNow in your pocket.",31,StudioUi.WHITE,true));
        StudioUi.space(page,9);
        StudioUi.add(page,StudioUi.text(this,
            "Design, animate and create with a genuine on-device Blender engine. Tools and performance depend on your phone's GPU and memory.",
            14,StudioUi.MUTED,false));
        StudioUi.space(page,22);

        // App-native 3D illustration, not a flat stock image or an unrelated editor.
        LinearLayout visual=StudioUi.column(this);
        visual.setBackground(StudioUi.gradient(this,0xFF2A2632,0xFF10151E,StudioUi.BORDER,22));
        TextView visualTitle=StudioUi.text(this,"NATIVE VIEWPORT  /  3D",11,StudioUi.WHITE,true);
        visualTitle.setLetterSpacing(.09f);
        visualTitle.setPadding(StudioUi.dp(this,16),StudioUi.dp(this,15),0,0);
        StudioUi.add(visual,visualTitle);
        StudioViewportArt artwork=new StudioViewportArt(this);
        visual.addView(artwork,new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,StudioUi.dp(this,218)));
        StudioUi.add(page,visual);
        StudioUi.space(page,20);

        LinearLayout editor=StudioUi.card(this);
        LinearLayout editorHead=StudioUi.row(this);
        TextView editorIcon=StudioUi.chip(this,"◈",StudioUi.ORANGE);
        editorHead.addView(editorIcon);
        TextView editorTop=StudioUi.text(this,"  FULL 3D WORKSPACE",13,StudioUi.WHITE,true);
        editorHead.addView(editorTop,new LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1));
        editorHead.addView(StudioUi.chip(this,"EXPERIMENTAL",StudioUi.ORANGE));
        StudioUi.add(editor,editorHead);
        StudioUi.space(editor,15);
        StudioUi.add(editor,StudioUi.text(this,"Blender Editor",24,StudioUi.WHITE,true));
        StudioUi.space(editor,5);
        StudioUi.add(editor,StudioUi.text(this,
            "Model  •  Sculpt  •  Rig  •  Animate  •  Render",13,StudioUi.MUTED,false));
        StudioUi.space(editor,17);
        StudioUi.add(editor,StudioUi.text(this,
            "PORTRAIT: a touch-size viewport with a focus toggle. LANDSCAPE: the complete Blender multi-panel desktop layout. All native tools and render quality are retained.",
            12,StudioUi.MUTED,false));
        StudioUi.space(editor,14);
        TextView open=StudioUi.action(this,"OPEN PORTRAIT FOCUS     ↗",StudioUi.PRIMARY);
        StudioUi.add(editor,open);
        open.setContentDescription("Open Blender portrait mobile viewport focus");
        open.setOnClickListener(v->launchEditor("portrait"));
        StudioUi.space(editor,9);
        TextView landscape=StudioUi.action(this,"OPEN FULL LANDSCAPE EDITOR     ↗",StudioUi.SECONDARY);
        StudioUi.add(editor,landscape);
        landscape.setContentDescription("Open full native Blender landscape studio");
        landscape.setOnClickListener(v->launchEditor("landscape"));
        StudioUi.add(page,editor);
        StudioUi.space(page,14);

        LinearLayout agent=StudioUi.violetCard(this);
        StudioUi.add(agent,StudioUi.label(this,"AUTOMATION  /  AI ASSISTANT"));
        StudioUi.space(agent,8);
        StudioUi.add(agent,StudioUi.text(this,"ChatGPT × Render",22,StudioUi.WHITE,true));
        StudioUi.space(agent,5);
        StudioUi.add(agent,StudioUi.text(this,
            "Pair your private relay, inspect native actions, run approved tasks and view activity history.",
            13,0xFFC1B8DA,false));
        StudioUi.space(agent,15);
        TextView bridge=StudioUi.action(this,"OPEN AGENT CONTROL     →",StudioUi.PURPLE);
        StudioUi.add(agent,bridge);
        bridge.setOnClickListener(v->startActivity(new Intent(this,com.rezox.render.agent.AgentActivity.class)));
        StudioUi.add(page,agent);
        StudioUi.space(page,14);

        LinearLayout projects=StudioUi.card(this);
        StudioUi.add(projects,StudioUi.label(this,"WORKFLOW  /  FILES"));
        StudioUi.space(projects,7);
        StudioUi.add(projects,StudioUi.text(this,"Project Library",21,StudioUi.WHITE,true));
        StudioUi.space(projects,4);
        StudioUi.add(projects,StudioUi.text(this,
            "Import a .blend file, inspect scene data and check device Vulkan capability.",
            13,StudioUi.MUTED,false));
        StudioUi.space(projects,15);
        TextView library=StudioUi.action(this,"IMPORT / INSPECT PROJECTS     →",StudioUi.SECONDARY);
        StudioUi.add(projects,library);
        library.setOnClickListener(v->startActivity(new Intent(this,MainActivity.class)));
        StudioUi.add(page,projects);
        StudioUi.space(page,24);
        StudioUi.add(page,StudioUi.label(this,"LOCAL FIRST   /   FILES STAY ON DEVICE"));
        StudioUi.space(page,6);
        StudioUi.add(page,StudioUi.text(this,
            "Render is an independent experimental Android port. The real editor requires compatible Vulkan drivers; the agent's relay only transfers commands and results.",
            12,StudioUi.MUTED,false));
    }
    private void launchEditor(String mode) {
        org.blender.blender.BlenderMobileControls.setMode(this,mode);
        startActivity(new Intent(this,EditorLaunchActivity.class));
    }
}
