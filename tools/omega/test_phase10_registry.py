"""Host-only tests: mocks here are not native Blender evidence."""
from pathlib import Path
import re
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "full-app" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import omega_registry as registry


class RegistryTests(unittest.TestCase):
    def context(self):
        return {"scene": object(), "production_root": "/private/native",
                "job_id": "a" * 32, "available_memory_bytes": 10000,
                "dry_run": False, "cancellation_requested": False,
                "capability_revision": registry.CAPABILITY_REVISION}

    def synthetic_module(self, **override):
        module = types.ModuleType("omega.phase04_geometry")
        module.CONTRACT_VERSION = registry.CONTRACT_VERSION
        module.OPERATION_NAMES = ("omega.geometry.inspect",)
        module.validate = lambda operation, payload: dict(payload)
        module.execute = lambda op, payload, context: {
            "operation": op, "state": "succeeded", "native_execution_verified": True,
            "quality_reduced": False, "created": []}
        module.audit = lambda op, payload, context: {"objects": 0}
        for name, value in override.items():
            setattr(module, name, value)
        return module

    def test_missing_modules_never_crash_registry(self):
        report = registry.capabilities()
        self.assertEqual(12, len(report["phases"]))
        self.assertEqual(set(registry.OPERATION_NAMES),
                         set(report["enabled_operations"]))
        self.assertIn(report["phases"][3]["status"], ("NOT_INSTALLED", "INSTALLED_UNVERIFIED"))
        self.assertFalse(report["quality_reduced"])

    def test_java_allowlist_matches_native_python_registry(self):
        path = ROOT / "app/src/main/java/com/rezox/render/omega/integration/OmegaOperations.java"
        names = set(re.findall(r'"(omega\.[a-z_]+\.[a-z_]+)"', path.read_text()))
        self.assertEqual(set(registry._ALLOWED) | set(registry.OPERATION_NAMES), names)

    def test_unknown_actions_and_oversize_payload_are_rejected(self):
        context = self.context()
        for operation in ("python.eval", "omega.geometry.eval", "bpy.ops.anything"):
            with self.subTest(operation=operation), self.assertRaisesRegex(
                    ValueError, "NATIVE_BLENDER_ACTION_UNAVAILABLE"):
                registry.dispatch(operation, {}, context)
        with self.assertRaisesRegex(ValueError, "COMMAND_TOO_LARGE"):
            registry.dispatch("omega.integration.capabilities",
                              {"blob": "x" * 131072}, context)
        for invalid in ([1], {"value": float("nan")}, {"value": object()}):
            with self.subTest(invalid=str(invalid)), self.assertRaisesRegex(
                    ValueError, "INVALID_ARGUMENTS"):
                registry.dispatch("omega.integration.capabilities", invalid, context)

    def test_native_context_cannot_be_supplied_with_bad_revision_or_job(self):
        context = self.context()
        for field, value, code in [("job_id", "bad", "INVALID_COMMAND_ID"),
                                   ("capability_revision", "stale", "CHECKPOINT_CONFLICT"),
                                   ("available_memory_bytes", -1, "INVALID_NATIVE_CONTEXT"),
                                   ("dry_run", True, "INVALID_NATIVE_CONTEXT")]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, code):
                registry.dispatch("omega.integration.capabilities", {},
                                  {**context, field: value})

    def test_installed_does_not_mean_verified_or_executable(self):
        module = self.synthetic_module()
        with mock.patch.dict(sys.modules, {"omega.phase04_geometry": module}):
            report = registry.capabilities()
            self.assertEqual("INSTALLED_UNVERIFIED", report["phases"][3]["status"])
            self.assertNotIn("omega.geometry.inspect", report["enabled_operations"])
            with self.assertRaisesRegex(RuntimeError, "CAPABILITY_NOT_VERIFIED"):
                registry.dispatch("omega.geometry.inspect", {}, self.context())

    def test_validated_phase_receipt_and_native_gate(self):
        module = self.synthetic_module()
        with mock.patch.dict(sys.modules, {"omega.phase04_geometry": module}), \
             mock.patch.object(registry, "VERIFIED_PHASES", frozenset({4})):
            with self.assertRaisesRegex(RuntimeError, "UNSUPPORTED_NATIVE_FEATURE"):
                registry.dispatch("omega.geometry.inspect", {}, self.context())
            with mock.patch.object(registry, "_real_scene", return_value=True):
                result = registry.dispatch("omega.geometry.inspect", {}, self.context())
                self.assertEqual("succeeded", result["state"])
                self.assertTrue(result["native_execution_verified"])

    def test_invalid_phase_contract_fails_closed(self):
        module = self.synthetic_module(OPERATION_NAMES=("omega.geometry.inspect",
                                                          "omega.simulation.bake"))
        with mock.patch.dict(sys.modules, {"omega.phase04_geometry": module}), \
             mock.patch.object(registry, "VERIFIED_PHASES", frozenset({4})):
            report = registry.capabilities()
            self.assertEqual("INVALID_CONTRACT", report["phases"][3]["status"])
            with self.assertRaisesRegex(RuntimeError, "CAPABILITY_NOT_VERIFIED"):
                registry.dispatch("omega.geometry.inspect", {}, self.context())

    def test_invalid_receipt_must_not_claim_success(self):
        module = self.synthetic_module(execute=lambda *_: {"state": "succeeded"})
        with mock.patch.dict(sys.modules, {"omega.phase04_geometry": module}), \
             mock.patch.object(registry, "VERIFIED_PHASES", frozenset({4})), \
             mock.patch.object(registry, "_real_scene", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "NATIVE_RECEIPT_INVALID"):
                registry.dispatch("omega.geometry.inspect", {}, self.context())


if __name__ == "__main__":
    unittest.main()
