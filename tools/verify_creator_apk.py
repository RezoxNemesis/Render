#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail closed on a stale, incomplete, or differently signed Animation Studio APK.

The Android build tools verify the actual APK signature and binary manifest.
This check also compares every shipped Render Python source with the checkout,
and verifies the exact existing patched ARM64 Blender engine. It does not imply
that the application has been installed or tested on an Android device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

PACKAGE = "com.rezox.render"
VERSION_CODE = "62"
VERSION_NAME = "0.61.0-direct-mcp"
SIGNER_SHA256 = "f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30"
ENGINE_SHA256 = "a87b805df88ab64b4af21baac98bf380de9b0a1d90ac5525c082c5aceac29d59"
REQUIRED_CREATOR_MODULES = frozenset({
    "render_creator_contract.py", "render_creator_ops.py", "render_creator_ui.py",
    "render_command_contract.py", "render_command_planner.py",
    "render_animation_layers.py", "render_animation_layers_contract.py",
    "render_motion_lab.py", "render_motion_lab_contract.py",
    "render_animation_finish.py", "render_animation_finish_contract.py",
    "render_animation_suite.py", "render_animation_ui.py",
})


def digest_stream(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def verify_android_identity(badging, signature):
    package_line = next((line for line in badging.splitlines()
                         if line.startswith("package: ")), "")
    identity = dict(re.findall(r"(\w+)='([^']*)'", package_line))
    if (identity.get("name"), identity.get("versionCode"), identity.get("versionName")) != (
            PACKAGE, VERSION_CODE, VERSION_NAME):
        raise ValueError("CREATOR_APK_IDENTITY_MISMATCH")
    if not re.search(r"^sdkVersion:'31'\s*$", badging, re.MULTILINE):
        raise ValueError("CREATOR_APK_MINIMUM_ANDROID_MISMATCH")
    native_line = next((line for line in badging.splitlines()
                        if line.startswith("native-code:")), "")
    if re.findall(r"'([^']+)'", native_line) != ["arm64-v8a"]:
        raise ValueError("CREATOR_APK_NATIVE_ABI_MISMATCH")
    signers = re.findall(r"^Signer #(\d+) certificate SHA-256 digest: ([a-fA-F0-9:]+)\s*$",
                         signature, re.MULTILINE)
    if (len(signers) != 1 or signers[0][0] != "1" or
            signers[0][1].replace(":", "").lower() != SIGNER_SHA256):
        raise ValueError("CREATOR_APK_HISTORICAL_SIGNER_MISMATCH")
    return {"package": PACKAGE, "version_code": int(VERSION_CODE),
            "version_name": VERSION_NAME, "minimum_android_api": 31,
            "abi": "arm64-v8a", "signer_certificate_sha256": SIGNER_SHA256}


def verify_packaged_source(runtime, source_dir):
    members = runtime.namelist()
    if len(members) != len(set(members)):
        raise ValueError("CREATOR_DUPLICATED_RUNTIME_MEMBER")
    sources = {p.relative_to(source_dir).as_posix(): p
               for p in source_dir.rglob("*.py")}
    if not REQUIRED_CREATOR_MODULES.issubset(sources):
        raise ValueError("CREATOR_SOURCE_MODULE_MISSING")
    proof = {}
    for relative, source in sorted(sources.items()):
        member = "scripts/startup/" + relative
        if member not in members:
            raise ValueError("CREATOR_RUNTIME_MODULE_MISSING: " + relative)
        packaged = runtime.read(member)
        if packaged != source.read_bytes():
            raise ValueError("CREATOR_RUNTIME_SOURCE_MISMATCH: " + relative)
        proof[relative] = hashlib.sha256(packaged).hexdigest()
    return proof


def verify_native_libraries(apk):
    result = {}
    for name in ("libblender.so", "librender_bridge.so", "libc++_shared.so"):
        member = "lib/arm64-v8a/" + name
        with apk.open(member) as stream:
            header = stream.read(64)
        if (len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or
                struct.unpack_from("<H", header, 18)[0] != 183):
            raise ValueError("CREATOR_NATIVE_LIBRARY_NOT_ARM64_ELF: " + name)
        with apk.open(member) as stream:
            digest = digest_stream(stream)
        result[name] = {"sha256": digest, "bytes": apk.getinfo(member).file_size}
    if result["libblender.so"]["sha256"] != ENGINE_SHA256:
        raise ValueError("CREATOR_NATIVE_ENGINE_CHANGED")
    notices = json.loads(apk.read("assets/licenses/Render-Native-Engine-Patches.json"))
    if notices.get("patched_library_sha256") != ENGINE_SHA256:
        raise ValueError("CREATOR_NATIVE_ENGINE_PROVENANCE_MISMATCH")
    return result


def verify(apk_path, source_dir, build_tools, source_sha, report_dir):
    if not re.fullmatch(r"[a-f0-9]{40}", source_sha):
        raise ValueError("CREATOR_EXACT_SOURCE_COMMIT_REQUIRED")
    report_dir.mkdir(parents=True, exist_ok=True)
    commands = {
        "signature": [str(build_tools / "apksigner"), "verify", "--verbose", "--print-certs", str(apk_path)],
        "badging": [str(build_tools / "aapt"), "dump", "badging", str(apk_path)],
        "manifest": [str(build_tools / "aapt"), "dump", "xmltree", str(apk_path), "AndroidManifest.xml"],
    }
    output = {}
    for name, command in commands.items():
        output[name] = subprocess.run(command, check=True, capture_output=True, text=True).stdout
        (report_dir / ("render-creator-" + name + ".txt")).write_text(output[name], encoding="utf-8")
    report = verify_android_identity(output["badging"], output["signature"])
    for required in ("RenderLongForegroundService", "FOREGROUND_SERVICE_MEDIA_PROCESSING",
                     "FileTransferService", "FOREGROUND_SERVICE_DATA_SYNC"):
        if required not in output["manifest"]:
            raise ValueError("CREATOR_ANDROID_SERVICE_MISSING: " + required)
    for forbidden in ("VideoStudioNativeBridgeService", "com.rezoxnemesis.videostudio"):
        if forbidden in output["manifest"]:
            raise ValueError("LEGACY_VIDEOSTUDIO_BRIDGE_STILL_EXPORTED: " + forbidden)
    with zipfile.ZipFile(apk_path) as apk:
        if len(apk.namelist()) != len(set(apk.namelist())):
            raise ValueError("CREATOR_DUPLICATED_APK_MEMBER")
        if apk.testzip() is not None:
            raise ValueError("CREATOR_APK_CORRUPT_MEMBER")
        report["native_libraries"] = verify_native_libraries(apk)
        with tempfile.TemporaryFile() as runtime_file:
            with apk.open("assets/blender_runtime.zip") as packed:
                shutil.copyfileobj(packed, runtime_file, 1024 * 1024)
            runtime_file.seek(0)
            with zipfile.ZipFile(runtime_file) as runtime:
                report["runtime_source_sha256"] = verify_packaged_source(runtime, source_dir)
    with apk_path.open("rb") as stream:
        report["apk_sha256"] = digest_stream(stream)
    report.update({"apk_filename": apk_path.name, "apk_bytes": apk_path.stat().st_size,
                   "source_commit": source_sha, "historical_development_signer": True,
                   "permanent_release_signing_claimed": False,
                   "android_device_install_tested": False,
                   "android_gpu_or_thermal_performance_tested": False})
    (report_dir / "render-creator-verification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parents[1] / "full-app/scripts")
    parser.add_argument("--build-tools", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.apk, args.source_dir, args.build_tools, args.source_sha, args.report_dir)
    print("PASS: Animation Studio APK", result["apk_sha256"], "source", result["source_commit"],
          "runtime modules", len(result["runtime_source_sha256"]))


if __name__ == "__main__":
    main()
