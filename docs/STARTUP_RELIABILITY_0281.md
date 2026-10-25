# 0.28.1 startup diagnostics

The workspace Android tests exposed two launcher defects: opening Android's
all-files Settings screen automatically after starting NativeActivity, and
selecting an older Downloads log ahead of the current app-local startup log.
The native window could remain black without useful visible startup status.

This update keeps the editor foregrounded during normal startup. Broad file
browser access remains available through the explicit **File browser access**
control. App-private work and Android's file picker do not require this grant.
NativeActivity records its chosen log path; diagnostics select that fresh log
and label older logs as historical. Log reads stay bounded to 32 KB and known
startup-log locations. The Blender control surface shows indeterminate startup
progress and elapsed waiting time until a real bpy heartbeat is observed; it
never fabricates a completion percentage. Once the editor responds, a long
render does not make the startup indicator reappear. The hub displays the
installed package version instead of a hard-coded older version.

An interrupted native launch now leaves a durable recovery gate. Android task
restoration pauses instead of repeatedly starting the failed engine. A fresh
owner or authenticated `editor.open` request authorizes one retry; restoring
that same Intent cannot replay the request. A live preparation worker can
continue across Activity recreation. The gate clears only after a real bpy
heartbeat. No project or reference files are removed.

The build adapter produces version `0.28.1-startup-diagnostics`, Android code 31,
with the original package and existing signing configuration. A repeated CMake
configuration also refreshes the exact pinned atomic header before applying
its guarded Android patch; previously a newer generated header caused the
second configure to fail. This does not change allocator algorithms or replace
the full Blender engine. The UI-status tests use the Android Java file API
surface while preserving their progress and symlink assertions.

## Verification

- Six startup-log tests: current versus historical logs, the native-selected
  path, known-path restriction, unavailable candidates and bounded log tails.
- Three runtime-cache seal tests and two native UI-status tests passed.
- Four recovery tests cover process restoration, consumed launch requests,
  explicit retries and preservation of saved project bytes.
- Five packaging tests passed, including the native log-path hook and removal
  of the automatic permission request. Staging against the actual pinned
  upstream Android activity and the complete Android build passed.
- Two consecutive native CMake configurations passed after reproducing the
  generated-header failure.
- The isolated workspace APK signature and package/version were checked, and
  Android acknowledged an in-place update without an uninstall or data reset.
  Its full `libblender.so` remains byte-identical to the pinned upstream engine.
- After an actual native crash, Android restored the launcher into the recovery
  screen and automatic retry stopped. The imported reference image retained its
  original SHA256. This recovery condition was not simulated.

These are build, contract, and isolated Android observations. The workspace has
no KVM or physical GPU. SwiftShader failed Blender's geometry-shader requirement;
Lavapipe passed that GPU requirement. Both tested startup paths then crashed
with SIGSEGV reported through `libndk_translation.so` in this ARM-on-x86 image;
the translated stack does not establish the original guest fault location.
Removing the permission interruption did not resolve that native crash. The
recovery guard passed its separate actual-crash check; editor readiness failed.
The waiting indicator compiled but was not visually confirmed on the native
surface before the crash. These checks do not
establish Realme device performance, phone thermal behavior, character likeness,
or production animation quality.

The workspace test APK has a separate local test certificate. It is not an
install-compatible update for the owner's phone. No private phone credential,
owner media, generated animation or signing secret is included in this change.
