# Render 0.28 native control candidate

This is a source candidate based on
`feature/027-durable-background-render-storage-20261022` at
`646437226fb1248d48bf9c4a189536084e4c8493`. Preparing the existing build adapter
selects version 0.28.0-native-control-reliability, Android versionCode 30.
The package remains `com.rezox.render`; the existing signing configuration and
certificate checks are preserved. No APK has been built, signed, installed, or
tested on the owner's phone during this task.

## Changes

- The primary artist UI runs inside Blender: a `SpaceView3D` POST_PIXEL draw
  handler and the native Blender status bar show the current action, checkpointed
  frame progress and Android-worker pause reasons. A small hand is drawn with
  Blender GPU primitives. After a durable native command result, an arrow may
  point to the actual object's projected position in that viewport. It does not
  invent input events, point to offscreen objects or confirm an unwritten result.
- `viewport.inspect` reports the Blender HUD registration, observed draw state,
  draw errors and recent projected-object coordinates. Actual GPU/BLF drawing on
  the phone remains unverified. Per-sample progress during a blocking native
  frame is not advertised; checkpointed frames and native reported progress
  are kept distinct.
- A `render.batch` CPU wake lock covers an outstanding native frame, rather than
  the whole batch. Thermal cooldown, memory/storage admission and moderate-load
  pacing hold no render wake lock.
- A cancellation received during cooldown returns a paused receipt without
  starting another frame. Two valid cool readings are required after a severe
  reading; an unavailable sensor cannot establish recovery.
- Successful command receipts that report a paused render retain that pause in
  the live status UI. Command journal terminal states remain unchanged.
- The editor's existing hand overlay retains paused/recovery notices, displays
  the native stage and reported percentage, and labels thermal/storage/memory
  waits in plain language. Actual touch coordinates remain separate from native
  API actions; the overlay does not invent or inject pointer gestures.
- A small arrow follows actual touch coordinates, including screen edges.
  Changing/recreating the editor clears coordinates from the previous view.
- A missing battery-temperature field is reported as unavailable, rather than
  being mistaken for a measured temperature of -0.1 C. An actual negative
  temperature remains valid telemetry.

These changes preserve the requested samples, resolution, geometry, frame range
and native engine. They do not establish the cause of the owner's thermal issue.

## Host verification on 2026-10-23

The repository's Java sources and JUnit/Robolectric tests were compiled and run
using JDK 17, Gradle 8.11.1 and the Android 35 `android-all` compile API. A standalone
Java harness was used because this machine has no Android SDK/NDK installation.
This verifies host behavior and compilation, not Android APK assembly or native
Blender execution. Toolchain downloads retained TLS and SHA-256 verification.

- 119 Java tests: passed, none failed or skipped. Includes ten deterministic
  batch scheduling cases, three presence lifecycle cases and two temperature
  telemetry cases added by this change, seven interaction/drawing cases, three
  capability/readiness cases, an Android Canvas pixel test and two Blender
  status-file integration cases.
- 45 existing Python contract tests: passed.
- 36 bridge/assembly/security/preflight/Blender-HUD tests: passed, including
  twelve Blender-side UI logic tests and two native receipt-ordering cases.
- The supported `prepare_production_toolkit.py` entry point ran twice against
  a separate source copy. The second invocation preserved the prepared output.

The scheduling tests use explicitly fake device readings and render receipts.
No test fixture from them is a rendered asset or Android completion evidence.
The pixel test executes Render's own overlay drawing code through Robolectric's
Android Canvas/Skia support. Optional PNG outputs are explicitly labeled host
UI tests; they are not phone captures or Blender renders.
No cloud Blender process, image generator, alternative renderer, Gallery query,
new MCP server or new relay was used.

Repository commands used for Python validation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools -p 'test_*contract.py' -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tools python3 -m unittest \
  tools.test_assemble_full_native tools.test_blender_bpy_bridge \
  tools.test_native_autonomy_security tools.test_blender_batch_assembly -v
```

On a configured Android development machine, the repository's normal Java test
entry point remains preparation followed by `gradle :app:testDebugUnitTest`.
Preparation rewrites build inputs, so use a disposable source copy when keeping
the development checkout unchanged is required.

## Connection blocker and native acceptance

The VideoStudio plugin tools are not exposed to this chat. A standard MCP
initialization request to the current owner-provided endpoint was rejected by
the environment's proxy: `Tunnel connection failed: 403 Forbidden`. It did not
reach the worker. This is not an offline-device finding, an authentication
finding, or evidence that the 3.5.5 carrier lacks production support.

The exact worker hostname was saved as a network-domain addition in the cloud
environment draft. The product requires reviewing/saving those settings and
publishing the environment to activate the configuration. No private endpoint
path, owner credential, or credential value is stored in this document.

A later runtime revision allowed the request to reach the worker's Cloudflare
edge, which returned HTTP 403, Error 1010, `browser_signature_banned`, with
`owner_action_required=true`. Native MCP initialization and app-status checks
remain blocked. The next required action is to allow legitimate access for the
existing MCP client in the worker's Cloudflare access/security configuration, or
make the existing connected VideoStudio plugin tools callable in this session.
No alternate relay or browser-signature bypass was attempted.

Once the existing connection is available:

1. Call `device_status`/`app_status` with the current installation's private
   owner authentication. Discover and use the tool's actual schema. The public
   Render UUID is never a device credential or a carrier deviceId.
2. Queue `projectId=active-native`, `action=autonomous_request`,
   `nativeAction=render.engine.status` with
   `nativeParameters={target_package: 'com.rezox.render'}`. Record that command ID
   and poll its exact native result.
3. Require `target_app=Render Studio`, `target_package=com.rezox.render`, and
   `render_public_id=01dfff8e-368e-4b4a-aedf-e1bec09e5490` in the native receipt.
4. Queue `render.production.execute` with `operation=capabilities`, `payload={}`
   and the same target_package. Poll that exact command ID. Read the returned
   operations and editor readiness before selecting subsequent operations.
5. Include `target_id=01dfff8e-368e-4b4a-aedf-e1bec09e5490` and the same
   target_package in every later production operation. Inspect capabilities,
   the current scene, storage, Android telemetry and editor/UI readiness. Save
   a native checkpoint before changing an existing scene.
6. Import/analyze the supplied reference through supported VideoStudio/Render
   surfaces. Create the character/scene/action in native Blender, inspect and
   checkpoint it, render a preview, inspect the actual result, then render and
   export original data through supported operations. Preserve separate preview
   and original outputs. Never replay an uncertain mutation just to get a reply.
7. Verify physical-device cooling/recovery, cancellation, visible progress,
   `.blend` preservation and exported movie evidence before calling the result
   complete. Confirm installed signing identity before any in-place update;
   never uninstall or clear the existing app to work around a signer mismatch.

No native command IDs, screenshots, rendered frames or animation export were
obtained in this task. The reference video is retained outside the checkout
for later native import; only its container metadata was inspected locally.

## Artist reference benchmarks

`benchmarks/native_artist_references.json` records the original action clip and
the two later references: a swinging character and an organic tree/sculpting
workflow. The actual uploaded videos stay outside the Git checkout. Content
hashes bind the benchmark records to those files.

Visual reference inspection, exact timing/camera comparison, editable geometry
and rig validation, native sculpt operation evidence, Blender HUD visibility,
thermal recovery and original export are native acceptance gates. All three
benchmarks currently have `outcome=not_run`; no similarity or device performance
score is invented. A primitive mesh or BMesh edit cannot satisfy a claim that a
real native sculpt brush executed. Reference filenames define the provisional
task categories, not proof that their contents have already been analyzed.
