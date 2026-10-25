# SPDX-License-Identifier: GPL-2.0-or-later
"""App contract proof: user-visible quality gates never mutate/render implicitly."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_unified_contract as Native
import render_agent_fastlane_contract as Fast

class CharacterQualityContract(unittest.TestCase):
    def test_registered_but_read_only_not_implicitly_finished(self):
        self.assertIn("studio.character.qa.inspect",Native.PROGRAM_OPS)
        self.assertIn("studio.character.qa.upright",Native.PROGRAM_OPS)
        self.assertIn("studio.character.qa.inspect",Fast.READS)
        self.assertNotIn("studio.character.qa.upright",Fast.READS)
        self.assertNotIn("studio.character.qa.inspect",Native.MUTATING)
        self.assertIn("studio.character.qa.upright",Native.MUTATING)
        self.assertFalse(Native.catalog()["concurrent_scene_edits"])
        plan=Native.plan({"name":"Inspect actor before 3-second test",
                          "steps":[{"operation":"studio.character.qa.inspect",
                                    "payload":{"object":"IslandHero_BaseBody",
                                               "reference":"Island_RefSheet"}}]})
        self.assertEqual(len(plan["steps"]),1)

    def test_original_actor_and_reference_paths_are_supported(self):
        base=(ROOT/"full-app/scripts/render_body_blockout.py").read_text()
        assert "render_sculpt_union_pending" in base
        assert "render_likeness_verified" in base
        runtime=(ROOT/"tools/assemble_full_native.py").read_text()
        assert '"render_character_quality_gates.py"' in runtime
        root=(ROOT/"full-app/scripts/render_unified_workspace.py").read_text()
        assert "studio.character.qa." in root
        prod=(ROOT/"full-app/scripts/render_production.py").read_text()
        assert "studio.character.qa.upright" in prod
        java=(ROOT/"app/src/main/java/com/rezox/render/agent/ProductionBridge.java").read_text()
        assert '"studio.character.qa.inspect"' in java
        assert '"studio.character.qa.upright"' in java

if __name__=="__main__":unittest.main()
