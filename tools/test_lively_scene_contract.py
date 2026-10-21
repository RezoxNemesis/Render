# SPDX-License-Identifier: GPL-2.0-or-later
"""No Blender executable required: verify safe packaged Android scene contract."""
import ast
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "full-app/scripts/render_lively_scene.py"
STARTUP = ROOT / "full-app/scripts/render_agent_startup.py"
POLICY = ROOT / "app/src/main/java/com/rezox/render/agent/AgentPolicy.java"
AGENT = ROOT / "app/src/main/java/com/rezox/render/agent/AgentActions.java"
SPOOL = ROOT / "app/src/main/java/com/rezox/render/agent/BlenderSpool.java"
ASSEMBLER = ROOT / "tools/assemble_full_native.py"


class NativeLivelySceneContractTests(unittest.TestCase):
    def test_python_modules_parse_without_running_blender(self):
        for source in (HELPER, STARTUP, ASSEMBLER):
            compile(source.read_text(encoding="utf-8"), str(source), "exec")

    def test_no_arbitrary_user_scripts_or_file_paths(self):
        tree = ast.parse(HELPER.read_text(encoding="utf-8"))
        forbidden = {"eval", "exec", "compile", "system", "popen", "subprocess"}
        imported = {alias.name.split(".")[0] for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in (node.names if isinstance(node, ast.Import) else
                                  [ast.alias(name=node.module or "")])}
        self.assertTrue(forbidden.isdisjoint(imported))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, forbidden)

    def test_opaque_restore_only_uses_our_snapshot_names(self):
        source = HELPER.read_text(encoding="utf-8")
        self.assertIn('filename = args["filename"]', source)
        self.assertIn('file.resolve().parent != projects.resolve()', source)
        self.assertIn('file.is_symlink()', source)
        self.assertRegex("Render_" + "a"*32 + ".blend",
                         re.compile(r"Render_[a-f0-9]{32}\.blend\Z"))
        for unsafe in ("../../secret.blend", "/storage/emulated/0/something.blend",
                       "not-render.blend", "Render_"+"x"*32+".blend"):
            self.assertNotRegex(unsafe, r"Render_[a-f0-9]{32}\.blend\Z")

    def test_registry_matches_dispatcher_and_checks_owned_files(self):
        policy = POLICY.read_text(encoding="utf-8")
        agent = AGENT.read_text(encoding="utf-8")
        spool = SPOOL.read_text(encoding="utf-8")
        startup = STARTUP.read_text(encoding="utf-8")
        for action in ("blender.project.restore_scene", "blender.scene.populate_lively",
                       "blender.scene.render_video"):
            for body in (policy, spool, startup):
                self.assertIn(action, body)
        self.assertIn('projects.find(args.getString("project_id"))', agent)
        self.assertIn('new File(context.getFilesDir(),"Projects")', agent)
        self.assertIn("PROJECT_REVISION_CONFLICT", agent)
        self.assertIn('args.length()!=0', spool)
        self.assertNotIn('ProcessBuilder(', HELPER.read_text(encoding="utf-8"))

    def test_apk_runtime_archive_includes_scene_helper(self):
        spec = importlib.util.spec_from_file_location("assemble_full_native_test", ASSEMBLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as work:
            archive = Path(work) / "blender_runtime.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("scripts/startup/upstream_example.py", "# upstream")
            module.attach_bpy_agent(archive, STARTUP, HELPER)
            with zipfile.ZipFile(archive) as z:
                self.assertIn("scripts/startup/render_agent_startup.py", z.namelist())
                self.assertIn("scripts/startup/render_lively_scene.py", z.namelist())
                self.assertEqual(z.read("scripts/startup/render_lively_scene.py"),
                                 HELPER.read_bytes())


if __name__ == "__main__":
    unittest.main()
