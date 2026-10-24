# Render 0.31.1 workspace testing

Historical result. Subsequent owner-authorized native modelling/animation checks
and the startup ANR fix are recorded in
[WORKSPACE_TESTING_0312.md](WORKSPACE_TESTING_0312.md).

Application: `com.rezox.render`, versionCode 37 / `0.31.1-native-reliability`.
Built application source: `37062c838cdf58e52f912eb0fff0606aa86680bd`.

## Passed

- **149 Android/JVM tests, zero failures/errors**, using JDK 17, Gradle 8.11.1,
  Android SDK 35 and Robolectric. Covers the migrated command journal, interrupted
  exact-ID recovery, retained results, queued cancellation, memory/thermal gates,
  render scheduling, readiness bound to process and launch, and existing behavior.
- **118 Python checks, zero failures**: 45 contracts, 68 behavior checks and five
  asset archive/catalog regressions. These are host checks with explicit doubles,
  without running Blender or constructing/rendering native benchmark scenes.
- Foundation APK, full native APK and workspace-only instrumentation APK compiled.
- Historical-signer CI build passed: https://github.com/RezoxNemesis/Render/actions/runs/40064887156
- Delivered APK independently passed signature, SHA-256, ZIP CRC and packaged
  Python-source equality checks. It retains the real pinned Android Blender engine.

Tests exposed and fixed missing finite-catalog metadata and a misleading HUD zero
when timing was unavailable. Older fixtures were updated to assert the new secure
readiness handshake, durable queue behavior and cancellation-aware pacing.

## Native emulator attempt: environment blocked

A fresh Android 15/API 35 Google APIs x86_64 emulator was created in the workspace.
Emulator version 37.2.12; ARM64 supported through `libndk_translation.so`; software
SwiftShader GPU. The workspace has **no KVM/CPU hardware virtualization**. No phone
or other existing device was used.

ADB became available, but Android did not set `sys.boot_completed` during the
480-second observation window after ADB availability. System services appeared
progressively, but app installation remained blocked. Both streaming and push
installation failed inside Android's booting package/storage framework:

```
java.lang.NullPointerException:
PackageManagerInternal.freeStorage(...) on a null object reference
at com.android.server.StorageManagerService.allocateBytes(...)
```

This happened before Render application code executed. It is **not a Render crash
or a successful installation**. The native UI, launch/readiness smoke checks,
configuration survival and the added read-only native diagnostics could not run.
The owned emulator was stopped after preserving the logs.

No animation, benchmark scene, production render or encoding was created. Native
Blender behavior, physical-phone compatibility, performance, thermal behavior and
24-hour/background endurance remain unverified. A hardware-accelerated Android
emulator or the owner's phone is the next runtime target; poll actual native
readiness before proceeding with any mutation.

## Artifact identity

APK SHA-256:
`5b993e4654d4867dd6790fb7fb0248eb29e5fa95b6e406392a75a87052db7cb6`

Historical certificate SHA-256:
`f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`

The current phone's installed certificate was not queried. No phone installation,
uninstall or data clear occurred. Matching the historical certificate is necessary
for an in-place update; do not uninstall to work around a signer mismatch.
