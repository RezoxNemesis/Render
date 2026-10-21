# Android-only Blender engine port contract

## Definition of done

The app runs locally on ARM64 Android hardware without a server and preserves Blender project content. Every core operation must execute in Android on-device code; Android-specific UI changes are welcome, feature removals are not.

## Truthful starting point

This repository currently contains an Android Activity, Storage Access Framework import, a tiny C++ JNI diagnostic bridge, unit tests, and no integrated Blender renderer. Upstream Blender currently documents builds for Linux/macOS/Windows, not Android. It is not correct to call this a working native Blender app.

## Engine integration phases (not yet completed)

1. Pin an upstream Blender revision and all dependency/license manifests. Establish reproducible ARM64/Android NDK cross-compilation of core utility libraries. Do not replace Blender evaluation with a lookalike implementation.
2. Android window lifecycle/GHOST equivalent, touch/stylus/mouse/keyboard/pen navigation, multiwindow survival, proper GPU/CPU work queues and thermal cancellation.
3. Bring up Blender Main/BKE/DNA/RNA, scene graph/depsgraph and real .blend load-save round-trip. Preserve blend linked-library semantics and versioned file behavior.
4. Bind Blender GPU module to compatible Android Vulkan drivers; port shader compilation, overlays, viewport, EEVEE features and shader graph behavior. Device limitations must be surfaced explicitly, not silently rewritten.
5. Port Cycles CPU execution and investigate Android Vulkan/mobile GPU compute backend where feasible. Preserve integrator algorithms/sample settings/output fidelity; speed may be slower. Desktop CUDA/OptiX/HIP/Metal backends are not available on normal mobile GPUs.
6. Complete Geometry Nodes, modifiers, sculpt, mesh edits, UVs, Grease Pencil, armatures/NLA, simulation, audio/video pipeline, compositing, scripting and extensions. Python and native binary extensions require Android builds and compatible ABI.
7. Package licensed essentials in the install plus optional Drive-synced asset packs. Verify offline reopen/render with a clean disconnected device.
8. Device matrix with actual frames and upstream Blender reference comparisons, performance, power/thermal recovery, crash and project file robustness.

## Hard blockers and risks

- ARM64 Android is not an officially supported Blender build target.
- Android Vulkan drivers differ across devices; equivalent viewport/rendering features will require porting and extensive compatibility work.
- CUDA/OptiX/HIP/Metal GPU paths cannot be advertised on unsupported phones. Cycles CPU may be computationally expensive; identical speed is not promised.
- Phone thermal limits, physical RAM, storage I/O and available graphics extensions place real ceilings on scenes even when the operation set is implemented.
- Some Blender Python add-ons depend on desktop-only native binaries or APIs and need separate Android-compatible builds.

## Release gates

A release cannot claim full Blender equivalence until the feature-parity matrix has passing automated tests and real device recordings/artifacts. Any unavailable feature is marked blocked, not hidden. No cloud operation is an acceptable substitute for local engine parity.
