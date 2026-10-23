"""Fail-closed pre-install APK gate; NEVER installs, signs or generates keys.

Call with --apk and actual installed package signer/version read on the device.
A source Gradle version or cached keystore fingerprint is not device evidence.
"""
import argparse
import io
import re
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

PACKAGE = "com.rezox.render"
REQUIRED = ("lib/arm64-v8a/libblender.so", "lib/arm64-v8a/librender_bridge.so")
ZIP = "assets/blender_runtime.zip"
STARTUP = ("scripts/startup/render_agent_startup.py",
           "scripts/startup/omega_registry.py",
           "scripts/startup/omega/__init__.py")


def inspect(apk, signer_log, badging, installed_signer, installed_version):
    installed_signer = re.sub("[^0-9a-f]", "", installed_signer.lower())
    if len(installed_signer) != 64 or not isinstance(installed_version, int) or installed_version < 1:
        raise ValueError("INSTALLED_PACKAGE_PROOF_REQUIRED")
    matches = re.findall(r"Signer #\d+ certificate SHA-256 digest:\s*([a-fA-F0-9]{64})",
                         signer_log)
    if len(matches) != 1 or matches[0].lower() != installed_signer:
        raise ValueError("INSTALLED_CERTIFICATE_MISMATCH")
    fields = re.search(r"package: name='([^']+)' versionCode='(\d+)'", badging)
    if not fields or fields.group(1) != PACKAGE:
        raise ValueError("ORIGINAL_PACKAGE_ID_MISMATCH")
    version = int(fields.group(2))
    if version <= installed_version:
        raise ValueError("VERSION_CODE_NOT_GREATER_THAN_INSTALLED")
    with zipfile.ZipFile(apk) as package:
        members = package.namelist()
        if len(members) != len(set(members)) or package.testzip() is not None:
            raise ValueError("APK_ZIP_INTEGRITY_FAILED")
        if any(name not in members or package.getinfo(name).file_size < 1
               for name in REQUIRED + (ZIP,)):
            raise ValueError("PINNED_NATIVE_LIBRARIES_MISSING")
        with zipfile.ZipFile(io.BytesIO(package.read(ZIP))) as runtime:
            embedded = runtime.namelist()
            if len(embedded) != len(set(embedded)) or runtime.testzip() is not None:
                raise ValueError("BLENDER_RUNTIME_ZIP_INVALID")
            if any(name not in embedded for name in STARTUP):
                raise ValueError("OMEGA_RUNTIME_MODULE_MISSING")
    return {"package": PACKAGE, "apk_version_code": version,
            "installed_version_code": installed_version,
            "signer_matches_installed": True, "omega_runtime_packaged": True,
            "safe_for_install": False, "phone_validation_required": True}


class ReleaseGateTests(unittest.TestCase):
    CERT = "a" * 64
    SIGN = "Signer #1 certificate SHA-256 digest: " + CERT
    BADGING = "package: name='com.rezox.render' versionCode='28' versionName='0.26'"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, present=True):
        path = Path(self.temp.name) / "fixture.apk"
        with zipfile.ZipFile(path, "w") as apk:
            for name in REQUIRED:
                apk.writestr(name, b"synthetic native library")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as runtime:
                for entry in STARTUP if present else STARTUP[:1]:
                    runtime.writestr(entry, b"# synthetic fixture")
            apk.writestr(ZIP, buffer.getvalue())
        return path

    def test_matching_signed_package_is_only_preflight_not_device_proof(self):
        result = inspect(self.fixture(), self.SIGN, self.BADGING, self.CERT, 27)
        self.assertFalse(result["safe_for_install"])
        self.assertTrue(result["phone_validation_required"])

    def test_exact_installed_cert_and_strict_monotonic_version(self):
        file = self.fixture()
        cases = [(self.CERT, 28, self.SIGN, self.BADGING, "VERSION_CODE"),
                 ("b" * 64, 27, self.SIGN, self.BADGING, "CERTIFICATE_MISMATCH"),
                 ("", 27, self.SIGN, self.BADGING, "PROOF_REQUIRED"),
                 (self.CERT, 27, self.SIGN,
                  self.BADGING.replace("com.rezox.render", "com.rezox.render.preview"), "PACKAGE_ID")]
        for cert, installed, sign, badge, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                inspect(file, sign, badge, cert, installed)

    def test_missing_omega_runtime_is_hard_error(self):
        with self.assertRaisesRegex(ValueError, "OMEGA_RUNTIME_MODULE_MISSING"):
            inspect(self.fixture(False), self.SIGN, self.BADGING, self.CERT, 27)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apk", type=Path, required=True)
    p.add_argument("--installed-signer-sha256", required=True)
    p.add_argument("--installed-version-code", type=int, required=True)
    p.add_argument("--apksigner", required=True)
    p.add_argument("--aapt", required=True)
    args = p.parse_args()
    signature = subprocess.check_output(
        [args.apksigner, "verify", "--print-certs", str(args.apk)], text=True)
    badging = subprocess.check_output([args.aapt, "dump", "badging", str(args.apk)], text=True)
    print(inspect(args.apk, signature, badging, args.installed_signer_sha256,
                  args.installed_version_code))


if __name__ == "__main__":
    import sys
    if "--apk" in sys.argv:
        main()
    else:
        unittest.main()
