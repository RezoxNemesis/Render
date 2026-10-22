# Render 0.22 Reference and Visual Control Implementation Plan

**Goal:** Improve the existing Android Blender/VideoStudio bridge through a reference-first authoring loop, truthful in-editor feedback, direct reference-media intake, readable scene geometry, and reliable exact-frame rendering.

**Architecture:** Keep com.rezox.render, its private project storage/public UUID and the existing VideoStudio MCP v3 carrier. Add typed operations behind production.execute; preserve Blender's original native engine and all existing operations. Native actions report actual receipts; visuals and similarity are separate acceptance gates.

**Tech stack:** Android Java 17, native Blender bpy, existing app-private spool, Android DocumentsProvider and sharing intents, PixelCopy, MediaMetadataRetriever, existing H264 encoder.

## Agreed user constraints
- Update the existing original app in-place, without uninstall, credential reset, new relay, Gallery enumeration or cloud Blender execution.
- Preserve the installed F3:D6:3F:B2 development signer and increase versionCode from 24 to 25; fail the build if signer is unavailable.
- Do not substitute a generated 2D image for an editable 3D model, or count objects/vertices as proof of resemblance.
- Preserve requested render dimensions, samples and texture fidelity. Keep owner Stop, target checks and Android thermal protection.
- Image/video similarity must be evaluated on actual native renders; no fabricated 90–100% metric.

## Root causes and acceptance targets
1. Previous portraits used guessed primitive assembly without importing the photograph, UV textures or iterative rendered likeness review. A new source workflow must preserve imported bytes, crop/aspect/orientation, support image boards and source metadata, and expose polygon/UV data for informed edits.
2. Several functions exist but are undiscoverable or incompletely described. Add operation schema discovery and an explicit read-only connection diagnosis instead of treating unsupported commands as offline devices.
3. The hand indicator exists in the agent console, not the Blender work area. Add an in-editor overlay tied to actual command/activity data and confirmed selection location; distinguish API operations from pointer input. Never animate pretend clicks.
4. Viewport jitter may come from overlapping geometry, unsuitable clipping ranges, or screen/surface scaling. Add measurable viewport/scene diagnostics, precise clip configuration and selection focus. Do not claim a driver fix without device evidence.
5. Render batch incorrectly compares an absolute next_frame to a relative frame_count when start != 1. Fix against the explicit end frame and test nonzero ranges. Add optimistic exact-frame preconditions and integrity/recovery checks.

## Implementation tasks
- [ ] Tests first: source/crop validation, finite normalized coordinates, exact frame-range progression, checksum failures, truthful capability flags.
- [ ] Direct reference inbox: explicit Android share/open-document input only; copy to app-owned content-addressed storage, validate image/video, expose metadata/list and native sampled video reference frames. No arbitrary path or network import.
- [ ] Native reference tools: image-board placement with crop/UV data, camera-background reference, geometry read and selected-object focus, surface/normals audits, explicitly supported modifier controls.
- [ ] Live feedback: weak-reference Activity overlay, actual command state/progress and confirmed projected selections; screenshots remain of Render's own visible window. Real pointer input must be gated by actual runtime support and never faked.
- [ ] Render reliability: exact end_frame, expected next-frame guard, deterministic recovery of stored hashes, bounded caching that cannot reuse a stale snapshot.
- [ ] Integration: exact-source build adapter, actual APK runtime scripts and manifest share Activity, unchanged native engine, same-signer version 0.22.0/build25.
- [ ] Run Python regression tests, real bpy fixture tests and Android unit/build checks; inspect signature/manifest and provide only a successful build.

## Evidence boundaries
Desktop Blender in CI is only a synthetic compatibility fixture, never the user's production renderer. Source and tests are not proof of phone screenshot/touch/codec/GPU behavior. Five minutes at 24fps requires 7,200 verified frames, with actual measured timing and memory, shot continuity, audio and animation quality assessed separately. Automatic neural single-image reconstruction, unconstrained full desktop parity and arbitrary operator execution are not silently implied by reference import. Unseen back/feet from a single photograph remain inferred, not exact observed facts.

## Review focus
Keep app signing/UUID stable; do not restart the active user scene. Handle malformed, enormous, rotated or mislabelled media without OOM. Preserve aspect ratio and avoid touching unrelated media. Invalidate stale viewport-coordinate hints on layout changes. Report native pause/failure honestly and prevent replaying uncertain mutations.
