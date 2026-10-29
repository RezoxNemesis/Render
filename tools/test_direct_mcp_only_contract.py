# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail-closed source contract for the Android app's dedicated Render Studio MCP."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "app/src/main/java/com/rezox/render/agent"

class DirectRenderMcpContract(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_no_videostudio_carrier_sources_or_exported_binder(self):
        self.assertFalse((AGENT / "VideoStudioNativeBridgeService.java").exists())
        self.assertFalse((AGENT / "VideoStudioMcpTransport.java").exists())
        manifest = self.read("app/src/main/AndroidManifest.xml")
        self.assertNotIn("VideoStudioNativeBridgeService", manifest)
        self.assertNotIn("com.rezoxnemesis.videostudio", manifest)
        self.assertNotIn("<queries>", manifest)

    def test_agent_only_polls_dedicated_render_worker(self):
        direct = self.read("app/src/main/java/com/rezox/render/agent/RenderDirectMcp.java")
        service = self.read("app/src/main/java/com/rezox/render/agent/AgentService.java")
        self.assertIn("render-studio-direct-mcp.prakasharuntandon634.workers.dev", direct)
        self.assertIn('private static final String LEGACY_TRANSPORT="videostudio-mcp-v3"', direct)
        self.assertIn("RenderDirectMcp.requireDirectPairing(credentials)", service)
        self.assertIn("AgentHttp.post(RenderDirectMcp.ORIGIN,path,", service)
        self.assertNotIn("VideoStudioMcpTransport", service)
        self.assertNotIn("VideoStudioNativeBridgeService", service)

    def test_pairing_is_primary_and_old_credentials_cannot_be_replayed(self):
        activity = self.read("app/src/main/java/com/rezox/render/agent/AgentActivity.java")
        self.assertIn("RenderDirectMcp.credentials(", activity)
        self.assertIn("RenderDirectMcp.isLegacyPairing(previous)", activity)
        self.assertIn("RenderDirectMcp.requireDirectPairing(secrets.load())", activity)
        self.assertIn("RenderDirectMcp.MCP_ENDPOINT", activity)
        self.assertNotIn("PAIR VIA VIDEOSTUDIO", activity)
        self.assertNotIn("CHECK VIDEOSTUDIO APP", activity)
        self.assertNotIn("VideoStudioMcpTransport", activity)
        self.assertNotIn("VideoStudioNativeBridgeService", activity)
        self.assertIn("native files remain", self.read("app/src/main/java/com/rezox/render/agent/RenderDirectMcp.java").replace("Blender and files remain", "native files remain"))

    def test_monotonic_signed_apk_identity(self):
        gradle = self.read("full-app/app/build.gradle")
        bridge = self.read("app/build.gradle.kts")
        self.assertIn("versionCode 62", gradle)
        self.assertIn("versionCode = 62", bridge)
        self.assertIn("versionName '0.61.0-direct-mcp'", gradle)
        self.assertIn('versionName = "0.61.0-direct-mcp"', bridge)
        verify = self.read("tools/verify_creator_apk.py")
        self.assertIn('VERSION_CODE = "62"', verify)
        self.assertIn("LEGACY_VIDEOSTUDIO_BRIDGE_STILL_EXPORTED", verify)

if __name__ == "__main__":
    unittest.main()
