"""Fail-closed path ownership gate for all 13 frozen RENDER OMEGA branches."""
import argparse
import fnmatch
import re
import subprocess
import unittest

SEED = "ed7ef34fa85d9e361bc9c92d554d8ec937755cc2"
RULES = {
 1: "full-app/app/src/main/java/com/rezox/render/EditorLaunchActivity.java full-app/app/src/main/java/org/blender/blender/BlenderMobileControls.java app/src/main/java/com/rezox/render/omega/engine/** full-app/scripts/omega/phase01_engine.py app/src/test/java/com/rezox/render/omega/engine/** tools/omega/test_phase01_*.py",
 2: "app/src/main/java/com/rezox/render/agent/ProductionBatch.java app/src/main/java/com/rezox/render/agent/RenderManualJobs.java app/src/main/java/com/rezox/render/agent/RenderRecoveryStatus.java app/src/main/java/com/rezox/render/agent/ProductionVideoEncoder.java full-app/scripts/render_production.py full-app/scripts/render_session_tools.py full-app/scripts/render_v25_recovery.py full-app/scripts/omega/phase02_render.py app/src/test/java/com/rezox/render/omega/render/** tools/omega/test_phase02_*.py",
 3: "app/src/main/java/com/rezox/render/agent/AgentJournal.java app/src/main/java/com/rezox/render/agent/AgentWorkPresence.java app/src/main/java/com/rezox/render/agent/StudioLiveHandOverlay.java app/src/main/java/com/rezox/render/omega/agent/** full-app/scripts/omega/phase03_agent.py app/src/test/java/com/rezox/render/omega/agent/** tools/omega/test_phase03_*.py",
 4: "full-app/scripts/omega/phase04_geometry.py tools/omega/test_phase04_*.py native-tests/omega/phase04/**",
 5: "full-app/scripts/omega/phase05_character.py tools/omega/test_phase05_*.py native-tests/omega/phase05/**",
 6: "full-app/scripts/omega/phase06_rig.py tools/omega/test_phase06_*.py native-tests/omega/phase06/**",
 7: "full-app/scripts/omega/phase07_motion.py tools/omega/test_phase07_*.py native-tests/omega/phase07/**",
 8: "full-app/scripts/render_assets.py full-app/scripts/omega/phase08_world.py tools/omega/test_phase08_*.py native-tests/omega/phase08/**",
 9: "full-app/scripts/omega/phase09_vfx.py tools/omega/test_phase09_*.py native-tests/omega/phase09/**",
 10: "full-app/scripts/render_agent_startup.py full-app/scripts/omega/__init__.py full-app/scripts/omega_registry.py app/src/main/java/com/rezox/render/agent/ProductionBridge.java app/src/main/java/com/rezox/render/agent/AgentActions.java app/src/main/java/com/rezox/render/agent/AgentPolicy.java app/src/main/java/com/rezox/render/agent/BlenderSpool.java app/src/main/java/com/rezox/render/omega/integration/** tools/assemble_full_native.py tools/prepare_production_toolkit.py tools/prepare_v23_reference.py app/build.gradle.kts full-app/app/build.gradle app/src/main/AndroidManifest.xml full-app/app/src/main/AndroidManifest.xml tools/configure_owner_signing.py .github/workflows/** tools/omega/test_phase10_*.py docs/omega/phase10-interface-test-data/**",
 11: "full-app/scripts/omega/phase11_artist.py app/src/main/java/com/rezox/render/omega/artist/** app/src/test/java/com/rezox/render/omega/artist/** tools/omega/test_phase11_*.py native-tests/omega/phase11/**",
 12: "full-app/scripts/omega/phase12_quality.py app/src/main/java/com/rezox/render/omega/quality/** app/src/test/java/com/rezox/render/omega/quality/** tools/omega/test_phase12_*.py native-tests/omega/phase12/**",
 13: "full-app/scripts/omega/phase13_simulation.py app/src/main/java/com/rezox/render/omega/simulation/** app/src/test/java/com/rezox/render/omega/simulation/** tools/omega/test_phase13_*.py native-tests/omega/phase13/**",
}


def violations(phase, paths):
    if phase not in RULES:
        raise ValueError("INVALID_PHASE")
    allowed = RULES[phase].split() + [f"reports/omega/PHASE_{phase:02}_RESULT.json"]
    return [path for path in paths
            if not any(fnmatch.fnmatchcase(path, pattern) for pattern in allowed)]


class OwnershipTests(unittest.TestCase):
    def test_blueprint_may_not_be_edited_by_any_phase(self):
        for phase in RULES:
            self.assertEqual(["docs/omega/RENDER_OMEGA_TEN_PHASE_MASTER_BLUEPRINT.md"],
                             violations(phase, ["docs/omega/RENDER_OMEGA_TEN_PHASE_MASTER_BLUEPRINT.md"]))

    def test_cross_phase_shared_and_report_fail(self):
        self.assertEqual(["full-app/scripts/omega/phase11_artist.py"],
                         violations(10, ["full-app/scripts/omega/phase11_artist.py"]))
        self.assertEqual(["full-app/scripts/render_agent_startup.py"],
                         violations(11, ["full-app/scripts/render_agent_startup.py"]))
        self.assertEqual(["reports/omega/PHASE_09_RESULT.json"],
                         violations(10, ["reports/omega/PHASE_09_RESULT.json"]))

    def test_phase10_owned_entrypoints_pass(self):
        self.assertEqual([], violations(10, ["full-app/scripts/omega_registry.py",
             "tools/assemble_full_native.py", ".github/workflows/omega-phase10.yml"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    if not all(re.fullmatch("[a-f0-9]{40}", s) for s in (args.base, args.head)):
        parser.error("full commit IDs are required")
    subprocess.run(["git", "merge-base", "--is-ancestor", SEED, args.head], check=True)
    shared = subprocess.check_output(["git", "merge-base", args.base, args.head], text=True).strip()
    paths = [s.decode() for s in subprocess.check_output(
        ["git", "diff", "--name-only", "-z", shared, args.head]).split(b"\0") if s]
    bad = violations(args.phase, paths)
    print("OMEGA_OWNERSHIP", args.phase, len(paths), "changed paths; violations:", bad)
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    import sys
    if "--phase" in sys.argv:
        main()
    else:
        unittest.main()
