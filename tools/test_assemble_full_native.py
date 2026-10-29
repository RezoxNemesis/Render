"""Synthetic unit tests for full-engine APK staging; no internet or engine files."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from xml.etree import ElementTree as ET
import zipfile
from assemble_full_native import attach_bpy_agent, stage, verify_apk, native_configuration_mask

A = "{http://schemas.android.com/apk/res/android}"

class NativePackagingTests(unittest.TestCase):
    def test_asset_path_configuration_preserves_existing_flags_and_rejects_drift(self):
        self.assertEqual(0x800017f0,native_configuration_mask(
            'orientation|keyboardHidden|keyboard|screenSize|screenLayout|density|navigation|uiMode'))
        self.assertEqual(0xc0000080,native_configuration_mask('0x40000000|orientation'))
        with self.assertRaisesRegex(ValueError,'UNKNOWN_UPSTREAM_NATIVE_CONFIGURATION_FLAG'):
            native_configuration_mask('unknownFutureConfiguration')
    def setUp(self):
        self.working = tempfile.TemporaryDirectory()
        self.base = Path(self.working.name)
        self.source = self.base / "source"
        java = self.source / "build_files/android/apk/app/src/main/java/org/blender/blender"
        java.mkdir(parents=True)
        (java / "BlenderActivity.java").write_text("""package org.blender.blender;
import android.app.NativeActivity;
import android.content.pm.ActivityInfo;
import android.view.View;
public class BlenderActivity extends NativeActivity {
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
    enterImmersive();
    requestAllFilesAccess();
  }
  private void chooseLogPath() {
      nativeSetLogPath(logPath);
  }
  private void enterImmersive() {
    View d = getWindow().getDecorView();
    d.setSystemUiVisibility(
        View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
        | View.SYSTEM_UI_FLAG_FULLSCREEN
        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
  }
}
""")
        main = self.source / "build_files/android/apk/app/src/main"
        (main / "res/values").mkdir(parents=True)
        (main / "res/values/strings.xml").write_text("<resources/>")
        self.manifest = main / "AndroidManifest.xml"
        self.manifest.write_text(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.blender.blender">'
            '<application android:label="Blender">'
            '<activity android:name="org.blender.blender.BlenderActivity" android:exported="true">'
            '<intent-filter><action android:name="android.intent.action.MAIN"/>'
            '<category android:name="android.intent.category.LAUNCHER"/></intent-filter>'
            '<intent-filter><action android:name="android.intent.action.VIEW"/></intent-filter>'
            '</activity></application></manifest>'
        )
        self.engine = self.base / "engine.apk"
        self.bridge = self.base / "foundation.apk"
        self.output = self.base / "stage"
        self.make_engine()
        with zipfile.ZipFile(self.bridge, "w") as z:
            z.writestr("lib/arm64-v8a/librender_bridge.so", b"bridge")

    def tearDown(self):
        self.working.cleanup()

    def make_engine(self, additions=None):
        with zipfile.ZipFile(self.engine, "w") as z:
            z.writestr("lib/arm64-v8a/libblender.so", b"original actual native engine")
            z.writestr("lib/arm64-v8a/libc++_shared.so", b"native STL")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer,"w") as runtime:
                runtime.writestr("scripts/startup/bl_ui_test.py", b"# ordinary upstream script")
            z.writestr("assets/blender_runtime.zip", buffer.getvalue())
            for name, data in (additions or {}).items():
                z.writestr(name, data)
        self.digest = hashlib.sha256(self.engine.read_bytes()).hexdigest()
        self.size = self.engine.stat().st_size

    def build(self):
        stage(self.engine, self.bridge, self.source, self.output,
              expected_size=self.size, expected_digest=self.digest,
              verify_source=False)

    def test_combines_full_blender_agent_and_manifest(self):
        self.build()
        self.assertEqual(b"original actual native engine",
                         (self.output / "lib/arm64-v8a/libblender.so").read_bytes())
        self.assertEqual(b"bridge", (self.output / "lib/arm64-v8a/librender_bridge.so").read_bytes())
        runtime = self.output / "assets/blender_runtime.zip"
        self.assertTrue(runtime.exists())
        with zipfile.ZipFile(runtime) as z:
            self.assertIn("scripts/startup/render_agent_startup.py", z.namelist())
            self.assertIn("scripts/startup/render_native_hud.py", z.namelist())
        java = self.output / "java/org/blender/blender/BlenderActivity.java"
        self.assertTrue(java.exists())
        self.assertIn("RENDER_AGENT_SPOOL",java.read_text())
        self.assertIn("render_editor_launch",java.read_text())
        self.assertIn("BlenderMobileControls.attach(this)",java.read_text())
        self.assertIn("RENDER_MOBILE_UI_MODE",java.read_text())
        self.assertIn("BlenderMobileControls.confirmHome(this)",java.read_text())
        self.assertIn("BlenderMobileControls.applySafeInsets(this)",java.read_text())
        self.assertNotIn("    requestAllFilesAccess();",java.read_text())
        self.assertIn('.putString("native_log_path", logPath)',java.read_text())
        log_method = java.read_text().split('private void chooseLogPath()', 1)[1].split('\n  private void', 1)[0]
        self.assertIn('EngineNativePaths.logPath(this)', log_method)
        self.assertNotIn('FileOutputStream', log_method)
        self.assertNotIn('publishOutputDir(', log_method)
        self.assertTrue((self.output / "assets/licenses/Render-Full-Native-Sources.txt").exists())
        root = ET.parse(self.output / "AndroidManifest.xml").getroot()
        self.assertIsNone(root.find("queries"))
        self.assertNotIn("package", root.attrib)
        self.assertIn("android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
                      [p.get(A+"name") for p in root.findall("uses-permission")])
        app = root.find("application")
        self.assertEqual("Render Studio", app.get(A+"label"))
        self.assertEqual("true", app.get(A+"enableOnBackInvokedCallback"))
        self.assertEqual("true", app.get(A+"resizeableActivity"))
        activities = {p.get(A+"name"):p for p in app.findall("activity")}
        self.assertIn("com.rezox.render.RenderHubActivity", activities)
        self.assertIn("com.rezox.render.agent.AgentActivity", activities)
        self.assertIn("com.rezox.render.MainActivity", activities)
        self.assertIn("com.rezox.render.EditorLaunchActivity", activities)
        blender = activities["org.blender.blender.BlenderActivity"]
        self.assertEqual('@integer/render_native_config_changes',blender.get(A+'configChanges'))
        integer=ET.parse(self.output/'res/values/render_native_configuration.xml').getroot().find('integer')
        self.assertTrue(int(integer.text,0)&0x80000000)
        self.assertEqual(1, len(blender.findall("intent-filter")))
        self.assertEqual("unspecified",blender.get(A+"screenOrientation"))
        launch = activities["com.rezox.render.RenderHubActivity"]
        self.assertEqual("android.intent.action.MAIN",
                         launch.find("intent-filter/action").get(A+"name"))
        self.assertEqual("com.rezox.render.agent.AgentService",
                         app.find("service").get(A+"name"))
        services=[s.get(A+"name") for s in app.findall("service")]
        self.assertNotIn("com.rezox.render.agent.VideoStudioNativeBridgeService",services)
        self.assertFalse(root.findall("queries/package"))

    def test_refuses_tampered_engine(self):
        with self.assertRaisesRegex(ValueError,"SHA256_MISMATCH"):
            verify_apk(self.engine,self.size,"0"*64)
        with self.assertRaisesRegex(ValueError,"SIZE_MISMATCH"):
            verify_apk(self.engine,self.size+1,self.digest)

    def test_runtime_seal_ignores_checkout_metadata_but_tracks_script_changes(self):
        scripts = self.base / "scripts"
        shutil.copytree(Path(__file__).resolve().parents[1] / "full-app/scripts", scripts,
                        ignore=shutil.ignore_patterns("__pycache__"))
        with zipfile.ZipFile(self.engine) as engine:
            original_runtime = engine.read("assets/blender_runtime.zip")

        def package(name):
            runtime = self.base / name
            runtime.write_bytes(original_runtime)
            attach_bpy_agent(runtime, scripts / "render_agent_startup.py",
                             scripts / "render_lively_scene.py",
                             scripts / "render_batch_assembly.py")
            return runtime.read_bytes()

        first = package("first.zip")
        for source in scripts.rglob("*.py"):
            os.utime(source, (1609459200, 1609459200))
            source.chmod(0o600)
        self.assertEqual(first, package("different-checkout.zip"))
        with zipfile.ZipFile(io.BytesIO(first)) as runtime:
            self.assertEqual(b"# ordinary upstream script",
                             runtime.read("scripts/startup/bl_ui_test.py"))
            self.assertEqual((scripts / "render_native_hud.py").read_bytes(),
                             runtime.read("scripts/startup/render_native_hud.py"))
        startup = scripts / "render_agent_startup.py"
        startup.write_bytes(startup.read_bytes() + b"\n# changed runtime payload\n")
        self.assertNotEqual(first, package("changed-script.zip"))

    def test_refuses_path_traversal(self):
        self.make_engine({"assets/../../escape": b"bad"})
        with self.assertRaisesRegex(ValueError,"UNSAFE_ENGINE_APK_MEMBER"):
            self.build()

    def test_refuses_agent_library_collision(self):
        self.make_engine({"lib/arm64-v8a/librender_bridge.so": b"collision"})
        with self.assertRaisesRegex(ValueError,"UPSTREAM_AGENT_LIBRARY_COLLISION"):
            self.build()

    def test_refuses_missing_engine_runtime(self):
        with zipfile.ZipFile(self.engine,"w") as z:
            z.writestr("lib/arm64-v8a/libblender.so",b"blender")
        self.digest = hashlib.sha256(self.engine.read_bytes()).hexdigest()
        self.size = self.engine.stat().st_size
        with self.assertRaisesRegex(ValueError,"INCOMPLETE"):
            self.build()

if __name__ == "__main__":
    unittest.main()
