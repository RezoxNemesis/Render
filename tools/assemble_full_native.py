#!/usr/bin/env python3
"""Repackage a SHA-pinned *real* Android Blender Full engine and Render's agent
into one Android Studio project. Build-only operation; nothing downloaded on phone.
Does not claim device compatibility until the resulting APK is tested on hardware.
"""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import xml.etree.ElementTree as ET
import zipfile

UPSTREAM_COMMIT = "d93bd33cba768e19ee4387a31c0ea137ee2f0047"
ENGINE_SHA256 = "3fe775a1e14470ebfcd3c25ae32b57003433f04552f896880631ae98b1f18aea"
ENGINE_BYTES = 286561495
ANDROID = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", ANDROID[1:-1])

def verify_apk(apk, expected_size=ENGINE_BYTES, expected_digest=ENGINE_SHA256):
    apk = Path(apk)
    if apk.stat().st_size != expected_size:
        raise ValueError("PINNED_ENGINE_APK_SIZE_MISMATCH")
    h = hashlib.sha256()
    with apk.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_digest:
        raise ValueError("PINNED_ENGINE_APK_SHA256_MISMATCH")

def valid_zip_entry(info):
    name = info.filename
    p = PurePosixPath(name)
    if not name or "\\" in name or p.is_absolute() or ".." in p.parts:
        raise ValueError("UNSAFE_ENGINE_APK_MEMBER")
    # Reject symlinks and non-regular Unix file types even in a hash-verified APK.
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise ValueError("UNSAFE_ENGINE_APK_MEMBER")
    return name

def native_configuration_mask(value):
    # CONFIG_ASSETS_PATHS is a framework configuration bit, absent from the
    # public aapt flag names. An integer resource preserves it through Android's
    # normal TypedArray/package parsing. GHOST already handles CONFIG_CHANGED.
    flags = dict(mcc=1, mnc=2, locale=4, touchscreen=8, keyboard=16,
                 keyboardHidden=32, navigation=64, orientation=128,
                 screenLayout=256, uiMode=512, screenSize=1024,
                 smallestScreenSize=2048, density=4096, layoutDirection=8192,
                 colorMode=16384, grammaticalGender=32768,
                 fontWeightAdjustment=0x10000000, fontScale=0x40000000)
    result = 0
    for token in filter(None, value.split("|")):
        token = token.strip()
        if token in flags:
            result |= flags[token]
        else:
            try:
                number = int(token, 0)
            except ValueError:
                raise ValueError("UNKNOWN_UPSTREAM_NATIVE_CONFIGURATION_FLAG") from None
            if not 0 <= number <= 0xffffffff:
                raise ValueError("INVALID_UPSTREAM_NATIVE_CONFIGURATION_MASK")
            result |= number
    return result | 0x80000000


def merge_manifest(source, resources=None):
    root = ET.parse(source).getroot()
    root.attrib.pop("package", None)   # AGP 8+ namespace comes from Gradle.
    # Android 11+ package visibility: explicitly inspect only our known
    # VideoStudio native Binder carrier, never scan unrelated installed apps.
    queries = root.find("queries")
    if queries is None:
        queries = ET.Element("queries")
        root.insert(0, queries)
    if not any(p.get(ANDROID + "name") == "com.rezoxnemesis.videostudio"
               for p in queries.findall("package")):
        ET.SubElement(queries, "package", {
            ANDROID + "name": "com.rezoxnemesis.videostudio"
        })
    application = root.find("application")
    if application is None:
        raise ValueError("UPSTREAM_MANIFEST_NO_APPLICATION")
    activity = next((node for node in application.findall("activity")
                     if node.get(ANDROID + "name") == "org.blender.blender.BlenderActivity"), None)
    if activity is None:
        raise ValueError("UPSTREAM_BLENDER_ACTIVITY_MISSING")
    # Upstream pins all users to sensorLandscape. Render instead exposes
    # full landscape AND a portrait-focused native workspace on a phone.
    # Java BlenderMobileControls supplies the owner's preferred orientation.
    activity.set(ANDROID + "screenOrientation", "unspecified")
    config_mask = native_configuration_mask(activity.get(ANDROID + "configChanges", ""))
    activity.set(ANDROID + "configChanges", "@integer/render_native_config_changes")
    if resources is not None:
        config_file = Path(resources) / "values/render_native_configuration.xml"
        if config_file.exists():
            raise ValueError("UPSTREAM_NATIVE_CONFIGURATION_RESOURCE_COLLISION")
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text('<resources><integer name="render_native_config_changes">'
                               + hex(config_mask) + '</integer></resources>\n', encoding="utf8")
    # One launcher opens Render's hub; native editor keeps .blend VIEW/EDIT intents.
    for intent in list(activity.findall("intent-filter")):
        if any(x.get(ANDROID + "name") == "android.intent.action.MAIN"
               for x in intent.findall("action")):
            activity.remove(intent)

    existing = {p.get(ANDROID + "name") for p in root.findall("uses-permission")}
    for permission in ("android.permission.FOREGROUND_SERVICE",
                       "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
                       "android.permission.FOREGROUND_SERVICE_MEDIA_PROCESSING",
                       "android.permission.FOREGROUND_SERVICE_DATA_SYNC",
                       "android.permission.POST_NOTIFICATIONS",
                       "android.permission.WAKE_LOCK"):
        if permission not in existing:
            ET.SubElement(root, "uses-permission", {ANDROID + "name": permission})
    application.set(ANDROID + "label", "Render Studio")
    application.set(ANDROID + "allowBackup", "false")
    application.set(ANDROID + "usesCleartextTraffic", "false")
    application.set(ANDROID + "enableOnBackInvokedCallback", "true")
    application.set(ANDROID + "resizeableActivity", "true")
    hub = ET.SubElement(application, "activity", {
        ANDROID + "name": "com.rezox.render.RenderHubActivity",
        ANDROID + "exported": "true",
        ANDROID + "screenOrientation": "unspecified",
    })
    filter_ = ET.SubElement(hub, "intent-filter")
    ET.SubElement(filter_, "action", {ANDROID + "name": "android.intent.action.MAIN"})
    ET.SubElement(filter_, "category", {ANDROID + "name": "android.intent.category.LAUNCHER"})
    for klass in ("com.rezox.render.MainActivity", "com.rezox.render.agent.AgentActivity",
                  "com.rezox.render.EditorLaunchActivity"):
        is_reference_inbox = klass.endswith("agent.AgentActivity")
        node = ET.SubElement(application, "activity", {
            ANDROID + "name": klass,
            ANDROID + "exported": "true" if is_reference_inbox else "false",
            ANDROID + "screenOrientation": "unspecified",
        })
        # Only explicit user SEND/Open Document grants arrive here; no Gallery
        # enumeration or broad READ_MEDIA permissions are requested.
        if is_reference_inbox:
            for action in ("android.intent.action.SEND",
                           "android.intent.action.SEND_MULTIPLE"):
                for mime in ("image/*", "video/*"):
                    intent = ET.SubElement(node, "intent-filter")
                    ET.SubElement(intent, "action", {ANDROID + "name": action})
                    ET.SubElement(intent, "category", {
                        ANDROID + "name": "android.intent.category.DEFAULT"})
                    ET.SubElement(intent, "data", {ANDROID + "mimeType": mime})
    service = ET.SubElement(application, "service", {
        ANDROID + "name": "com.rezox.render.agent.AgentService",
        ANDROID + "exported": "false",
        ANDROID + "foregroundServiceType": "specialUse",
    })
    ET.SubElement(service, "property", {
        ANDROID + "name": "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
        ANDROID + "value": "User-started and visible remote native project-command session with notification, Stop and Revoke",
    })
    long_render = ET.SubElement(application, "service", {
        ANDROID + "name": "com.rezox.render.agent.RenderLongForegroundService",
        ANDROID + "exported": "false",
        ANDROID + "foregroundServiceType": "mediaProcessing|specialUse",
    })
    ET.SubElement(long_render, "property", {
        ANDROID + "name": "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
        ANDROID + "value": "Explicit user-requested native Blender frame rendering with visible status, pause and crash-safe checkpoints",
    })
    ET.SubElement(application, "service", {
        ANDROID + "name": "com.rezox.render.agent.FileTransferService",
        ANDROID + "exported": "false",
        ANDROID + "foregroundServiceType": "dataSync",
    })
    ET.SubElement(application, "service", {
        ANDROID + "name": "com.rezox.render.agent.VideoStudioNativeBridgeService",
        ANDROID + "exported": "true",
    })
    ET.SubElement(application, "receiver", {
        ANDROID + "name": "com.rezox.render.agent.NativeWorkStopReceiver",
        ANDROID + "exported": "false",
    })
    return ET.ElementTree(root)


class _RuntimeScriptArchive(zipfile.ZipFile):
    """Keep runtime seals stable when a checkout changes only file metadata."""

    def write(self, filename, arcname=None, compress_type=None, compresslevel=None):
        if arcname is None:
            raise ValueError("RUNTIME_SCRIPT_ARCHIVE_NAME_REQUIRED")
        entry = zipfile.ZipInfo(arcname, date_time=(2020, 1, 1, 0, 0, 0))
        entry.create_system = 3
        entry.external_attr = 0o100644 << 16
        self.writestr(entry, Path(filename).read_bytes(),
                      compress_type=self.compression if compress_type is None else compress_type,
                      compresslevel=compresslevel)


def attach_bpy_agent(runtime_zip, source_py, scene_py=None, batch_py=None):
    """Startup timer executes typed bpy operations, never arbitrary Python code."""
    with zipfile.ZipFile(runtime_zip) as packed:
        names = packed.namelist()
        if not any(name.startswith("scripts/startup/") for name in names):
            raise ValueError("UPSTREAM_BLENDER_STARTUP_TREE_MISSING")
        if "scripts/startup/render_agent_startup.py" in names:
            raise ValueError("BLENDER_AGENT_SCRIPT_COLLISION")
        if scene_py is not None and "scripts/startup/render_lively_scene.py" in names:
            raise ValueError("BLENDER_LIVELY_SCRIPT_COLLISION")
        if batch_py is not None and "scripts/startup/render_batch_assembly.py" in names:
            raise ValueError("BLENDER_BATCH_SCRIPT_COLLISION")
    with _RuntimeScriptArchive(runtime_zip, "a") as packed:
        packed.write(source_py, "scripts/startup/render_agent_startup.py",
                     compress_type=zipfile.ZIP_DEFLATED)
        if scene_py is not None:
            packed.write(scene_py, "scripts/startup/render_lively_scene.py",
                         compress_type=zipfile.ZIP_DEFLATED)
        for name in ("render_file_contract.py", "render_file_ops.py", "render_artist_ops.py", "render_body_blockout.py", "render_character_tools.py", "render_asset_sources.py", "render_production.py", "render_production_contract.py", "render_production_detail.py", "render_studio_ops.py", "render_studio_contract.py", "render_reference_motion.py", "render_reference_motion_contract.py",
                     "render_unified_contract.py", "render_unified_queue.py", "render_unified_workspace.py", "render_unified_curves.py", "render_live_gestures.py",
                     "render_ik_contract.py", "render_ik_control.py",
                     "render_agent_fastlane_contract.py", "render_agent_fastlane.py",
                     "render_viewport_fidelity_contract.py", "render_viewport_fidelity.py",
                     "render_viewport_fidelity_ui.py",
                     "render_reference_timeline.py"):
            source = Path(source_py).with_name(name)
            if not source.is_file():
                raise ValueError("PRODUCTION_RUNTIME_NOT_PACKAGED")
            packed.write(source, "scripts/startup/" + name,
                         compress_type=zipfile.ZIP_DEFLATED)
        if batch_py is not None:
            packed.write(batch_py, "scripts/startup/render_batch_assembly.py",
                         compress_type=zipfile.ZIP_DEFLATED)
        # The runtime is immutable after stage; save/recovery helpers are
        # packaged alongside the upstream bpy startup script, not an APK shell.
        for extra in ("render_session_tools.py", "render_v25_recovery.py", "render_assets.py", "render_native_hud.py",
                      "render_asset_library.py", "render_execution_settings.py"):
            source = Path(source_py).with_name(extra)
            if not source.is_file():
                raise ValueError("SESSION_RUNTIME_NOT_PACKAGED")
            packed.write(source, "scripts/startup/" + extra,
                         compress_type=zipfile.ZIP_DEFLATED)
        # Keep the pinned full Blender runtime intact. Each independently
        # reviewed Omega module is an optional Python package member, not a
        # startup script or a replacement for libblender.so.
        scripts = Path(source_py).parent
        omega_dir = scripts / "omega"
        omega_files = [
            (scripts / "omega_registry.py", "scripts/startup/omega_registry.py"),
            (omega_dir / "__init__.py", "scripts/startup/omega/__init__.py"),
        ]
        allowed = {
            "phase01_engine.py", "phase02_render.py", "phase03_agent.py",
            "phase04_geometry.py", "phase05_character.py", "phase06_rig.py",
            "phase07_motion.py", "phase08_world.py", "phase09_vfx.py",
            "phase11_artist.py", "phase12_quality.py", "phase13_simulation.py",
        }
        if omega_dir.is_dir():
            for phase_file in sorted(omega_dir.glob("phase*.py")):
                if phase_file.name not in allowed:
                    raise ValueError("UNRECOGNIZED_OMEGA_MODULE")
                omega_files.append((phase_file, "scripts/startup/omega/" + phase_file.name))
        for source, archive_name in omega_files:
            if not source.is_file():
                raise ValueError("OMEGA_REGISTRY_RUNTIME_MISSING")
            if archive_name in names:
                raise ValueError("UPSTREAM_OMEGA_MODULE_COLLISION")
            packed.write(source, archive_name, compress_type=zipfile.ZIP_DEFLATED)

def patch_native_activity(path):
    java = path.read_text(encoding="utf-8")
    original = "  protected void onCreate(Bundle state) {"
    if java.count(original) != 1:
        raise ValueError("PINNED_BLENDER_ACTIVITY_HOOK_CHANGED")
    patch = original + """
    setRequestedOrientation(BlenderMobileControls.preferredOrientation(this));
    /* Native GHOST starts during super.onCreate. Publish the exact
       Android owner-selected mobile mode BEFORE libblender reads argv. */
    try {
      String mobileMode=getSharedPreferences("render_mobile_ui", MODE_PRIVATE)
          .getString("mode","portrait");
      Os.setenv("RENDER_MOBILE_UI_MODE", mobileMode, true);
    }
    catch (Exception ex) { Log.w(TAG,"mobile screen mode unavailable",ex); }
    /* Startup breadcrumb visible in Render Editor Diagnostics even if the GPU fails. */
    getSharedPreferences("render_editor_launch", MODE_PRIVATE).edit()
        .putString("stage", "Blender NativeActivity initialized; preparing native viewport")
        .putLong("updated", System.currentTimeMillis()).apply();
    /* Render's app-private command spool, read by Blender's bpy startup timer.
       No Android listening port, no remote render process. */
    try {
      com.rezox.render.NativeEditorConfiguration.publish(this);
      File commandDirectory = new File(getFilesDir(), "render_bpy_jobs");
      if (!commandDirectory.isDirectory() && !commandDirectory.mkdirs()) {
        throw new java.io.IOException("Cannot initialize Render command directory");
      }
      Os.setenv("RENDER_AGENT_SPOOL", commandDirectory.getAbsolutePath(), true);
    }
    catch (Exception exception) {
      Log.w(TAG, "Render native bpy bridge unavailable", exception);
    }
"""
    java = java.replace(original, patch)
    # App-private projects, runtime and SAF imports do not require all-files
    # access. Launching Settings after NativeActivity starts steals its window
    # during Vulkan initialization. Keep broad file access an explicit action.
    storage_request = "    requestAllFilesAccess();"
    if java.count(storage_request) != 1:
        raise ValueError("PINNED_BLENDER_STORAGE_REQUEST_HOOK_CHANGED")
    java = java.replace(storage_request, "    // File browser access is requested explicitly from Render controls.", 1)
    # Shared-storage probes on NativeActivity's main thread caused an actual
    # input-dispatch ANR. The loader prepares log/output storage off the UI
    # thread; the activity publishes only the already prepared private path.
    method = "  private void chooseLogPath() {"
    if java.count(method) != 1:
        raise ValueError("PINNED_BLENDER_LOG_PREPARATION_HOOK_CHANGED")
    start = java.index(method)
    end = start + len(method)
    depth = 1
    while end < len(java) and depth:
        depth += (java[end] == '{') - (java[end] == '}')
        end += 1
    if depth or "nativeSetLogPath(logPath);" not in java[start:end]:
        raise ValueError("PINNED_BLENDER_LOG_PREPARATION_BODY_CHANGED")
    java = java[:start] + '''  private void chooseLogPath() {
    logPath = com.rezox.render.omega.engine.EngineNativePaths.logPath(this);
    if (logPath != null) {
      nativeSetLogPath(logPath);
    }
  }''' + java[end:]
    log_hook = "      nativeSetLogPath(logPath);"
    if java.count(log_hook) != 1:
        raise ValueError("PINNED_BLENDER_LOG_PATH_HOOK_CHANGED")
    java = java.replace(log_hook, log_hook + '''
      getSharedPreferences("render_editor_launch", MODE_PRIVATE).edit()
          .putString("native_log_path", logPath).apply();''', 1)
    final_init = "    super.onCreate(state);"
    if final_init in java:
        java = java.replace(final_init, final_init + """
    getSharedPreferences("render_editor_launch", MODE_PRIVATE).edit()
        .putString("stage", "Blender NativeActivity created; awaiting Vulkan frames")
        .putLong("updated", System.currentTimeMillis()).apply();
""",1)
    # The stock NativeActivity hides all Android bars and places Blender's
    # toolbar under cutouts. Restore safe content insets and provide an
    # always-reachable in-editor Home/Focus/Scale/Rotate touch panel.
    old_launch = ("    setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);"
                  "\n    enterImmersive();")
    if old_launch not in java:
        raise ValueError("PINNED_NATIVE_BLENDER_LAUNCH_HOOK_CHANGED")
    java = java.replace(old_launch, "    BlenderMobileControls.attach(this);\n    com.rezox.render.agent.ProductionCapture.attach(this);\n    com.rezox.render.agent.StudioLiveHandOverlay.attach(this);", 1)
    old_immersive = """  private void enterImmersive() {
    View d = getWindow().getDecorView();
    d.setSystemUiVisibility(
        View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
        | View.SYSTEM_UI_FLAG_FULLSCREEN
        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
  }"""
    if old_immersive not in java:
        raise ValueError("PINNED_BLENDER_INSETS_HOOK_CHANGED")
    java = java.replace(old_immersive, """  private void enterImmersive() {
    BlenderMobileControls.applySafeInsets(this);
  }""", 1)
    if "android.window.OnBackInvokedCallback renderBackCallback;" not in java:
        cls = "public class BlenderActivity extends NativeActivity {"
        if java.count(cls)!=1: raise ValueError("PINNED_BLENDER_CLASS_DECLARATION_CHANGED")
        java=java.replace(cls,cls+"\n  android.window.OnBackInvokedCallback renderBackCallback;",1)
    if ("  public void onBackPressed(" in java or "  protected void onDestroy(" in java
            or " void onConfigurationChanged(" in java):
        raise ValueError("PINNED_BLENDER_NAVIGATION_HOOK_COLLISION")
    # The system back callback handles Android 13+/16 gestures. This fallback
    # handles old navigation-key devices. Neither exits without confirmation.
    addon = """
  @Override
  public void onBackPressed() {
    BlenderMobileControls.confirmHome(this);
  }

  @Override
  public void onConfigurationChanged(android.content.res.Configuration value) {
    super.onConfigurationChanged(value);
    com.rezox.render.NativeEditorConfiguration.configurationChanged(this);
  }

  @Override
  public boolean dispatchTouchEvent(android.view.MotionEvent event) {
    com.rezox.render.agent.StudioLiveHandOverlay.onRealTouch(event);
    return super.dispatchTouchEvent(event);
  }

  @Override
  protected void onDestroy() {
    com.rezox.render.agent.StudioLiveHandOverlay.detach(this);
    BlenderMobileControls.detach(this);
    super.onDestroy();
  }
"""
    if not java.rstrip().endswith("}"): raise ValueError("INVALID_UPSTREAM_JAVA_END")
    java = java.rstrip()[:-1] + addon + "}"
    path.write_text(java, encoding="utf-8")

def check_source(source, verify):
    path = Path(source)
    manifest = path / "build_files/android/apk/app/src/main/AndroidManifest.xml"
    java = path / "build_files/android/apk/app/src/main/java/org/blender/blender/BlenderActivity.java"
    res = path / "build_files/android/apk/app/src/main/res"
    if not manifest.is_file() or not java.is_file() or not res.is_dir():
        raise ValueError("UPSTREAM_ANDROID_SOURCE_INCOMPLETE")
    if verify:
        revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        if revision != UPSTREAM_COMMIT:
            raise ValueError("UPSTREAM_SOURCE_REVISION_MISMATCH")
    return manifest, java, res

def stage(engine, bridge, source, destination, expected_size=ENGINE_BYTES,
          expected_digest=ENGINE_SHA256, verify_source=True):
    verify_apk(engine, expected_size, expected_digest)
    manifest, java, res = check_source(source, verify_source)
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    libraries = destination / "lib/arm64-v8a"
    assets = destination / "assets"
    libraries.mkdir(parents=True)
    assets.mkdir(parents=True)
    seen = set()
    with zipfile.ZipFile(engine) as original:
        for info in original.infolist():
            name = valid_zip_entry(info)
            if name in seen:
                raise ValueError("DUPLICATED_ENGINE_APK_MEMBER")
            seen.add(name)
            if info.is_dir():
                continue
            if (name.startswith("lib/arm64-v8a/") and name.endswith(".so") and
                name.count("/") == 2) or name.startswith("assets/"):
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with original.open(info) as readable, target.open("wb") as output:
                    shutil.copyfileobj(readable, output, length=1024 * 1024)
    essentials = [
        libraries / "libblender.so",
        libraries / "libc++_shared.so",
        assets / "blender_runtime.zip",
    ]
    if not all(p.is_file() and p.stat().st_size > 0 for p in essentials):
        raise ValueError("FULL_BLENDER_NATIVE_RUNTIME_INCOMPLETE")
    with zipfile.ZipFile(bridge) as agent_apk:
        key = "lib/arm64-v8a/librender_bridge.so"
        if key not in agent_apk.namelist():
            raise ValueError("RENDER_NATIVE_AGENT_LIBRARY_MISSING")
        target = libraries / "librender_bridge.so"
        if target.exists():
            raise ValueError("UPSTREAM_AGENT_LIBRARY_COLLISION")
        with agent_apk.open(key) as readable, target.open("wb") as output:
            shutil.copyfileobj(readable, output, length=1024 * 1024)
    java_dst = destination / "java/org/blender/blender/BlenderActivity.java"
    java_dst.parent.mkdir(parents=True)
    shutil.copy2(java, java_dst)
    patch_native_activity(java_dst)
    shutil.copytree(res, destination / "res", dirs_exist_ok=True)
    startup = Path(__file__).resolve().parents[1] / "full-app/scripts/render_agent_startup.py"
    lively = Path(__file__).resolve().parents[1] / "full-app/scripts/render_lively_scene.py"
    assembly = Path(__file__).resolve().parents[1] / "full-app/scripts/render_batch_assembly.py"
    attach_bpy_agent(assets / "blender_runtime.zip", startup, lively, assembly)
    merged = merge_manifest(manifest, destination / "res")
    merged.write(destination / "AndroidManifest.xml", encoding="utf-8", xml_declaration=True)
    notices = assets / "licenses"
    notices.mkdir(exist_ok=True)
    if verify_source:
        from patch_pinned_timeline_dispatch import apply_pinned_fix
        apply_pinned_fix(libraries / "libblender.so", notices)
    (notices / "Render-Full-Native-Sources.txt").write_text(
        "Full Blender native engine source: https://github.com/simfeo/blender\n"
        "Pinned source revision: " + UPSTREAM_COMMIT + "\n"
        "APK release: https://github.com/simfeo/blender/releases/tag/android-alpha-4\n"
        "Engine APK SHA-256: " + ENGINE_SHA256 + "\n"
        "Blender source is GPL-2.0-or-later; consult matching source and bundled licenses.\n"
        "Render Android agent code and build adapters are in https://github.com/RezoxNemesis/Render\n"
        "Verified production staging applies the timeline-core dispatch fix; see "
        "Render-Native-Engine-Patches.json and blender-timeline-core.patch for exact hashes "
        "and corresponding source. Other engine features are retained.\n",
        encoding="utf-8")
    print("STAGED_FULL_NATIVE_BLENDER", len(list(libraries.glob("*.so"))),
          "libraries", (assets / "blender_runtime.zip").stat().st_size, "runtime bytes")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-apk", required=True)
    parser.add_argument("--bridge-apk", required=True)
    parser.add_argument("--upstream-source", required=True)
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    stage(a.engine_apk, a.bridge_apk, a.upstream_source, a.output)

if __name__ == "__main__":
    main()
