# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure contracts for v0.25 protected still frames and independent recovery."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"full-app/scripts"

def contract():
    spec=importlib.util.spec_from_file_location("render_v25_contract_test",SOURCE/"render_production_contract.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class StillQualityContract(unittest.TestCase):
    def test_native_still_honors_requested_resolution_engine_and_samples(self):
        c=contract()
        native=c.render_spec({"output_kind":"STILL","width":3840,"height":2160,
                              "fps":24,"start":103,"end":103,
                              "samples":128,"engine":"CYCLES"})
        self.assertEqual(native["output_kind"],"STILL")
        self.assertEqual(native["width"],3840)
        self.assertEqual(native["height"],2160)
        self.assertEqual(native["samples"],128)
        self.assertEqual(native["engine"],"CYCLES")
        self.assertEqual(native["frame_count"],1)
        self.assertEqual(c.render_spec({})["output_kind"],"ANIMATION")
        for payload in ({"output_kind":"RAW_PYTHON"},
                        {"output_kind":"STILL","start":1,"end":2},
                        {"output_kind":"STILL","width":1921}):
            with self.assertRaises(ValueError):
                c.render_spec(payload)

    def test_previous_snapshot_requires_sha_receipt(self):
        from tools.test_render_v24_contract import FakeBlender
        with tempfile.TemporaryDirectory() as d:
            previous=os.environ.get("RENDER_AGENT_SPOOL")
            old_bpy=sys.modules.get("bpy")
            old_module=sys.modules.get("render_session_tools")
            try:
                os.environ["RENDER_AGENT_SPOOL"]=str(Path(d)/"render_bpy_jobs")
                fake=FakeBlender()
                fake.scene.frame_current=103
                sys.modules["bpy"]=fake
                spec=importlib.util.spec_from_file_location("render_session_tools",SOURCE/"render_session_tools.py")
                studio=importlib.util.module_from_spec(spec)
                sys.modules["render_session_tools"]=studio
                spec.loader.exec_module(studio)
                first=studio.save_session()
                second=studio.save_session()
                self.assertEqual(first["sha256"],second["sha256"])
                folder=Path(d)/"Production/Projects"
                self.assertTrue((folder/"CurrentSession.previous.json").is_file())
                (folder/"CurrentSession.blend").write_bytes(b"broken")
                self.assertEqual("CurrentSession.previous.blend",studio._recoverable_session().name)
                (folder/"CurrentSession.previous.blend").write_bytes(b"changed")
                self.assertIsNone(studio._recoverable_session())
                spec=studio._render_spec(fake.scene,"STILL")
                self.assertEqual((spec["start"],spec["end"]),(103,103))
                self.assertEqual((spec["width"],spec["height"]),(800,450))
                self.assertEqual(spec["samples"],48)
            finally:
                if previous is None:os.environ.pop("RENDER_AGENT_SPOOL",None)
                else:os.environ["RENDER_AGENT_SPOOL"]=previous
                if old_bpy is None:sys.modules.pop("bpy",None)
                else:sys.modules["bpy"]=old_bpy
                if old_module is None:sys.modules.pop("render_session_tools",None)
                else:sys.modules["render_session_tools"]=old_module

if __name__=="__main__":
    unittest.main()
