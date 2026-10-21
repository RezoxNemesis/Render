"""Same real relay actions against a temporary isolated PostgreSQL schema.

CI supplies local Postgres 16; no owner credentials or cloud dependencies.
"""
import base64
import hashlib
import os
import unittest
import uuid
from urllib.parse import quote

from core import Relay, Denied

DSN = os.environ.get("TEST_POSTGRES_DSN")
BASE = "https://render-pg-test.example"
SECRET = "unit-test-only-postgres-enrollment-not-a-real-secret"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
CAPS = [{"id": "engine.status", "available": True, "api_version": 1,
         "input_schema": {"type": "object", "additionalProperties": False,
                          "properties": {}}}]


@unittest.skipUnless(DSN, "PostgreSQL integration DSN not supplied")
class PersistentRelayTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        self.schema = "relay_" + uuid.uuid4().hex
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute('CREATE SCHEMA "' + self.schema + '"')
        options = quote("-csearch_path=" + self.schema, safe="")
        self.url = DSN + ("&" if "?" in DSN else "?") + "options=" + options
        self.now = [100000]
        self.relay = Relay(self.url, BASE, SECRET, clock=lambda: self.now[0])
        self.phone = self.relay.enroll(SECRET, "Physical-device test fixture")
        self.client = self.relay.register([REDIRECT])["client_id"]
        verifier = "V" * 64
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        authorization = self.relay.authorize(
            self.client, REDIRECT, challenge, self.phone["link_code"], BASE + "/mcp", "render")
        tokens = self.relay.exchange(
            self.client, authorization, verifier, REDIRECT, BASE + "/mcp")
        self.access = tokens["access_token"]
        self.token = self.phone["device_token"]
        self.relay.poll(self.token, True, CAPS, None)

    def tearDown(self):
        import psycopg
        with psycopg.connect(DSN, autocommit=True) as conn:
            conn.execute('DROP SCHEMA IF EXISTS "' + self.schema + '" CASCADE')

    def test_state_survives_process_reconstruction(self):
        job = self.relay.submit(self.access, "pg-1", "engine.status", {})
        running = self.relay.poll(self.token, True, CAPS, None)["job"]
        self.relay.result(self.token, running["job_id"], running["digest"],
                          "succeeded", {"executed_by": "android"})
        restarted = Relay(self.url, BASE, SECRET, clock=lambda: self.now[0])
        self.assertEqual(job["job_id"], running["job_id"])
        self.assertEqual(
            restarted.job(self.access, job["job_id"])["result"],
            {"executed_by": "android"},
        )
        with self.assertRaises(Denied):
            restarted.enroll(SECRET, "Repeated enrollment")

    def test_fifo_and_idempotency_at_identical_timestamps(self):
        ids = [self.relay.submit(self.access, "pg-item-" + str(i), "engine.status", {})
               for i in range(7)]
        for receipt in ids:
            dispatched = self.relay.poll(self.token, True, CAPS, None)["job"]
            self.assertEqual(receipt["job_id"], dispatched["job_id"])
            self.relay.result(self.token, dispatched["job_id"], dispatched["digest"],
                              "succeeded", {"pass": True})
            repeated = self.relay.submit(
                self.access, "pg-item-" + str(ids.index(receipt)), "engine.status", {})
            self.assertEqual(repeated["job_id"], receipt["job_id"])

    def test_revocation_persists_across_restarts(self):
        self.relay.revoke(self.token)
        recreated = Relay(self.url, BASE, SECRET, clock=lambda: self.now[0])
        with self.assertRaises(Denied):
            recreated.status(self.access)
        with self.assertRaises(Denied):
            recreated.poll(self.token, True, CAPS, None)


if __name__ == "__main__":
    unittest.main()
