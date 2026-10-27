# SPDX-License-Identifier: GPL-2.0-or-later
"""Negative gates for an incorrect signer, stale runtime, or wrong Android APK."""
import io
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

from tools import verify_creator_apk as V


class CreatorApkReleaseChecks(unittest.TestCase):
    def setUp(self):
        self.badging = ("package: name='com.rezox.render' versionCode='60' "
                        "versionName='0.50.0-creator-studio'\n"
                        "sdkVersion:'31'\nnative-code: 'arm64-v8a'\n")
        self.signature = "Signer #1 certificate SHA-256 digest: " + V.SIGNER_SHA256 + "\n"

    def test_original_package_monotonic_version_and_historical_signer(self):
        report = V.verify_android_identity(self.badging, self.signature)
        self.assertEqual(report["version_code"], 60)
        self.assertEqual(report["signer_certificate_sha256"], V.SIGNER_SHA256)

    def test_rejects_wrong_package_version_minimum_and_abi(self):
        for original, replacement in (("com.rezox.render", "com.rezox.render.preview"),
                                      ("versionCode='60'", "versionCode='49'"),
                                      (V.VERSION_NAME, "0.40.0-viewport-fidelity"),
                                      ("sdkVersion:'31'", "sdkVersion:'28'"),
                                      ("'arm64-v8a'", "'arm64-v8a' 'x86_64'")):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                V.verify_android_identity(self.badging.replace(original, replacement), self.signature)

    def test_rejects_missing_different_or_additional_signer(self):
        for signature in ("", self.signature.replace(V.SIGNER_SHA256, "a" * 64),
                          self.signature + self.signature.replace("#1", "#2")):
            with self.subTest(signature=signature), self.assertRaises(ValueError):
                V.verify_android_identity(self.badging, signature)

    def runtime(self, sources, missing=None, stale=None, duplicate=None):
        memory = io.BytesIO()
        with zipfile.ZipFile(memory, "w") as archive:
            for source in sources.rglob("*.py"):
                relative = source.relative_to(sources).as_posix()
                if relative == missing:
                    continue
                name = "scripts/startup/" + relative
                archive.writestr(name, b"old runtime\n" if relative == stale else source.read_bytes())
                if relative == duplicate:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        archive.writestr(name, source.read_bytes())
        memory.seek(0)
        return zipfile.ZipFile(memory)

    def test_every_runtime_source_must_match_exact_checkout_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            sources = Path(temporary)
            for name in V.REQUIRED_CREATOR_MODULES | {"render_existing_feature.py"}:
                (sources / name).write_text("# current " + name + "\n")
            with self.runtime(sources) as archive:
                result = V.verify_packaged_source(archive, sources)
                self.assertEqual(set(result), V.REQUIRED_CREATOR_MODULES | {"render_existing_feature.py"})
            for failure in ({"missing": "render_creator_ops.py"},
                            {"stale": "render_command_planner.py"},
                            {"stale": "render_existing_feature.py"},
                            {"duplicate": "render_creator_ui.py"}):
                with self.subTest(failure=failure), self.runtime(sources, **failure) as archive:
                    with self.assertRaises(ValueError):
                        V.verify_packaged_source(archive, sources)

    def test_empty_source_tree_cannot_approve_old_apk(self):
        with tempfile.TemporaryDirectory() as temporary:
            sources = Path(temporary)
            with self.runtime(sources) as archive, self.assertRaises(ValueError):
                V.verify_packaged_source(archive, sources)


if __name__ == "__main__":
    unittest.main()
