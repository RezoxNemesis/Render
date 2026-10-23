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

On 2026-10-23, the prepared production source passed 136 Android/JVM unit tests
and 100 Python contract tests. Both Android application builds and the plain
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
`render` and read-only `status` phases through the app's actual ProductionBridge.
Core/assets/render receipts are guarded against blind replay. Native feature,
asset-network and screen-off render acceptance results will be recorded after
those phases finish. A successful shell command alone is not a native pass.

The clean workspace candidate is 302,116,716 bytes, SHA-256
`ac6165d1a4917772810cfde25a157d28f2c8f2d70510b9913fcdbed98d646002`.
All non-signature ZIP payloads match the installed candidate byte for byte;
the installed incremental APK contained unused ZIP padding removed by a clean
build. The candidate uses a separate workspace test signer. It is not an
owner-phone in-place update, and no phone installation is claimed.

The owner's existing VideoStudio endpoint previously returned an explicit
Cloudflare 403/1010 access denial. No bypass was attempted. Existing private
installation authentication and a compatible owner signing identity are still
required for phone connection/deployment. Public Render IDs are not credentials.
