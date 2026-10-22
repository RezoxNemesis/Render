"""Real bpy fixture, only a Blender binary is native test evidence."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

try:
    import bpy
except ImportError:
    bpy = None

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "full-app" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import omega_registry as registry


@unittest.skipIf(bpy is None, "Requires actual Blender bpy")
class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        os.environ["RENDER_AGENT_SPOOL"] = str(Path(self.temp.name) / "spool")
        mesh = bpy.data.meshes.new("OMEGA_Phase10_Mesh")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        mesh.update()
        self.obj = bpy.data.objects.new("OMEGA_Phase10_Triangle", mesh)
        bpy.context.scene.collection.objects.link(self.obj)

    def tearDown(self):
        bpy.data.objects.remove(self.obj, do_unlink=True)
        self.temp.cleanup()

    def test_native_spool_dispatch_and_audit_do_not_modify_render_quality(self):
        import render_agent_startup as startup
        scene = bpy.context.scene
        before = (scene.render.engine, scene.render.resolution_x,
                  scene.render.resolution_y, scene.render.fps_base)
        command = {"id": "b" * 32, "action": "omega.dispatch",
                   "args": {"operation": "omega.integration.audit",
                            "payload": {}, "available_memory_bytes": 0}}
        result = startup._dispatch(command)
        self.assertEqual(scene.name, result["scene"])
        self.assertGreaterEqual(result["objects"], 1)
        self.assertTrue(result["native_execution_verified"])
        self.assertFalse(result["visual_quality_verified"])
        self.assertFalse(result["quality_reduced"])
        self.assertEqual(before, (scene.render.engine, scene.render.resolution_x,
                                  scene.render.resolution_y, scene.render.fps_base))
        command["args"]["operation"] = "omega.geometry.bridge_loops"
        with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
            startup._dispatch(command)


if __name__ == "__main__":
    unittest.main(argv=[__file__], verbosity=2)
