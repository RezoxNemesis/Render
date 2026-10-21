#!/usr/bin/env python3
"""Repository contract checks; not a substitute for Android/Blender parity tests."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
manifest = (root / "app/src/main/AndroidManifest.xml").read_text()
jni = (root / "app/src/main/cpp/render_bridge.cpp").read_text()
activity = (root / "app/src/main/java/com/rezox/render/MainActivity.java").read_text()
readme = (root / "README.md").read_text()
store = (root / "docs/ASSETS_AND_STORAGE.md").read_text()

required = {
    "no network permission required": "android.permission.INTERNET" not in manifest,
    "engine must not pretend ready": "JNI_FALSE" in jni and "NOT integrated" not in jni.replace("NOT integrated", ""),
    "SAF import": "ACTION_OPEN_DOCUMENT" in activity,
    "local streaming": "InputStream" in activity and "OutputStream" in activity,
    "honest scaffold status": "does not yet contain or execute Blender itself" in readme,
    "Drive optional": "optional" in store and "NO Blender factory assets have been uploaded" in store,
}
for name, ok in required.items():
    print(("PASS" if ok else "FAIL") + " " + name)
sys.exit(0 if all(required.values()) else 1)
