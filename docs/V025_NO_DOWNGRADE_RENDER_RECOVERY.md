# Render Studio: no silent quality downgrade contract (0.25)

## Goal
Take native desktop Blender-style modeling, sculpting, material, rigging and rendering onto Android. Adapt UI, memory scheduling, thermal handling and recovery **without secretly simplifying the user's project or silently lowering requested output quality**.

This is an engineering acceptance contract, **not** a claim of complete Blender feature parity, GPU/driver parity, or guaranteed rendering on every Android device. If a requested capability cannot execute, fail explicitly, preserve the scene and offer a user-approved alternative. Do not falsify progress or output receipts.

## Evidence from owner recording 1000071980.mp4 (22 October 2026)
- ~0–5s: native Blender viewport and File > Recover > Last Session; error mentions `/data/user/0/com.rezox.render/cache/quit.blend` missing.
- ~8–16s: native Render Result is checkerboard; Blender progress indicator stays at **Rendering… 0%**. This is a live render state, **not evidence of completed blank output**.
- ~18–25s: Blender native editor disappears; the Android Render engine preparation page reappears and Blender initializes with its startup splash.
- ~30–40s: after another render attempt, the Render Result checkerboard appears; the building scene is seen when returning to viewport.
- Without tombstones/Android `ApplicationExitInfo` and GPU logs, the recording **does not prove** whether the cause is driver instability, resource exhaustion, a renderer error, scene settings or user navigation.

### Recover Last Session root cause
Blender's standard `quit.blend` is normally written at an orderly exit. A failed or killed process may not have one. Silently creating a false `quit.blend` would mask the crash and could overwrite later work. Render instead has an explicitly named app-owned checked snapshot, SHA-256 receipts, separately verified previous good snapshot and a confirmation step with rollback copy before replacing active edits.

## Implemented v0.25 engineering
- **Native engine retained:** pinned full Blender Android build, no switch to lite or replacement image generator.
- **No hidden sample cap:** removed 4,096 Cycles sample clamp and unsupported EEVEE fallback to guessed 64. Strictly preserve configured engine, dimensions and user-selected sample count; unsupported sample controls fail explicitly.
- **Protected single-frame PNG:** Blender File/Render and Android overlay command creates an immutable `.blend` snapshot, renders one requested full-resolution frame through the same native production worker, then verifies SHA of the PNG. No one-frame MP4 overhead. Animated scenes still use existing PNG masters and Android H.264 encoder.
- **Crash evidence:** real bpy `render_init`, `render_complete`, `render_cancel` journal callbacks; Android `ApplicationExitInfo` from same package for recent native crash, ANR or low-memory exit reasons when available. A started event without a completion event is marked **unconfirmed**, not "GPU crash proven."
- **App-owned project continuity:** previous snapshot now receives a separate SHA receipt; failed/corrupt latest cannot silently override it. Explicit recovery creates its own pre-recovery backup of the currently open scene.
- **Live work transparency:** thermal/user paused native render state distinct from unconfirmed crash; progress measures committed frames, not speculative partial pixels.
- **Release hygiene:** original `com.rezox.render` package, versionCode 27, unchanged installed signing identity verified during protected build. No uninstall, automatic merge or loss of existing user data.

## Not yet proven / still required
1. On-device root-cause diagnosis of the exact recorded F12 failure, using exit reason/tombstone plus GPU and app logs.
2. Five-minute sustained native render (both Eevee and Cycles if supported), including thermal ramp and resume after a deliberate process kill.
3. Real image integrity: dimensions, actual PNG content, camera/lighting/material fidelity and expected desktop-vs-Android reference measurements.
4. Variable frame rate and exact fractional FPS metadata parity across the Android H.264 encoder.
5. Full rigging and deformer animation, procedural fluid/simulation, all desktop add-ons, and support for extremely large scenes that exceed memory.
6. Image texture and geometry streaming/out-of-core caches for very large scenes; existing Render engine remains constrained by device memory and driver features.
7. Safe, stable update from the currently installed original APK with exact signing certificate and preserved app-private projects/Render public identity.

## Acceptance gates
- All Python contract tests and real Blender bpy fixtures pass; Android Java/Robolectric tests pass.
- Full native APK bundles `render_v25_recovery.py` and native protected still route with `versionCode 27` and original certificate.
- Device test of File > Recover > Render Studio, user-confirmed overwrite, corrupt latest fallback, and Android background/foreground resume.
- Zero invisible reductions to geometry, textures, samples or requested final output dimensions.
- Before claiming video/render reliability, inspect generated PNG and H.264 frames, native exit reason and reported thermal state on the actual supported device.

See PR #8 on branch `feature/025-no-downgrade-render-recovery-20261022` stacked over #7.
