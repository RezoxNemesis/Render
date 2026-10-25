# SPDX-License-Identifier: GPL-2.0-or-later
"""Pure host tests of owner-controlled Blender UI contracts and durable plans."""
import json
from pathlib import Path
import tempfile
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_unified_contract as C
import render_unified_queue as Q

class UnifiedStudioTest(unittest.TestCase):
    def sample(self,pid=None):
        data={"name":"Sculpt then animate","steps":[
            {"operation":"mesh.create","payload":{"name":"Head","kind":"UV_SPHERE"}},
            {"operation":"animation.keys","payload":{"object":"Head","keys":[
                {"frame":1,"path":"location","value":[0,0,0]},
                {"frame":10,"path":"location","value":[1,0,0]}]}}]}
        if pid:data["plan_id"]=pid
        return data

    def test_catalog_exposes_nine_honest_native_disciplines(self):
        catalog=C.catalog(active="animation")
        self.assertEqual(len(catalog["workspaces"]),9)
        self.assertIn("sculpt",[x["id"] for x in catalog["workspaces"]])
        self.assertIn("simulation",[x["id"] for x in catalog["workspaces"]])
        self.assertFalse(catalog["concurrent_scene_edits"])
        self.assertFalse(catalog["continuous_execution_after_force_stop_guaranteed"])
        for record in catalog["workspaces"]:
            self.assertFalse(record["feature_parity_claimed"])
            self.assertFalse(record["vendor_software_installed"])

    def test_plan_is_bounded_typed_and_rejects_code_injection(self):
        good=C.plan(self.sample())
        self.assertEqual(len(good["fingerprint"]),64)
        for attack in [
            {"name":"unsafe/../path","steps":self.sample()["steps"]},
            {"name":"valid","steps":[{"operation":"bpy.execute_python","payload":{}}]},
            {"steps":[{"operation":"mesh.create","payload":{},"python":"evil"}]},
            {"steps":[]},
            {"steps":self.sample()["steps"]*9},
            {"steps":[{"operation":"animation.keys","payload":{"float":float("nan")}}]},
            {"steps":self.sample()["steps"],"arbitrary":"command"}
        ]:
            with self.subTest(attack=str(attack)[:65]):
                with self.assertRaises(ValueError):C.plan(attack)

    def test_one_step_per_tick_and_idempotent_retrieval(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.sample("a"*32)
            start=Q.submit(d,p)
            self.assertFalse(start["idempotent"])
            self.assertTrue(Q.submit(d,p)["idempotent"])
            self.assertEqual(start["total_steps"],2)
            with self.assertRaises(ValueError):
                Q.submit(d,dict(p,steps=[p["steps"][0]]))
            operations=[]
            def runner(op,args,plan_id):
                operations.append(op)
                return {"object":"Head","step":len(operations)}
            self.assertEqual(Q.tick(d,runner)["result"],"succeeded")
            self.assertEqual(Q.get(d,p["plan_id"])["completed_steps"],1)
            self.assertEqual(Q.tick(d,runner)["result"],"succeeded")
            self.assertEqual(Q.get(d,p["plan_id"])["state"],"completed")
            self.assertEqual(operations,["mesh.create","animation.keys"])
            self.assertEqual(Q.tick(d,runner)["executed_steps"],0)
            self.assertNotIn("payload",str(Q.list_jobs(d)))

    def test_independent_plans_fair_and_pause_resume(self):
        with tempfile.TemporaryDirectory() as d:
            a=Q.submit(d,self.sample("a"*32))
            b=Q.submit(d,self.sample("b"*32))
            Q.pause(d,a["plan_id"])
            trace=[]
            Q.tick(d,lambda op,arg,pid:(trace.append(pid),{"ok":True})[1])
            self.assertEqual(trace,["b"*32])
            Q.resume(d,a["plan_id"])
            self.assertEqual(Q.get(d,a["plan_id"])["state"],"queued")
            self.assertEqual(Q.tick(d,lambda op,arg,pid:{"ok":True},render_busy=True)["executed_steps"],0)
            self.assertEqual(Q.get(d,a["plan_id"])["completed_steps"],0)
            self.assertTrue(Q.cancel(d,a["plan_id"])["state"]=="cancelled")

    def test_mutating_exception_does_not_replay_on_restart(self):
        with tempfile.TemporaryDirectory() as d:
            ref=Q.submit(d,self.sample("c"*32))
            seen=[]
            def crashes(op,arg,id):
                seen.append(op)
                raise RuntimeError("native step failed after potential mutation")
            result=Q.tick(d,crashes)
            self.assertEqual(result["result"],"needs_review")
            self.assertEqual(len(seen),1)
            self.assertEqual(Q.tick(d,crashes)["executed_steps"],0)
            with self.assertRaises(ValueError):Q.resume(d,ref["plan_id"])
            self.assertTrue(Q.get(d,ref["plan_id"])["requires_manual_review"])
            # The on-disk running receipt is what remains after a hard kill.
            path=Path(d)/"StudioPlans"/(ref["plan_id"]+".json")
            payload=json.loads(path.read_text())
            payload["state"]="running"
            path.write_text(json.dumps(payload))
            self.assertEqual(Q.recover(d)["interrupted_steps_marked_needs_review"],1)
            self.assertEqual(Q.get(d,ref["plan_id"])["completed_steps"],0)
            Q.cancel(d,ref["plan_id"])
            self.assertEqual(Q.get(d,ref["plan_id"])["state"],"cancelled")

    def test_queue_cannot_drown_phone_with_unbounded_plans(self):
        with tempfile.TemporaryDirectory() as d:
            for n in "1234":Q.submit(d,self.sample(n*32))
            with self.assertRaises(ValueError):Q.submit(d,self.sample("5"*32))
            Q.cancel(d,"1"*32)
            Q.submit(d,self.sample("5"*32))
            with self.assertRaises(ValueError):Q.get(d,"../../secrets")

    def test_sculpt_plan_receipt_retains_only_verified_mesh_revision(self):
        with tempfile.TemporaryDirectory() as d:
            first={"operation":"studio.sculpt.brush",
                   "payload":{"object":"Face","expected_sha256":"a"*64}}
            second={"operation":"studio.sculpt.brush",
                    "payload":{"object":"Face","expected_sha256":"$prev_mesh_sha256"}}
            accepted=Q.submit(d,{"plan_id":"6"*32,"name":"Staged sculpture",
                                 "steps":[first,second]})
            assert accepted["state"]=="queued"
            once=Q.tick(d,lambda op,payload,pid:{
                "object":"Face","mesh_revision_after":"b"*64,
                "native_blender_vertex_coordinates_updated":True})
            self.assertEqual(once["result"],"succeeded")
            stored=Q._load_file(Q._path(d,"6"*32))
            self.assertEqual(stored["receipts"][0]["mesh_revision_after"],"b"*64)
            self.assertEqual(stored["steps"][1]["payload"]["expected_sha256"],
                             "$prev_mesh_sha256")
            self.assertNotIn("mesh_revision_after",str(Q.list_jobs(d)))
            # A synthetic executor is not allowed to mark an unsuccessful step
            # complete merely because it produces JSON.
            stopped=Q.tick(d,lambda op,payload,pid:{"paused":True})
            self.assertEqual(stopped["result"],"needs_review")
            self.assertTrue(Q.get(d,"6"*32)["requires_manual_review"])

    def test_tampered_checkpoint_is_never_executed(self):
        with tempfile.TemporaryDirectory() as d:
            ref=Q.submit(d,self.sample("e"*32))
            path=Path(d)/"StudioPlans"/(ref["plan_id"]+".json")
            payload=json.loads(path.read_text())
            payload["steps"][0]["payload"]["name"]="ModifiedWithoutNewPlan"
            path.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):Q.get(d,ref["plan_id"])
            with self.assertRaises(ValueError):Q.tick(d,lambda *args:{"ok":True})

if __name__=="__main__":unittest.main()
