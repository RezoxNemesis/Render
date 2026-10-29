# SPDX-License-Identifier: GPL-2.0-or-later
"""Negative gates for an incorrect signer, stale runtime, or wrong Android APK."""
import io
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile
from unittest.mock import patch

from tools import verify_creator_apk as V
from tools import prepare_production_toolkit as P


class CreatorApkReleaseChecks(unittest.TestCase):
    def setUp(self):
        self.badging = ("package: name='com.rezox.render' versionCode='62' "
                        "versionName='0.61.0-direct-mcp'\n"
                        "sdkVersion:'31'\nnative-code: 'arm64-v8a'\n")
        self.signature = "Signer #1 certificate SHA-256 digest: " + V.SIGNER_SHA256 + "\n"

    def test_original_package_monotonic_version_and_historical_signer(self):
        report = V.verify_android_identity(self.badging, self.signature)
        self.assertEqual(report["version_code"], 62)
        self.assertEqual(report["signer_certificate_sha256"], V.SIGNER_SHA256)

    def test_rejects_wrong_package_version_minimum_and_abi(self):
        for original, replacement in (("com.rezox.render", "com.rezox.render.preview"),
                                      ("versionCode='62'", "versionCode='61'"),
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
                            {"missing": "render_motion_lab.py"},
                            {"stale": "render_animation_layers.py"},
                            {"stale": "render_animation_finish.py"},
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

    def test_version_adapter_promotes_previous_release_once_and_refuses_future_versions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = (("app/build.gradle.kts", 'versionCode = 61\nversionName = "0.60.0-animation-studio"'),
                     ("full-app/app/build.gradle", "versionCode 61\nversionName '0.60.0-animation-studio'"))
            for relative, contents in files:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(contents)
            with patch.object(P, "ROOT", root):
                P.promote_startup_version()
                promoted = {relative: (root / relative).read_bytes() for relative, _ in files}
                P.promote_startup_version()
                self.assertEqual(promoted, {relative: (root / relative).read_bytes() for relative, _ in files})
                for relative, _ in files:
                    self.assertIn(V.VERSION_NAME, (root / relative).read_text())
                (root / files[0][0]).write_text('versionCode = 63\nversionName = "0.62.0"')
                with self.assertRaises(RuntimeError):
                    P.promote_startup_version()


if __name__ == "__main__":
    unittest.main()
