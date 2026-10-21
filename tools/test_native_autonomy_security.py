"""Release trust boundary and native work telemetry contract."""
import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class NativeAutonomySecurityTests(unittest.TestCase):
    def test_signing_secrets_absent_from_branch_debug_workflow(self):
        text=(ROOT/".github/workflows/full-native-apk.yml").read_text()
        self.assertNotIn("secrets.RENDER_ANDROID_SIGNING_",text)
        self.assertNotIn("assembleRelease",text)
        self.assertIn("assembleDebug",text)

    def test_release_signer_requires_manual_main_approval(self):
        text=(ROOT/".github/workflows/render-owner-release.yml").read_text()
        self.assertIn("workflow_dispatch:",text)
        self.assertIn("github.ref == 'refs/heads/main'",text)
        self.assertIn("name: render-production",text)
        self.assertIn("assembleRelease",text)
        self.assertIn("apksigner",text)
        self.assertIn("03:01:F0:84:CB:37:45:7B:E8:23:53:A8:A0:7E:88:14:35:17",text)
        self.assertNotIn("pull_request:",text)

    def test_setup_never_prints_private_keys_or_places_password_in_argv(self):
        script=(ROOT/"tools/configure_owner_signing.py").read_text()
        compile(script,"configure_owner_signing.py","exec")
        self.assertIn("getpass.getpass",script)
        self.assertIn('"-storepass:env"',script)
        self.assertIn('value=value)',script)
        self.assertNotIn("print(password)",script)
        self.assertIn("PROTECT_PRODUCTION_ENVIRONMENT",script)

    def test_real_native_status_not_browser_simulation(self):
        service=(ROOT/"app/src/main/java/com/rezox/render/agent/VideoStudioNativeBridgeService.java").read_text()
        android=(ROOT/"app/src/main/java/com/rezox/render/agent/AgentWorkPresence.java").read_text()
        spool=(ROOT/"app/src/main/java/com/rezox/render/agent/BlenderSpool.java").read_text()
        python=(ROOT/"full-app/scripts/render_lively_scene.py").read_text()
        self.assertIn("ArrayBlockingQueue<>(12)",service)
        self.assertIn("AgentWorkPresence.begin",service)
        self.assertIn("AgentWorkPresence.finish",service)
        self.assertIn("MAX_STALE_MS",android)
        self.assertIn("POST_NOTIFICATIONS",android)
        self.assertIn("progressFile",spool)
        self.assertIn("on_native_frame",python)
        self.assertIn("render_pre",python)

    def test_new_native_python_parses(self):
        for name in ("render_lively_scene.py","render_agent_startup.py"):
            p=ROOT/"full-app/scripts"/name
            ast.parse(p.read_text(),filename=str(p))

if __name__=="__main__":
    unittest.main()
