# SPDX-License-Identifier: GPL-2.0-or-later
"""Host tests: ChatGPT batching is read-only and queue cache never serves stale."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_agent_fastlane_contract as Fast
import render_unified_contract as C
import render_unified_queue as Q

class AgentFastlaneContracts(unittest.TestCase):
    def test_batched_reads_are_only_allowlisted_native_inspection(self):
        reads=[{"operation":"studio.sculpt.inspect","payload":{"object":"Head"}},
               {"operation":"studio.plan.list","payload":{}}]
        self.assertEqual(Fast.batch({"reads":reads}),reads)
        for attack in (
            {"reads":[{"operation":"studio.sculpt.brush","payload":{}}]},
            {"reads":[{"operation":"studio.plan.submit","payload":{}}]},
            {"reads":[{"operation":"studio.curve.adjust","payload":{}}]},
            {"reads":[{"operation":"studio.agent.batch.inspect","payload":{}}]},
            {"reads":[{"operation":"operator.execute","payload":{}}]},
            {"reads":[{"operation":"studio.plan.list","payload":{},"python":"bad"}]},
            {"reads":[{"operation":"studio.plan.list","payload":{"x":float("nan")}}]},
            {"reads":[]},
            {"reads":reads*4},
            {"reads":"scene.inspect"},
        ):
            with self.subTest(attack=str(attack)[:60]):
                with self.assertRaises(ValueError):Fast.batch(attack)
        assert len(Fast.READS)>=10

    def test_bootstrap_etag_and_optional_fields_are_bounded(self):
        self.assertEqual(Fast.bootstrap({"query":"natural animation",
                                        "include_queue":True})["query"],"natural animation")
        for bad in ({"query":"a"*81},{"limit":0},{"limit":100},
                    {"known_manifest_sha256":"private_token"},
                    {"include_queue":"yes"},{"include_scene":1},
                    {"python":"script"},{"query":float("nan")}):
            with self.assertRaises(ValueError):Fast.bootstrap(bad)

    def test_rank_helps_natural_language_without_remote_embeddings(self):
        self.assertGreater(Fast.rank("animate a character limb using IK",
                    "studio.ik.target","animation",["NLA","Keyframes"]),0)
        self.assertGreater(Fast.rank("zoom viewport",
                    "studio.view.orbit","sculpt",["Sculpt Mode"]),0)
        self.assertGreater(Fast.rank("faster chatgpt status",
                    "studio.agent.bootstrap","agent",["Agent","Status"]),0)
        self.assertEqual(Fast.rank("utterly_unrelated_secret_phrase",
                    "studio.ik.target","animation",[]),0)

    def test_plan_preflight_does_not_claim_payload_simulation_or_rollback(self):
        p={"name":"Actor motion","steps":[
            {"operation":"studio.pose.inspect","payload":{"rig":"ActorRig"}},
            {"operation":"studio.ik.blend","payload":{"rig":"ActorRig","bone":"Shin",
                                                      "influence":1,"frame":20,
                                                      "expected_sha256":"a"*64}}]}
        result=Fast.preview(p,C.PROGRAM_OPS,C.MUTATING)
        self.assertEqual(result["mutating_steps"],1)
        self.assertEqual(result["read_only_steps"],1)
        self.assertFalse(result["simulation_executed"])
        self.assertFalse(result["per_operation_payload_preflight_complete"])
        self.assertFalse(result["automatic_rollback_guaranteed"])
        with self.assertRaises(ValueError):
            Fast.preview({"name":"Fake","steps":[{
               "operation":"shell.exec","payload":{"cmd":"rm"}}]},C.PROGRAM_OPS,C.MUTATING)

    def test_cache_cold_hot_and_external_rewrite_invalidate(self):
        with tempfile.TemporaryDirectory() as d:
            name="a"*32
            item={"plan_id":name,"name":"Fast plan","steps":[
                {"operation":"studio.pose.inspect","payload":{"rig":"Rig"}}]}
            Q.submit(d,item)
            hot=Q.cache_stats()["hits"]
            got=Q.get(d,name)
            again=Q.get(d,name)
            self.assertEqual(again,got)
            self.assertGreater(Q.cache_stats()["hits"],hot)
            # Exposing status to callers must not mutate a cached receipt.
            rows=Q._all(d)
            rows[0][0]["name"]="bad external caller"
            self.assertEqual(Q.get(d,name)["name"],"Fast plan")
            path=Path(d)/"StudioPlans"/(name+".json")
            data=json.loads(path.read_text())
            data["fingerprint"]="b"*64
            stage=path.with_suffix(".tmp")
            stage.write_text(json.dumps(data))
            os.replace(stage,path)
            with self.assertRaises(ValueError):
                Q.get(d,name)
            # A valid user-visible state change is observed without stale
            # data after atomic cross-process substitution.
            data["fingerprint"]=C.plan({"name":data["name"],"steps":data["steps"]})["fingerprint"]
            stage.write_text(json.dumps(data));os.replace(stage,path)
            self.assertEqual(Q.get(d,name)["name"],"Fast plan")
            self.assertLessEqual(Q.cache_stats()["bytes"],2*1024*1024)

    def test_older_recovery_tests_still_required(self):
        with tempfile.TemporaryDirectory() as d:
            p={"plan_id":"f"*32,"name":"Recover me",
               "steps":[{"operation":"scene.inspect","payload":{}}]}
            Q.submit(d,p)
            result=Q.tick(d,lambda *_: (_ for _ in ()).throw(RuntimeError("oops")))
            self.assertEqual(result["result"],"needs_review")
            self.assertFalse(Q.recover(d)["automatic_replay"])
            self.assertEqual(Q.tick(d,lambda *args:{"ok":True})["executed_steps"],0)

if __name__=="__main__":unittest.main()
