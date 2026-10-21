#!/usr/bin/env python3
"""Repackage a SHA-pinned *real* Android Blender Full engine and Render's agent
into one Android Studio project. Build-only operation; nothing downloaded on phone.
Does not claim device compatibility until the resulting APK is tested on hardware.
"""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import xml.etree.ElementTree as ET
import zipfile

UPSTREAM_COMMIT = "d93bd33cba768e19ee4387a31c0ea137ee2f0047"
ENGINE_SHA256 = "3fe775a1e14470ebfcd3c25ae32b57003433f04552f896880631ae98b1f18aea"
ENGINE_BYTES = 286561495
ANDROID = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", ANDROID[1:-1])

def verify_apk(apk, expected_size=ENGINE_BYTES, expected_digest=ENGINE_SHA256):
    apk = Path(apk)
    if apk.stat().st_size != expected_size:
        raise ValueError("PINNED_ENGINE_APK_SIZE_MISMATCH")
    h = hashlib.sha256()
    with apk.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_digest:
        raise ValueError("PINNED_ENGINE_APK_SHA256_MISMATCH")

def valid_zip_entry(info):
    name = info.filename
    p = PurePosixPath(name)
    if not name or "\\" in name or p.is_absolute() or ".." in p.parts:
        raise ValueError("UNSAFE_ENGINE_APK_MEMBER")
    # Reject symlinks and non-regular Unix file types even in a hash-verified APK.
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
        raise ValueError("UNSAFE_ENGINE_APK_MEMBER")
    return name

def merge_manifest(source):
    root = ET.parse(source).getroot()
    root.attrib.pop("package", None)   # AGP 8+ namespace comes from Gradle.
    application = root.find("application")
    if application is None:
        raise ValueError("UPSTREAM_MANIFEST_NO_APPLICATION")
    activity = next((node for node in application.findall("activity")
                     if node.get(ANDROID + "name") == "org.blender.blender.BlenderActivity"), None)
    if activity is None:
        raise ValueError("UPSTREAM_BLENDER_ACTIVITY_MISSING")
    # One launcher opens Render's hub; native editor keeps .blend VIEW/EDIT intents.
    for intent in list(activity.findall("intent-filter")):
        if any(x.get(ANDROID + "name") == "android.intent.action.MAIN"
               for x in intent.findall("action")):
            activity.remove(intent)

    existing = {p.get(ANDROID + "name") for p in root.findall("uses-permission")}
    for permission in ("android.permission.FOREGROUND_SERVICE",
                       "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
                       "android.permission.POST_NOTIFICATIONS"):
        if permission not in existing:
            ET.SubElement(root, "uses-permission", {ANDROID + "name": permission})
    application.set(ANDROID + "label", "Render Studio")
    application.set(ANDROID + "allowBackup", "false")
    application.set(ANDROID + "usesCleartextTraffic", "false")
    hub = ET.SubElement(application, "activity", {
        ANDROID + "name": "com.rezox.render.RenderHubActivity",
        ANDROID + "exported": "true",
        ANDROID + "screenOrientation": "unspecified",
    })
    filter_ = ET.SubElement(hub, "intent-filter")
    ET.SubElement(filter_, "action", {ANDROID + "name": "android.intent.action.MAIN"})
    ET.SubElement(filter_, "category", {ANDROID + "name": "android.intent.category.LAUNCHER"})
    for klass in ("com.rezox.render.MainActivity", "com.rezox.render.agent.AgentActivity"):
        ET.SubElement(application, "activity", {
            ANDROID + "name": klass,
            ANDROID + "exported": "false",
            ANDROID + "screenOrientation": "unspecified",
        })
    service = ET.SubElement(application, "service", {
        ANDROID + "name": "com.rezox.render.agent.AgentService",
        ANDROID + "exported": "false",
        ANDROID + "foregroundServiceType": "specialUse",
    })
    ET.SubElement(service, "property", {
        ANDROID + "name": "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE",
        ANDROID + "value": "User-started and visible remote native project-command session with notification, Stop and Revoke",
    })
    return ET.ElementTree(root)

def check_source(source, verify):
    path = Path(source)
    manifest = path / "build_files/android/apk/app/src/main/AndroidManifest.xml"
    java = path / "build_files/android/apk/app/src/main/java/org/blender/blender/BlenderActivity.java"
    res = path / "build_files/android/apk/app/src/main/res"
    if not manifest.is_file() or not java.is_file() or not res.is_dir():
        raise ValueError("UPSTREAM_ANDROID_SOURCE_INCOMPLETE")
    if verify:
        revision = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
        if revision != UPSTREAM_COMMIT:
            raise ValueError("UPSTREAM_SOURCE_REVISION_MISMATCH")
    return manifest, java, res

def stage(engine, bridge, source, destination, expected_size=ENGINE_BYTES,
          expected_digest=ENGINE_SHA256, verify_source=True):
    verify_apk(engine, expected_size, expected_digest)
    manifest, java, res = check_source(source, verify_source)
    destination = Path(destination)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    libraries = destination / "lib/arm64-v8a"
    assets = destination / "assets"
    libraries.mkdir(parents=True)
    assets.mkdir(parents=True)
    seen = set()
    with zipfile.ZipFile(engine) as original:
        for info in original.infolist():
            name = valid_zip_entry(info)
            if name in seen:
                raise ValueError("DUPLICATED_ENGINE_APK_MEMBER")
            seen.add(name)
            if info.is_dir():
                continue
            if (name.startswith("lib/arm64-v8a/") and name.endswith(".so") and
                name.count("/") == 2) or name.startswith("assets/"):
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with original.open(info) as readable, target.open("wb") as output:
                    shutil.copyfileobj(readable, output, length=1024 * 1024)
    essentials = [
        libraries / "libblender.so",
        libraries / "libc++_shared.so",
        assets / "blender_runtime.zip",
    ]
    if not all(p.is_file() and p.stat().st_size > 0 for p in essentials):
        raise ValueError("FULL_BLENDER_NATIVE_RUNTIME_INCOMPLETE")
    with zipfile.ZipFile(bridge) as agent_apk:
        key = "lib/arm64-v8a/librender_bridge.so"
        if key not in agent_apk.namelist():
            raise ValueError("RENDER_NATIVE_AGENT_LIBRARY_MISSING")
        target = libraries / "librender_bridge.so"
        if target.exists():
            raise ValueError("UPSTREAM_AGENT_LIBRARY_COLLISION")
        with agent_apk.open(key) as readable, target.open("wb") as output:
            shutil.copyfileobj(readable, output, length=1024 * 1024)
    java_dst = destination / "java/org/blender/blender/BlenderActivity.java"
    java_dst.parent.mkdir(parents=True)
    shutil.copy2(java, java_dst)
    shutil.copytree(res, destination / "res", dirs_exist_ok=True)
    merged = merge_manifest(manifest)
    merged.write(destination / "AndroidManifest.xml", encoding="utf-8", xml_declaration=True)
    notices = assets / "licenses"
    notices.mkdir(exist_ok=True)
    (notices / "Render-Full-Native-Sources.txt").write_text(
        "Full Blender native engine source: https://github.com/simfeo/blender\n"
        "Pinned source revision: " + UPSTREAM_COMMIT + "\n"
        "APK release: https://github.com/simfeo/blender/releases/tag/android-alpha-4\n"
        "Engine APK SHA-256: " + ENGINE_SHA256 + "\n"
        "Blender source is GPL-2.0-or-later; consult matching source and bundled licenses.\n"
        "Render Android agent code and build adapters are in https://github.com/RezoxNemesis/Render\n",
        encoding="utf-8")
    print("STAGED_FULL_NATIVE_BLENDER", len(list(libraries.glob("*.so"))),
          "libraries", (assets / "blender_runtime.zip").stat().st_size, "runtime bytes")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-apk", required=True)
    parser.add_argument("--bridge-apk", required=True)
    parser.add_argument("--upstream-source", required=True)
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    stage(a.engine_apk, a.bridge_apk, a.upstream_source, a.output)

if __name__ == "__main__":
    main()
