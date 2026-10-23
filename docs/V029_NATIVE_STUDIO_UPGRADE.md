# Render 0.29.0 native studio candidate

Version `0.29.0-native-studio-upgrade` / Android code 35 improves the existing
Android Render application and its native Blender runtime. The character film
is paused at the user's request. These engineering checks are not a film,
character-likeness test, phone performance benchmark or 24-hour endurance pass.

## Rendering and background work

An individual production frame now has a six-hour native completion budget.
The batch admission window remains bounded separately. Pausing a frame that
Blender already claimed waits for its actual result before releasing the render
wake lock. Completed frame receipts remain available for exact-command-ID
inspection through `native.command.status`; an uncertain outcome is never
automatically replayed. Frame PNGs, frozen scene checkpoints and existing
integrity/reconciliation checks remain the recovery boundary.

`render.job.start` remains the asynchronous Android foreground-service entry
point. Job ownership checks prevent a new request from replacing another
pending/running job. Opted-in agent work can request an Android service restart;
owner disablement, force-stop and Android background restrictions still apply.
Status exposes battery optimization, interactive-screen and power-save state.

Quality controls and throughput controls are separate. Native Blender's new
Rendering panel exposes engine, dimensions, output scale and samples, plus
persistent render-data caching and CPU thread controls. Caching can improve
multi-frame throughput at the cost of retained memory. It does not promise a
measured speedup. Typed performance configuration cannot change quality fields.
Render plans preserve omitted artist settings instead of substituting default
samples, engine or dimensions. Requested settings are validated and native RNA
clamping rolls back the change.

Thermal and memory admission continue to use observed Android readings. No
sensor is bypassed and no geometry, sample count or resolution is silently
reduced. The blocking per-frame native render cannot provide verified
sample-level progress or mid-frame thermal interruption through this bridge.
Android 15 media-processing quotas, force-stop and manufacturer power policies
mean uninterrupted 24-hour operation is not guaranteed. The engine is still
owned by NativeActivity; activity-independent lifetime needs device validation.

## Native artist workflow

The Blender sidebar gains an Assets panel with explicit public Poly Haven CC0
search for models, materials and HDRIs, verified resumable downloads, progress,
pause and native import. This is a finite public catalog. The user selects
resolution; unavailable resolutions fail explicitly rather than substituting a
smaller asset. Original provider files and license provenance are preserved.
TLS verification, allowed HTTPS hosts, provider sizes/digests, local SHA-256,
dependency path checks and storage reserve checks remain enabled.

Models become editable native Blender collections. HDRIs remain original HDR
data. Imported images are packed for portable checkpoints. A native file picker
can load full-resolution images supported by Blender as reference objects; it
does not claim an image is reconstructed 3D geometry. No Gallery query is used.

The reviewed operator surface adds transform application, modifier
application/removal, subdivision, normal recalculation, merge by distance and
smart UV projection. Modifier validation now happens before creation, so an
invalid subdivision request leaves no unwanted modifier. Blender's own UI
remains available; the typed MCP surface does not expose arbitrary Python.

The app-private Java-to-Python launch handoff is published before companion
menus and the artist HUD are imported. Readiness now requires a fresh heartbeat
written by Blender's real timer with the current Android process ID. Old
process heartbeats cannot establish readiness. A long frame refreshes this
heartbeat before publishing its final result, avoiding a stale-heartbeat race
on the next frame.

## Existing VideoStudio transport

The existing authenticated Binder/MCP path remains in use. Network failures use
bounded exponential jitter and numeric `Retry-After`, independently of command
IDs and durable receipts. This does not replay mutations. Recovery responses
include the exact native command ID when available. Typed reference uploads
validate and index image/video metadata; image and video limits are distinct.
No additional MCP, relay or cloud renderer is introduced.

## Validation boundary

On 2026-10-23, initial production source passed 136 Android/JVM unit tests
and 100 Python contract tests. The follow-up fixes passed 141 Android/JVM tests
and 117 Python checks, including the Blender HUD tests and runtime packaging
seal tests. Both Android application builds and the plain
instrumentation APK built successfully. These host tests use explicit doubles
where appropriate and do not establish native scene or render completion.

The full 0.29.0 APK was installed on the isolated Android 35 workspace emulator.
Actual native Blender emitted its timer heartbeat and displayed the viewport.
The guarded Vulkan counter dispatch correction from 0.28.3 is retained, with
its exact original/corrected hashes and source-equivalent diff in the APK. It
is not a full engine source rebuild. The emulator uses software GPU and ARM64
translation without KVM; its speed and thermal behavior do not represent the
owner's Dimensity 7300 phone.

`NativeStudioChecks` provides fixed debug-emulator-only `core`, `assets`,
`render`, `launch`, `configuration` and read-only `status` phases through the app's actual ProductionBridge.
Core/assets/render receipts are guarded against blind replay. The actual native
core phase passed: checkpointing, quality preservation during a performance
change, subdivision, normals, UV projection, invalid-modifier rejection without
mutation, modifier application, transform application, original PNG import and
metadata, viewport capture and the final checkpoint. The applied mesh has 98
vertices / 96 faces. The in-Blender HUD reports an observed viewport draw with
no draw error. See the [sanitized Android receipt](../benchmarks/native-studio-029/core-android-result.json)
and [actual Android capture](../benchmarks/native-studio-029/core-android-viewport.png).
An initial readiness-only failure was inspected and preserved before this run;
no scene operation existed to replay.

Two additional findings drove a follow-up candidate. A read-only asset poll
was rejected while a slow software-GPU redraw postponed the heartbeat; it had
only returned a loading catalog, with no download/import request. Read-only
asset search/status can now wait in the queue after the same native process has
genuinely initialized. Mutations still require fresh readiness, and queued work
never counts as native completion. The captured HUD also exposed toolbar
occlusion; its layout now reserves the toolbar/sidebar width.

A later Android resource-configuration event (`CONFIG_ASSETS_PATHS`) destroyed
and recreated NativeActivity in the same process, followed by a Vulkan driver
crash. This occurred before the render test's `onStart`: there was no render
test receipt, render-job preference or job directory, so no render was queued.
The follow-up manifest preserves the original configuration flags plus that
event through `@integer/render_native_config_changes`. The normal native
configuration callback keeps the existing Blender context. A launch UUID and
observed configuration callback count support a fixed emulator-only acceptance
phase that requires the same activity identity and a fresh actual viewport
after `am update-appinfo`. Android PackageManager resolved the installed flag in
the actual launch-phase receipt. Callback/viewport acceptance is still pending.

Normal extraction during that launch exposed another upgrade failure: the new
runtime was sealed and activated, but deletion of the obsolete backup failed.
Its Python executable shortcut pointed into the previous APK directory, already
removed by Android. `File.exists()` followed that dangling shortcut and skipped
it, leaving the parent directory non-empty. Cleanup now unlinks symbolic links
before testing existence, without following their targets. Tests cover the
actual dangling-APK-link case, preservation of a linked production directory and
a missing/dangling root. Once a valid new runtime is active, an obsolete backup
cleanup error is recorded and retried on a later sealed reuse; it no longer
blocks launching that valid runtime. No production project is removed.

Native checkpoints also exposed a thumbnail-cache write to unwritable
`/data/.cache`. Validated Android startup now supplies a private
`XDG_CACHE_HOME`, preserving explicit overrides and leaving `HOME` unchanged.
Asset-network, resource-change and screen-off render acceptance remain pending.
A successful shell command alone is not a native pass.

The original clean workspace candidate was 302,116,716 bytes, SHA-256
`ac6165d1a4917772810cfde25a157d28f2c8f2d70510b9913fcdbed98d646002`.
Its payloads matched the installed baseline candidate after removing unused ZIP
padding from the incremental build. The follow-up cleanup candidate is
302,119,988 bytes, SHA-256
`7602172eb8b10960f0be1e99f2f145a5054c170c98f0e5db820d2ecfb13eabec`.
Its runtime ZIP is
`dcfc5e46efc1456d0e14d4fe5e01769f4285b0ddaf69b7b1d9b710802bb50991`;
the corrected native engine remains unchanged. Both full app/test APK builds
passed. The candidate uses a separate workspace test signer. It is not an
owner-phone in-place update, and no phone installation is claimed.

The owner's existing VideoStudio endpoint previously returned an explicit
Cloudflare 403/1010 access denial. No bypass was attempted. Existing private
installation authentication and a compatible owner signing identity are still
required for phone connection/deployment. Public Render IDs are not credentials.
