# Native artist workspace check

This is a fixed integration fixture for `com.rezox.render`, run only in an
isolated, debuggable Android emulator. It calls Render's existing
`ProductionBridge` and typed legacy native actions. It does not add an MCP
server, accept arbitrary Python, or use host/cloud Blender.

The owner authorized native model and animation checks after the initial
engineering-only pass. A compiled fixture, launch acknowledgement or queued
render is not evidence that Blender created a model, rendered a frame or
encoded a movie. Inspect the native receipts and actual output files.

## Sequence

Use the historical-signer application candidate and the workspace test APK
with the **same certificate**. Android rejects a locally signed test runner
against the historical-signer application, including debuggable builds. The
build-only CI workflow emits the fixed runner signed with the pinned historical
identity; no private signing material is exported to the workspace.
Start the Render hub first. Keep the existing application process when invoking
instrumentation with `am instrument -w --no-restart -e phase <phase>
com.rezox.render.test/com.rezox.render.qa.NativeStudioChecks`.

1. `launch`: request editor preparation once. Require a fresh native heartbeat
   bound to the current process and launch before continuing.
2. `diagnostics`: inspect native capabilities, scene, settings and viewport.
3. `artist_model`: checkpoint the original, create a separate ceramic mug scene,
   build the hollow lathed body and curve handle, assign glaze/metal/coffee
   materials, add a base, three area lights and camera, and save a `.blend` copy.
4. `artist_preview`: plan and start one frame using an explicitly selected
   640×360, 32-sample preview profile. Inspect the actual native PNG.
5. `artist_animate`: checkpoint and keyframe the mug group's rotation at frames
   1, 9, 17, 25 and 33, then save the editable animation project.
6. `artist_animation`: start an explicit preview job for frames 1–32 at 16 fps.
7. `artist_status`: repeatable read-only inspection of the exact retained jobs.
8. `artist_encode`: require 32 completed frames; verify Render's Android-native
   encoder/export receipt and resulting MP4. No host encoding is used.

The separate scene's final settings are 1280×720, 128 samples at 16 fps, using
the original scene's engine. Final settings are not silently reduced. The
fixture enables persistent render data explicitly. These settings describe the
requested test; they do not establish visual realism or performance.

Every mutating phase refuses to run again if its app-private validation receipt
already exists. Inspect `files/StudioValidation/029_<phase>.json` and the exact
`native_command_id` using `native.command.status` before deciding how to recover
from a failure. Never blindly rerun an uncertain mutation. Read-only status is
safe to poll. The fixture retains intermediate operation results and native
failure IDs/receipts for this purpose.

Pull only the fixture receipts, native project checkpoint, exact render job
files and scoped captures. Do not browse the Gallery or copy private device
credentials. Preserve each original separately from previews. Compare output
hashes with native receipts and inspect image/video metadata before reporting
completion. Emulator results cannot establish realme P1 Speed thermal,
performance or 24-hour background behavior.
