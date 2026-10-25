#!/usr/bin/env python3
"""Deterministic, source-drift-checked integration into the native APK build."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

def replace(path,before,after):
    target=ROOT/path;text=target.read_text()
    if after in text:return
    if text.count(before)!=1:raise RuntimeError('SOURCE_DRIFT: '+path+' '+repr(before[:90]))
    target.write_text(text.replace(before,after,1))

def promote_startup_version():
    for name in ('app/build.gradle.kts','full-app/app/build.gradle'):
        target=ROOT/name;source=target.read_text()
        new='versionCode = 48' if name.endswith('.kts') else 'versionCode 48'
        new_name='0.39.0-agent-fastlane'
        if new in source and new_name in source:continue
        previous=[]
        for code,version in ((30,'0.28.0-native-control-reliability'),
                             (31,'0.28.1-startup-diagnostics'),
                             (32,'0.28.2-loader-diagnostics'),
                             (33,'0.28.3-vulkan-timeline-fix'),
                             (34,'0.28.4-native-launch-handoff'),
                             (35,'0.29.0-native-studio-upgrade'),
                             (36,'0.31.0-native-reliability'),
                             (37,'0.31.1-native-reliability'),
                             (38,'0.31.2-native-startup-storage'),
                             (39,'0.31.3-character-review'),
                             (40,'0.32.0-native-storage-assets'),
                             (41,'0.32.1-native-storage-assets'),
                             (42,'0.32.2-mp4-recovery'),
                             (43,'0.34.0-native-reference-motion'),
                             (44,'0.35.0-joint-multiview-fit'),
                             (45,'0.36.0-unified-blender-workspaces'),
                             (46,'0.37.0-live-sculpt-acting'),
                             (47,'0.38.0-native-ik-video-sync')):
            old='versionCode = '+str(code) if name.endswith('.kts') else 'versionCode '+str(code)
            if source.count(old)==1 and source.count(version)==1:previous.append((old,version))
        if len(previous)!=1:
            raise RuntimeError('V0290_STARTUP_VERSION_ADAPTER_DRIFT: '+name)
        old,old_name=previous[0]
        target.write_text(source.replace(old,new,1).replace(old_name,new_name,1))

def prepare():
    # Build adapters run twice in CI. The v0.22 extension intentionally adds
    # on top of the v0.21 source patch; a second run must verify the complete
    # extension rather than trying to reapply the older intermediate pattern.
    stage=(ROOT/'tools/assemble_full_native.py').read_text()
    if 'StudioLiveHandOverlay.attach(this);' in stage:
        promote_startup_version()
        required=(
            ('tools/assemble_full_native.py','render_studio_contract.py'),
            ('tools/assemble_full_native.py','render_file_ops.py'),
            ('app/src/main/java/com/rezox/render/agent/StorageOperations.java','storage.task.refresh'),
            ('app/src/main/java/com/rezox/render/agent/ProductionBridge.java','StudioReferenceInbox.list(context,p)'),
            ('full-app/scripts/render_production.py','import render_studio_ops'),
            ('full-app/app/build.gradle','versionCode 48'),
            ('app/build.gradle.kts','versionCode = 48'),
        )
        if not all(marker in (ROOT/path).read_text() for path,marker in required):
            raise RuntimeError('INCOMPLETE_V022_BUILD_ADAPTER_STATE')
        print('Render 0.39.0 adapter verified; no second mutation')
        return
    prefix='app/src/main/java/com/rezox/render/agent/'
    replace(prefix+'AgentPolicy.java','registry.put("engine.status", Collections.emptySet());','registry.put("engine.status", Collections.emptySet());\n        registry.put("production.execute", fields("operation", "payload", "target_id"));')
    replace(prefix+'AgentActions.java','if(field.equals("assembly")){','if(field.equals("operation")){\n                    prop.put("type","string");\n                }else if(field.equals("payload")){\n                    prop.put("type","object");\n                }else if(field.equals("target_id")){\n                    prop.put("type","string").put("pattern","^[a-fA-F0-9-]{36}$");\n                }else if(field.equals("assembly")){')
    replace(prefix+'AgentActions.java','String[] required = id.equals("blender.scene.batch_assembly")','String[] required = id.equals("production.execute") ? new String[]{"operation"} : id.equals("blender.scene.batch_assembly")')
    replace(prefix+'AgentActions.java','.put("read_only",!bpy || id.equals("blender.scene.summary")','.put("read_only",(!bpy && !id.equals("production.execute")) || id.equals("blender.scene.summary")')
    replace(prefix+'AgentActions.java','checkCancelled(cancelled);\n        if (action.equals("agent.capabilities"))','checkCancelled(cancelled);\n        if (action.equals(ProductionBridge.ACTION)) return ProductionBridge.execute(context,args,cancelled);\n        if (action.equals("agent.capabilities"))')
    replace(prefix+'BlenderSpool.java','private static void checkArguments(String action, JSONObject args) throws Exception {','private static void checkArguments(String action, JSONObject args) throws Exception {\n        if("blender.production.execute".equals(action)){ProductionBridge.validate(args);return;}')
    replace(prefix+'BlenderSpool.java','long timeoutMillis=action.equals("blender.scene.render_video") ? 1800000L :','long timeoutMillis=action.equals("blender.production.execute") ? 600000L :\n            action.equals("blender.scene.render_video") ? 1800000L :')
    replace(prefix+'BlenderSpool.java','if(contents.length>65536)','if(contents.length>131072)')
    service=ROOT/(prefix+'VideoStudioNativeBridgeService.java');text=service.read_text()
    if 'raw.length()>32768' in text:service.write_text(text.replace('raw.length()>32768','raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>131072'))
    elif 'length>131072' not in text:raise RuntimeError('SOURCE_DRIFT: Binder payload bound')
    replace('full-app/scripts/render_agent_startup.py','_MAX_BYTES = 65536','_MAX_BYTES = 131072')
    before='    # Local touch-overlay UI operations; NOT remotely registered agent actions.'
    after='''    if action == "blender.production.execute":
        import importlib.util
        module_path = Path(__file__).with_name("render_production.py")
        module_spec = importlib.util.spec_from_file_location("render_production", module_path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module.execute(args, ROOT, command.get("id"))
'''+before
    replace('full-app/scripts/render_agent_startup.py',before,after)
    before='''            packed.write(scene_py, "scripts/startup/render_lively_scene.py",
                         compress_type=zipfile.ZIP_DEFLATED)'''
    after=before+'''
        for name in ("render_production.py", "render_production_contract.py"):
            source = Path(source_py).with_name(name)
            if not source.is_file():
                raise ValueError("PRODUCTION_RUNTIME_NOT_PACKAGED")
            packed.write(source, "scripts/startup/" + name,
                         compress_type=zipfile.ZIP_DEFLATED)'''
    replace('tools/assemble_full_native.py',before,after)
    replace('tools/assemble_full_native.py','java = java.replace(old_launch, "    BlenderMobileControls.attach(this);", 1)','java = java.replace(old_launch, "    BlenderMobileControls.attach(this);\\n    com.rezox.render.agent.ProductionCapture.attach(this);", 1)')
    replace('app/src/test/java/com/rezox/render/agent/AgentPolicyTest.java','assertEquals(25,AgentPolicy.ACTIONS.size());','assertEquals(26,AgentPolicy.ACTIONS.size());\n        assertTrue(AgentPolicy.ACTIONS.containsKey("production.execute"));')
    for name in ('full-app/app/build.gradle','app/build.gradle.kts'):
        path=ROOT/name;s=path.read_text()
        s=re.sub(r'versionCode\s*(?:=\s*)?\d+',lambda match:'versionCode = 24' if name.endswith('.kts') else 'versionCode 24',s,count=1)
        s=re.sub(r'versionName\s*(?:=\s*)?[\"\'][^\"\']+[\"\']',lambda match:'versionName = "0.21.0-native-thermal-batch-drive"' if name.endswith('.kts') else "versionName '0.21.0-native-thermal-batch-drive'",s,count=1)
        path.write_text(s)
    from harden_production_runtime import apply
    apply(ROOT)
    from prepare_v23_reference import apply as install_reference_studio
    install_reference_studio()
    # v0.24 is an in-place successor; never silently downgrade an already
    # installed v0.22, rotate its signer, or change the Android package name.
    for name in ('app/build.gradle.kts','full-app/app/build.gradle'):
        target=ROOT/name
        source=target.read_text()
        before='versionCode = 25' if name.endswith('.kts') else 'versionCode 25'
        after='versionCode = 26' if name.endswith('.kts') else 'versionCode 26'
        if source.count(before)!=1:
            raise RuntimeError('V024_VERSION_ADAPTER_DRIFT: '+name)
        source=source.replace(before,after,1)
        source=source.replace('0.22.0-native-reference-precision',
            '0.24.0-native-continuity-assets')
        target.write_text(source)
    # Strict monotonic Android version, original package and same signing identity.
    for name in ('app/build.gradle.kts','full-app/app/build.gradle'):
        target=ROOT/name
        source=target.read_text()
        before='versionCode = 26' if name.endswith('.kts') else 'versionCode 26'
        after='versionCode = 27' if name.endswith('.kts') else 'versionCode 27'
        if source.count(before)!=1:
            raise RuntimeError('V025_VERSION_ADAPTER_DRIFT: '+name)
        source=source.replace(before,after,1).replace(
            '0.24.0-native-continuity-assets','0.25.0-native-verified-recovery')
        target.write_text(source)
    # OMEGA combined development candidate must be newer than 0.25, and
    # preserve the SAME com.rezox.render package and original signer.
    for name in ('app/build.gradle.kts','full-app/app/build.gradle'):
        target=ROOT/name
        source=target.read_text()
        older='versionCode = 27' if name.endswith('.kts') else 'versionCode 27'
        newer='versionCode = 28' if name.endswith('.kts') else 'versionCode 28'
        if source.count(older)!=1:
            raise RuntimeError('OMEGA_INPLACE_VERSION_ADAPTER_DRIFT: '+name)
        source=source.replace(older,newer,1)
        source=source.replace('0.25.0-native-verified-recovery','0.26.0-omega-test-candidate')
        target.write_text(source)
    # 0.27 retains the same com.rezox.render Android identity and the exact
    # original install-compatible development signer. APK install is NEVER
    # attempted by the build adapter.
    for name in ('app/build.gradle.kts','full-app/app/build.gradle'):
        target=ROOT/name
        source=target.read_text()
        old='versionCode = 28' if name.endswith('.kts') else 'versionCode 28'
        new='versionCode = 29' if name.endswith('.kts') else 'versionCode 29'
        if source.count(old)!=1:
            raise RuntimeError('V027_MONOTONIC_VERSION_ADAPTER_DRIFT: '+name)
        source=source.replace(old,new,1).replace(
            '0.26.0-omega-test-candidate','0.27.0-resumable-long-render')
        target.write_text(source)
    # 0.28 fixes thermal scheduling and visible native pause state. Preparing
    # a build does not install it or prove the device's signing identity.
    for name in ('app/build.gradle.kts','full-app/app/build.gradle'):
        target=ROOT/name
        source=target.read_text()
        old='versionCode = 29' if name.endswith('.kts') else 'versionCode 29'
        new='versionCode = 30' if name.endswith('.kts') else 'versionCode 30'
        if source.count(old)!=1:
            raise RuntimeError('V028_MONOTONIC_VERSION_ADAPTER_DRIFT: '+name)
        source=source.replace(old,new,1).replace(
            '0.27.0-resumable-long-render','0.28.0-native-control-reliability')
        target.write_text(source)
    promote_startup_version()
    print('RENDER 0.39.0 source staged (versionCode 48); signing must be verified by the build')
if __name__=='__main__':prepare()
