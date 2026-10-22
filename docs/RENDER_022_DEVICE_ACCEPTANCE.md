# Render Studio 0.22 reference-first Android Blender — acceptance handoff

This upgrade adds a **source-guided production workflow** to the existing
`com.rezox.render` app, keeping the exact app identity, VideoStudio MCP v3
carrier, existing native Blender runtime, private scenes, and installed
signing certificate. It is not a prebuilt photoreal model, and code/CI tests
do not prove 90–100% likeness or five-minute film-quality animation.

## Root causes from the failed reference-model attempts

The older character was assembled from disconnected generic primitives
and guessed colors without importing the actual reference image, matching
camera/crop/landmarks, calibrating sculpt geometry, or rendering side-by-side
comparison images. Dense polygons and a smooth-shading modifier cannot
substitute for good anatomical topology, PBR textures, believable hair,
realistic fabric/garment shapes, and iterative likeness evaluation.

Additional failures: reference/video assets could not be received directly
from Android's share sheet; command receipts were mistaken for visible GUI
taps; viewport zoom/clip precision was unknown; no means existed to
quantify 2D landmark projection error; and render.batch treated absolute
frame IDs as relative counts when rendering ranges did not begin at frame 1.

## Implemented and independently testable

- One existing VideoStudio MCP → Binder connection; native
  `production.execute` routes versioned reference, viewport and UI state
  operations with target Render public-ID checks.
- Explicit **owner-selected** photo/video imports through Android's
  `ACTION_SEND`, `ACTION_SEND_MULTIPLE`, or `ACTION_OPEN_DOCUMENT`.
  No Gallery enumeration. Originals copied into SHA-256-addressed app-private
  media, with actual dimensions, orientation metadata, and bounded
  video-frame sampling.
- Packed native Blender reference-image boards with UV crop and source hash,
  camera-background support, and fixed provenance. A photo board is marked
  as reference-only, not treated as a reconstructed 3D person.
- Read-only mesh/UV/material inspection and normalized model-landmark
  projection measurement from an actual Blender camera; the metric is
  **2D normalized RMS**, explicitly not facial identity or photorealism.
- Typed, bounded Blender object operations with inspectable schemas.
  Arbitrary Python/shell, cross-app taps, unrestricted Gallery and filesystem
  operations are not added.
- In-editor hand HUD tracks real native Blender execution stages and
  confirmed edited-object receipts; a separate nonblocking touch marker
  appears only at coordinates of a *real owner touch*. Native data-API calls
  never generate fabricated File-menu taps.
- Viewport inspecting and precision-focused clip near/far settings preserve
  mesh density, original texture data and full render-quality settings.
  Actual mobile GPU jitter reduction remains a physical-device test.
- Resumable native frame rendering supports non-1 start ranges with
  `next_frame > end_frame` as the completion test, plus optional expected
  frame preconditions. A 300-second sequence at 24fps needs 7,200 verified
  frames and practical measured resources; no promise of a guaranteed duration.

## On-phone post-install acceptance

1. Save the currently open user scene; never uninstall either original app.
2. Verify APK package `com.rezox.render`, monotonic versionCode 25, and
   **exact installed certificate SHA-256**
   `f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`.
   If no matching private key is available, **fail the release**. Do not
   generate a new debug signer and claim in-place compatibility.
3. Install as an update. Confirm existing app-private .blend projects, public
   UUID, and VideoStudio 3.5.5 MCP credential still work, with native receipt.
4. Explicitly share an image/video into Render; verify image metadata, no
   Gallery scan, and a native UV-cropped reference board.
5. Check the in-editor hand through a real touch and a confirmed bpy object
   edit. Confirm the HUD does not show invented mouse/menu interactions.
6. Obtain native, user-visible screenshots and reference comparison renders.
   Verify avatar shape, anatomy, cloth, PBR, skin, hair, motion contact, light
   and shot continuity through images, **not object-count success reports**.
7. Compare viewport clip/focus at identical device/scene/zoom; record actual
   jitter, device driver and frame statistics before/after.
8. Create a short true Android-native animation and inspect PNG/MP4 outputs;
   then stress test 7,200-frame recovery, thermals, storage and no data loss.

## Evidence and limits

Continuous unit tests and synthetic Blender fixtures are engineering gates,
not proof of matching the user's image or of photorealistic rendering on
Android. A single frontal image cannot reveal the true back/occluded
surfaces. Automatic full-body photo-to-rigged-human neural reconstruction,
all third-party Blender plugins, arbitrary full-desktop function parity,
guaranteed crash-free 10-million unique models, and arbitrary 5-minute
cinematic quality are **not** supplied by this feature. The human still
needs visually accurate sculpting, source annotations and source-specific
material/rigging work.

Release changes stay in a draft pull request; the current installed Render
0.21 scene is not overwritten, and no extra MCP or cloud GPU is introduced.
