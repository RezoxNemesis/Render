# Render 0.31.2 native workspace evidence

Application `com.rezox.render`, versionCode **38**,
`0.31.2-native-startup-storage`. Native runtime-tested application source:
`b5a4ba9d3d96da7c69e3a09e9631dfd20b42bd2e`.
Historical-signer build:
https://github.com/RezoxNemesis/Render/actions/runs/40069907206

The owner subsequently requested real native asset and animation testing. This
report supersedes the initial blocked-emulator outcome in
[WORKSPACE_TESTING_0311.md](WORKSPACE_TESTING_0311.md). Host checks, a launch request,
an installed APK or a queued render do not establish native output success.

## Environment and startup findings

The isolated workspace uses Android 15/API 35 Google APIs x86_64 r09, emulator
37.2.12 and ARM64 `libndk_translation`/Berberis. The host has no KVM, four CPU cores
and a 16 GiB memory limit. Render's packaged ARM64 Blender runs inside Android;
no desktop/cloud Blender, external generator or Gallery access is used.

- An early boot attempt failed in Android's package/storage framework before
  installation. A subsequent boot installed the historical-signer candidate.
- Real execution exposed an input-dispatch ANR in the old native activity's
  startup log probe of shared Downloads. Version 0.31.2 prepares private startup
  storage in the preflight worker and removes UI-thread storage probing.
- SwiftShader failed Blender's required Vulkan geometry-shader support and the
  native process crashed. Lavapipe passed that device check and initialized the
  native GPU resources, Python and Blender timer.
- The first Lavapipe emulator aborted in Mesa's host `llvmpipe_map_memory`
  assertion. The cgroup recorded no OOM kill. This does not establish an app
  memory leak, a phone GPU issue or a successfully completed model.
- Recovery retained the same application data and used Lavapipe with two
  software-GPU workers, a 4 GiB/two-core guest and a 1280×960 display. A Java
  debugger remained attached to avoid stock input timeouts during very slow
  software execution. This is a diagnostic environment, not a normal startup
  performance measurement. Display size does not change camera render quality.

## Confirmed native results

The recovered process published a fresh timer heartbeat bound to its actual PID
and native launch identity. Fixed read-only diagnostics passed through the same
ProductionBridge/native executor used by the existing integration:

- Blender **5.3.0 Alpha**, active scene `Scene`, three startup objects, camera and
  editable mesh data. Existing settings were 1920×1080, 100%, 64 samples, 24 fps,
  engine `BLENDER_EEVEE`.
- Native artist capabilities, quality/performance/profile inspection and viewport
  inspection returned retained command IDs. The native viewport HUD draw was
  observed, without fabricating pointer taps.
- Render's own native-window capture produced a verified 1280×960 PNG showing
  Blender Quick Setup. Its SHA-256 was
  `11fc20d0278434f6637e28fff40663168582177bdc7b6bc6a44f21d332be3d0c`.
  ADB screencap was unreliable for this Vulkan surface and is not substituted
  for Render's capture evidence.
- The native modelling fixture saved the original scene as a 97,030-byte BLEND
  checkpoint (SHA-256
  `5f80f1425c9899f5198fde42d36dc9d6f1ad63dc8f7046dd0ff710c62d800629`),
  preserved it and created the separate `WorkspaceCeramicMugTest` scene. Native
  receipts confirm the 1,088-vertex/1,026-polygon hollow mug mesh, subdivision
  modifier, ceramic material and curved handle. The complete modelling phase
  passed: **11 scene objects**, eight materials, coffee, metal/brass base, ground,
  three area lights and camera. The editable 150,581-byte asset checkpoint was
  pulled and independently matched its native SHA-256:
  `ae7afcabc1f1c95f9e3e2c5df1a301317391013b1bb835b2fa6e458ae0fd8374`.
  The original-scene checkpoint was also pulled and hash verified.

The test created a glazed ceramic mug, coffee, metal base, brass accent, matte
ground, three area lights and camera. It explicitly requests a **640×360,
32-sample preview**, preserving separate **1280×720, 128-sample final settings**
in this new test scene. Native receipts confirm enabling persistent render data
did not change quality, and configuring the preview profile did not change the
active scene's quality.

The still preview plan was durably saved as job
`3a608dc18f374cdabb7d88c0b6023757`; Android reported an active media-processing
foreground service, ongoing notification and two actions. Notification permission
was granted as emulator setup. Native EEVEE began frame 1, then Berberis aborted:

```
intrinsics.cc:21: CHECK failed: host_platform::kHasF16C
Fatal signal 6 (SIGABRT)
```

The guest CPU lacks F16C. An isolated, stopped-CPU probe with explicit feature
enforcement confirmed `TCG doesn't support requested feature` for both AVX and
F16C. This workspace cannot fix that requirement by selecting another CPU model.
The retained manifest records **0/1 completed frames**, no frame hash and no movie.
The original native command `2d90d6b9e4a542f08bcc568fe4b8011e` remains claimed
without a completion result. Its request and missing-result check were retained;
it was not replayed. The owned emulator application was explicitly force-stopped
after the native crash and manually reopened for recovery; this is not evidence
of execution after force-stop.

The reopened hub displayed 0/1 verified frames and unavailable/busy native
readiness. A real tap on its Pause control persisted `resume_requested=false`
and `PAUSING_AFTER_FRAME`, preventing automatic render resumption. This verifies
the durable pause intent after interruption, not the completion of an in-flight
frame or 24-hour background endurance.

Recovery started a fresh native process and explicitly restored the mug from its
SHA-bound checkpoint, preserving the default scene. The startup autosave was not
available in this fixture run; this verifies explicit checkpoint recovery, not
automatic restoration of arbitrary unsaved edits. A fixed emulator-only helper
submitted structured native `project.restore` and `viewport.focus` requests using
unique IDs, atomic publication, fresh launch/PID readiness and retained results.
It adds no server or relay and does not test VideoStudio authentication.

Render's own `screenshot.capture`, called on the debug instrumentation worker
through ProductionBridge, captured the restored mug after real touches dismissed
Quick Setup and the bundled splash. The final capture's temporary JSON result was
lost to JDB's `ObjectCollectedException`; the app-owned PNG was retained, pulled
and checked against Android's `sha256sum`. It is an unmodified **1280×960 native
viewport capture**, SHA-256
`d62858ca3801a2c3f0910fcddce8dfcd360cb38ae2b10a88d3a3e0e0464ba866`.
It shows the actual mug, handle, coffee, base and native interrupted-job HUD; it
does not establish final rendered appearance or photorealism.

The native animation phase passed: five rotation-vector keys on `WS_MugTurntable`
at frames **1, 9, 17, 25 and 33**, and separate before/after BLEND checkpoints.
The saved animation checkpoint is 151,918 bytes, native SHA-256
`365e035ab86925c8eaa4b6960875395207b6238865cdc5063ed42e6223b4ae52`.
A second host `llvmpipe_map_memory` assertion terminated the emulator before the
independent pull and halfway-pose check. The latter failed before queuing any
command. Recovery now boots Android only to retrieve the exact saved checkpoint;
no native render is retried. The intended 32-frame/16 fps animation preview and
encoding phases were **not started** after the proven F16C blocker. No movie,
completed PNG render, evaluated halfway pose or visual-realism pass is claimed.

The screenshot also exposed a historical render heading above the correct
interruption message. The final source labels paused/recovery/terminal HUD
headings explicitly. This small UI follow-up is built separately; the native
asset/animation runtime evidence above belongs to the stated earlier source
commit. It is not a runtime pass of the final heading change.

Each operation retains its exact native ID. Mutating phases refuse blind reruns;
uncertain outcomes require inspecting the original command's result first.
The fixture and procedure are documented in
[NATIVE_ARTIST_WORKSPACE_0311.md](NATIVE_ARTIST_WORKSPACE_0311.md).

## Build and host checks

The foundation APK, full native APK and instrumentation compiled. Seven targeted
native assembly checks and two focused Robolectric startup-path checks passed.
The latter use an explicit OS-environment shadow, not a real native Android OS.
The prior 0.31.1 pass recorded 149 Android/JVM tests and 118 Python checks. Those
complete suites were not rerun for the startup-path-only follow-up.

APK signature/SHA-256, ZIP CRC and source packaging were independently checked.
All 146 native libraries and the runtime archive are unchanged from 0.31.1;
17 packaged Python modules exactly match the built source commit.

## Limits and identity

No physical phone was used. Realme P1 Speed/Dimensity 7300 performance, thermals,
output-quality comparisons, uninterrupted 24-hour execution, process-death render
recovery and actual VideoStudio authentication/reconnection remain unverified.
The fixed fixture calls Render's inner ProductionBridge, not a remote VideoStudio
MCP connection. Android restrictions and force-stop behavior still apply.

APK SHA-256:
`ad2695f48b99d1cb76868ce44e5cd60d31662a053106497d88bab74c8d69ecce`.

Certificate SHA-256:
`f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`.

Android accepted the matching historical-signer update in the owned workspace
emulator. The currently installed phone certificate was not queried, so phone
update compatibility is conditional on that certificate matching. No phone
installation, uninstall or data clear occurred. This is a debuggable historical-
signer candidate, not evidence of store-release readiness.
