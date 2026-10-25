# Render Studio 0.31.2 — native engineering candidate

Package `com.rezox.render`; versionCode **38**;
versionName `0.31.2-native-startup-storage`; ARM64; minimum Android 12/API 31.
Retains the previously committed native Blender, Vulkan, OMEGA, project-storage
and export improvements. No native engine library was replaced.

## Changes

- Native startup separates launch acceptance from a fresh Blender timer heartbeat
  bound to the current process and launch. It reuses a live editor, guards
  overlapping launches, stages runtime upgrades, preserves failure logs and
  reports readiness failures. Real workspace execution exposed a UI-thread
  shared-Downloads log probe; startup storage now prepares on the loader worker.
  Buffered extraction reduces storage queries and bounds progress updates.
- Render intentions, settings, exact command IDs, retained results and verified
  completed frames persist. Foreground notifications and Hub/editor controls
  expose pause, resume, cancellation and recovery. Uncertain mutations require
  polling their original IDs before retry. The existing VideoStudio native Binder
  integration remains, with the private credential separate from the public ID.
- Separate preview/final profiles preserve unspecified artist settings. Persistent
  render data, scene/module reuse, bounded caches and fewer redundant native
  updates avoid unnecessary work without reducing final resolution, samples,
  geometry or textures. No performance gain has been measured.
- Android thermal status and memory govern frame admission. Battery temperature
  is labeled separately from unavailable CPU temperature. Memory reserve and
  frame pacing are configurable; thermal protections remain active.
- Native artist operations cover inspection, modelling, sculpting, materials,
  expressions, rigging, animation, cameras, lights, saving and available exports.
  New `body.blockout` supports validated metre-based proportions for an editable
  first-stage character. It explicitly leaves sculpt union, fingers, facial
  likeness, garments and rigging unfinished. See [body controls](NATIVE_BODY_BLOCKOUT.md).
- The native HUD reports real actions, queue/frame progress, elapsed time and
  calculable frame ETA. Paused/interrupted/terminal states are explicit. The
  unobtrusive pointer reflects actual input/actions and stays outside camera renders.
- Poly Haven/AmbientCG search exposes licensing, formats, previews and sizes.
  Resumable downloads keep originals separate from previews and report available
  integrity checks honestly. Explicit document/share imports handle supported
  images/videos without Gallery enumeration.
- A native crash-recovery check exposed zero-byte checkpoint copies after
  successful save callbacks. Copies now use hidden same-directory staging,
  header/path checks, file fsync, SHA-256, atomic rename and directory fsync.
  BLEND exports/recovery backups share this path; relative asset links and the
  current scene's unit scale are preserved. A later native body checkpoint
  survived one unexpected emulator host-GPU abort with its exact hash intact.

## Build and validation

Final APK source: `8fe278b8917d02d47dcbc660d8cb27ee0854531d`.
Signed [CI build 40080186139](https://github.com/RezoxNemesis/Render/actions/runs/40080186139)
succeeded. Independent signature, package identity, ZIP CRC and source-packaging
checks verified **146 unchanged native libraries** and **18 matching Python modules**.
The runtime archive changed to package the updated Python operations.

The owner subsequently authorized tests, superseding the original request to
skip them. Earlier host suites and focused follow-ups passed. Actual Android
Blender execution created and checkpointed an editable mug, inserted animation
keys and created a separate Stage 1 body blockout. Native viewport captures were
verified. The animation checkpoint failed crash recovery before the save fix.
No camera-render frame or encoded movie completed. Runtime evidence belongs to
the specific earlier builds in the [workspace report](WORKSPACE_TESTING_0312.md);
the final relative-link/unit-scale changes have host checks, not a native rerun.

## Limits and signing

Repeated emulator host software-GPU aborts prevented full character proportion
review and sculpting. The ARM translator also lacks F16C required by the attempted
EEVEE frame. Photorealism, final-quality comparisons, phone performance/thermals,
remote VideoStudio authentication and uninterrupted 24-hour work are unverified.
Android/vendor limits can stop work; explicit force-stop prevents execution.
Pause/cancel acts at native frame boundaries, and interrupted frames restart;
completed verified frames are retained. Catalogs/importers/exporters remain finite.
HDR/32-bit rendering remains available through native Blender, outside the new
durable PNG-job pipeline. See [retained limits](V031_RELEASE_NOTES.md).

APK SHA-256: `9e745320c1c468a6a4f6963b19cb962e24f09ea85fdd3563ced90e38e463ee12`.
Historical certificate SHA-256:
`f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`.
This is a **debuggable candidate**. Matching-signer updates were installed only
in the owned emulator; the final APK was inspected, not installed there.
No phone install, certificate query, uninstall or data clear occurred. An in-place
phone update requires the installed certificate to match; do not uninstall to
bypass a mismatch.
