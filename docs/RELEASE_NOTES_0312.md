# Render Studio 0.31.2 — native startup storage

Adds discoverable `body.blockout` with explicit, validated proportions and native
editable body volumes for a staged character workflow. It checkpoints first and
does not claim a finished sculpt, facial likeness or final render. Reference
images are not bundled. See [native body controls](NATIVE_BODY_BLOCKOUT.md).

Package `com.rezox.render`, versionCode **38**. Retains the 0.31.1 engineering
upgrades, native Blender libraries, project compatibility and render settings.

The retained upgrades include process/launch-bound native readiness, durable
exact-ID Binder results and render queues, completed-frame recovery, foreground
controls/notifications, separate preview/final profiles, Android thermal/memory
gates, native artist operations, the truthful editor HUD, explicit media import
and CC0 asset search/download/import. The existing VideoStudio Binder integration
remains; no additional MCP server or relay was introduced.

Real Android workspace testing exposed an input-dispatch ANR while the native
activity opened its startup log in shared Downloads storage on the UI thread.
Startup log/output storage is now prepared by the existing background loader.
The native activity publishes an already prepared private log path without
probing shared storage. The previous private startup log is retained, and both
current and previous logs are available to diagnostics. Existing explicit
Blender output paths and native output-directory overrides are preserved.

Runtime extraction now buffers archive reads and checks the free-space reserve
at bounded 4 MiB intervals instead of querying storage for every inflater chunk.
Progress updates include bytes during large files and are limited to one update
per two seconds. Archive validation, staging/rollback and the 64 MiB free-space
reserve remain. No scene detail, samples, textures or output quality is reduced.

The native HUD now labels interrupted, paused, completed, cancelled and failed
work explicitly. Workspace captures exposed an interrupted render retaining an
ambiguous historical action heading; the recovery stage and verified frame count
were already correct. This final heading change receives a separate signed build.

The fixed workspace integration fixture creates an editable glazed ceramic mug,
metal base, lighting, keyframes and explicitly selected preview jobs through
Render's native operations. The build workflow emits a matching signed test APK;
a differently signed local runner was correctly rejected by Android.

Validation: Android foundation/full-native compilation, seven focused native
assembly checks, and two targeted Robolectric checks for the UI-thread guard,
retained failure log and preserved output-directory override. The OS environment
calls use an explicit host-test shadow. These checks do not establish native
modelling/rendering success; that requires actual receipts and output files.

The first software-emulator attempt reached Blender's Vulkan device checks.
SwiftShader lacks the geometry-shader feature required by the bundled engine;
the native engine then crashed. Lavapipe passed the geometry-feature check and
reached native Python, a timer heartbeat and the Blender Quick Setup UI. The
emulator later aborted in Mesa's software-GPU memory mapping; a recovery attempt
uses fewer software-GPU workers. That recovery passed native diagnostics and
Render's native-window capture. Native modelling receipts confirm the original
scene checkpoint and complete 11-object mug scene with materials, subdivision,
lights and camera. Its editable BLEND checkpoint was pulled and hash verified.
Native checkpoint restore and five turntable rotation keys also passed; a separate
animation checkpoint was reported saved. After a host-GPU crash and Android
reboot, that recent file and its rollback were **zero bytes**. The earlier mug
checkpoint survived. Successful save callbacks and immediate hashes were not
sufficient evidence of durable storage. Native checkpoint copies, session saves,
recovery backups and BLEND exports now use hidden staging, file fsync, verified
publication by rename and directory fsync before returning a receipt. These
changes still require native interruption validation; no host-power-loss guarantee
is made. The real native viewport screenshot is
included with the workspace evidence.
The still job started EEVEE in an active Android foreground service, then the
emulator's ARM translator aborted on missing F16C. A separate CPU probe confirms
this TCG emulator cannot provide AVX/F16C. No PNG frame or movie completed;
visual realism and final output quality are unverified. See the
[native workspace report](WORKSPACE_TESTING_0312.md) for exact evidence and limits.

No physical-phone installation, realme performance/thermal result, measured
speedup, final-quality comparison or uninterrupted 24-hour operation is claimed.
Android may terminate work; force-stop prevents execution. Pause/cancel takes
effect at a native frame boundary, and resume preserves verified completed frames,
not samples inside an interrupted frame. Catalogs and native import/export
availability remain finite. See [retained engineering limits](V031_RELEASE_NOTES.md).

The APK uses the repository's historical certificate
`f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`.
It is a debuggable candidate. The installed phone certificate was not queried;
in-place phone compatibility requires it to match. Do not uninstall to bypass
a mismatch. The owned emulator accepted the matching signed update.
