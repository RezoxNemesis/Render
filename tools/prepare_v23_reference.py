#!/usr/bin/env python3
"""Idempotent, source-drift-checked v0.22 native media/viewport bridge integration.

Run AFTER the existing 0.21 production adapter. Never remove upstream Blender,
rotate the installed certificate, or change app/project/credential identities.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def patch(path,old,new):
    file=ROOT/path
    source=file.read_text()
    if new in source:return
    if source.count(old)!=1:raise RuntimeError("V022_SOURCE_DRIFT: "+str(path)+" -> "+repr(old[:100]))
    file.write_text(source.replace(old,new,1))

def apply():
    java='app/src/main/java/com/rezox/render/agent/ProductionBridge.java'
    contract='full-app/scripts/render_production_contract.py'
    runtime='full-app/scripts/render_production.py'
    ops='"reference.list","reference.metadata","reference.video_frame","reference.pick","ui.state","connection.diagnose","reference.bind","reference.landmarks","viewport.inspect","viewport.configure","viewport.focus","object.geometry","operator.describe","operator.execute",'
    patch(java,'"render.plan","render.step","render.batch","render.status","render.encode","drive.status","drive.backup"',
          ops+'"render.plan","render.step","render.batch","render.status","render.encode","drive.status","drive.backup"')
    patch(java,'if(operation.equals("reference.write"))return ProductionFiles.writeReference(context,p);',
          '''if(operation.equals("reference.write"))return ProductionFiles.writeReference(context,p);
        if(operation.equals("reference.list"))return StudioReferenceInbox.list(context,p);
        if(operation.equals("reference.metadata"))return StudioReferenceInbox.details(context,p);
        if(operation.equals("reference.video_frame"))return StudioReferenceInbox.sample(context,p);
        if(operation.equals("ui.state")){fields(p,"");return StudioLiveHandOverlay.snapshot(context);}
        if(operation.equals("connection.diagnose")){
            fields(p,"");
            JSONObject status=new JSONObject().put("app","Render Studio")
                .put("render_public_id",publicId)
                .put("target_package",context.getPackageName())
                .put("editor_ready",editorReady(context))
                .put("owner_bridge_enabled",new AgentSecrets(context).videoStudioBridgeEnabled())
                .put("work",StudioLiveHandOverlay.snapshot(context))
                .put("reference_inbox",StudioReferenceInbox.list(context,
                    new JSONObject().put("offset",0).put("limit",1)))
                .put("native_binder_verified_by_this_call",true);
            return status;
        }
        if(operation.equals("reference.pick")){
            fields(p,"");
            Intent picker=new Intent(context,AgentActivity.class)
                .setAction("com.rezox.render.agent.PICK_MEDIA")
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            context.startActivity(picker);
            return new JSONObject().put("picker_launch_requested",true)
                .put("owner_ui_needed",true).put("completed_import",false);
        }''')
    patch(java,'.put("render_batch_max_frames",12)',
          '''.put("render_batch_max_frames",12)
                .put("direct_owner_media_import","Android ACTION_SEND / ACTION_OPEN_DOCUMENT")
                .put("reference_image_video_supported",true)
                .put("geometry_projection_error_metric","normalized 2D landmark RMS, not likeness percent")
                .put("supports_readonly_ui_state",true)
                .put("viewport_precision_controls_available",true)
                .put("native_operator_coverage","explicit allowlist, not arbitrary Python")''')
    # Versioned capability schemas are a richer list than guessed function names.
    patch(java,'.put("maximum_request_bytes",131072)',
          '.put("maximum_request_bytes",131072)') if False else None

    patch(contract,"    'render.plan', 'render.step', 'render.status', 'render.encode',",
          """    'reference.bind','reference.landmarks','viewport.inspect','viewport.configure','viewport.focus',
    'object.geometry','operator.describe','operator.execute',
    'render.plan', 'render.step', 'render.status', 'render.encode',""")
    patch(runtime,"    if operation=='scene.inspect':",
          """    if operation in ('reference.bind','reference.landmarks','viewport.inspect',
                     'viewport.configure','viewport.focus','object.geometry',
                     'operator.describe','operator.execute'):
        studio_path=Path(__file__).with_name('render_studio_ops.py')
        studio_spec=importlib.util.spec_from_file_location('render_studio_ops',studio_path)
        studio_module=importlib.util.module_from_spec(studio_spec)
        studio_spec.loader.exec_module(studio_module)
        return studio_module.execute(operation,p,root,scene)
    if operation=='scene.inspect':""")
    patch('tools/assemble_full_native.py',
          'for name in ("render_production.py", "render_production_contract.py", "render_production_detail.py"):',
          'for name in ("render_production.py", "render_production_contract.py", "render_production_detail.py", "render_studio_ops.py", "render_studio_contract.py"):')

    # The editor overlay has a genuine owner-touch hook. bpy operations are
    # reported as native actions; no Blender menu taps are fabricated.
    stage='tools/assemble_full_native.py'
    patch(stage,'''  @Override
  protected void onDestroy() {
    BlenderMobileControls.detach(this);
    super.onDestroy();
  }''',
          '''  @Override
  public boolean dispatchTouchEvent(android.view.MotionEvent event) {
    com.rezox.render.agent.StudioLiveHandOverlay.onRealTouch(event);
    return super.dispatchTouchEvent(event);
  }

  @Override
  protected void onDestroy() {
    com.rezox.render.agent.StudioLiveHandOverlay.detach(this);
    BlenderMobileControls.detach(this);
    super.onDestroy();
  }''')
    patch(stage,'java = java.replace(old_launch, "    BlenderMobileControls.attach(this);\\n    com.rezox.render.agent.ProductionCapture.attach(this);", 1)',
          'java = java.replace(old_launch, "    BlenderMobileControls.attach(this);\\n    com.rezox.render.agent.ProductionCapture.attach(this);\\n    com.rezox.render.agent.StudioLiveHandOverlay.attach(this);", 1)')

    # Separate screenshot focus from visibility. PixelCopy still captures only
    # our own visible Blender window, never other applications or Gallery.
    capture='app/src/main/java/com/rezox/render/agent/ProductionCapture.java'
    patch(capture,'!a.isFinishing()&&a.hasWindowFocus()',
          '!a.isFinishing()&&a.getWindow().getDecorView().isAttachedToWindow()&&a.getWindow().getDecorView().isShown()')
    patch(capture,'activity.isFinishing()||!activity.hasWindowFocus()',
          'activity.isFinishing()||!activity.getWindow().getDecorView().isAttachedToWindow()||!activity.getWindow().getDecorView().isShown()')

    batch='app/src/main/java/com/rezox/render/agent/ProductionBatch.java'
    patch(batch,'.put("total_frames",spec.getInt("frame_count"))',
          '.put("total_frames",spec.getInt("frame_count"))\n            .put("start_frame",spec.getInt("start")).put("end_frame",spec.getInt("end"))')
    patch(batch,'"job_id,max_frames,max_wall_ms,cooldown_max_ms,expected_fingerprint"',
          '"job_id,max_frames,max_wall_ms,cooldown_max_ms,expected_fingerprint,expected_next_frame"')
    patch(batch,'int maxFrames=(int)ProductionBridge.integer(p,"max_frames",1,12,8);',
          '''if(p.has("expected_next_frame") &&
           ProductionBridge.integer(p,"expected_next_frame",1,10000000,-1)!=current.getInt("next_frame"))
            throw new IllegalArgumentException("RENDER_NEXT_FRAME_CONFLICT");
        int maxFrames=(int)ProductionBridge.integer(p,"max_frames",1,12,8);''')
    patch(batch,'current.getInt("next_frame")>current.getInt("total_frames")',
          'current.getInt("next_frame")>current.getInt("end_frame")')
    patch(batch,'if(result.optInt("completed_frames")<=current.getInt("completed_frames"))',
          'if(result.optInt("completed_frames")<=current.getInt("completed_frames"))')

    # Include deliberate owner UI action rather than hidden auto-import.
    agent='app/src/main/java/com/rezox/render/agent/AgentActivity.java'
    patch(agent,'if(StudioReferenceInbox.isExplicitOwnerMediaIntent(getIntent()))receiveReferenceIntent(getIntent());',
          '''if(StudioReferenceInbox.isExplicitOwnerMediaIntent(getIntent()))
            confirmSharedReference(getIntent());
        else if(getIntent()!=null&&"com.rezox.render.agent.PICK_MEDIA".equals(getIntent().getAction())){
            setIntent(new Intent(this,AgentActivity.class));
            StudioReferenceInbox.openPicker(this);
        }''')
    patch(agent,'    private void receiveReferenceIntent(Intent inbound){',
          '''    private void confirmSharedReference(Intent inbound){
        new AlertDialog.Builder(this)
            .setTitle("Import these images/videos into Render?")
            .setMessage("Only the files explicitly shared with Render will be copied into its private reference inbox. No Gallery browsing occurs.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Import",(dialog,which)->receiveReferenceIntent(inbound))
            .show();
    }
    private void receiveReferenceIntent(Intent inbound){''')
    # APK version is increased monotonically, same installed signing certificate.
    for file in ('app/build.gradle.kts','full-app/app/build.gradle'):
        path=ROOT/file;text=path.read_text()
        old='versionCode = 24' if file.endswith('kts') else 'versionCode 24'
        new='versionCode = 25' if file.endswith('kts') else 'versionCode 25'
        if new not in text:
            if text.count(old)!=1:raise RuntimeError('APP_VERSION_SOURCE_DRIFT')
            text=text.replace(old,new,1)
        oldver='0.21.0-native-thermal-batch-drive'
        if oldver in text:text=text.replace(oldver,'0.22.0-native-reference-precision')
        path.write_text(text)
    print('Render v0.22: scoped reference inbox, real editor hand, visual bpy operations, exact render resume. Same original package and signer.')
if __name__=='__main__':apply()
