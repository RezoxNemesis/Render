# Render Studio 0.40.0 — Phase 1: Pixel and Viewport Fidelity

**Status:** source/CI development, draft PR #43. The aim is to repair
unreadable, noisy Blender **viewport preview** while retaining the complete
original native Blender engine, scene, materials and final render quality.
This phase does not claim to reconstruct missing anatomical polygons, replace
proprietary ZBrush/Maya, or fix the native Android GPU driver.

## The defects shown in the owner screenshots

The actor/vehicle viewport captures show small models, blocky patchy
surfaces, heavy visual clutter/overlays and limited facial detail. They are
valid evidence of unacceptable preview readability, but screenshots alone
cannot tell whether the root cause is:

- *coplanar/z-fighting geometry*: duplicated object, identical/overlapping
  mesh objects, actual intersecting polygons;
- *alpha/transparent materials*: blended/hashed Eevee material preview,
  missing texture, partial transparency or GPU dither/temporal ghosting;
- *view depth precision*: far/near plane ratio too large for scene scale,
  very distant object view, x-ray/wireframe overlay;
- *actual asset quality*: low texture resolution, smooth shading off,
  low mesh density, incorrect real anatomy or material topology;
- *mobile GPU/driver issues*: missing Vulkan features, alpha/temporal
  reprojection, power/thermal throttling. Actual GPU profiling is required.

**No single anti-aliasing slider corrects each possible cause.** In
particular, disabling shadows/overlays can make an unstable object more
legible but DOES NOT delete doubled faces or create new skin textures.

## Implemented native Blender commands (discoverable by normal ChatGPT)

Use the existing authenticated Render production.execute with the known
Render target ID. The built-in studio.agent.bootstrap and studio.tool.search
return these exact typed native operations, not remembered old commands:

| Operation | Real behavior |
|---|---|
| studio.preview.capabilities | Query current Blender version, actual GPU backend if supported, available profiles and native viewport count |
| studio.preview.inspect | Read actual VIEW_3D display/overlay/clipping fields and SHA revision; reports no viewport in headless Blender instead of making up a visual result |
| studio.preview.diagnose | Inspect actual selected mesh, alpha/blend material, texture pixel size and image loading, nonuniform/negative scale, first-sampled duplicate geometry and viewport object size/depth range |
| studio.preview.profile.apply | Apply one **reversible** single-view fidelity profile; optional expected state SHA blocks stale overwrites. Does not change geometry, scene camera, final rendering samples or color grading |
| studio.preview.profile.restore | Restore original per-view shading/overlays/clipping from this Blender window's in-memory snapshot |
| studio.preview.aa.inspect | Read only real supported native viewport anti-aliasing values; does not silently change them |
| studio.preview.aa.configure | Explicit owner permission required for GLOBAL viewport-AA preference change; checks real enum values and supports restore |

### Profiles

- CLEAN_SOLID: native studio-lit SOLID shading, material color, shadows on,
  no x-ray or wire overlay. Priority: clean silhouette.
- DETAIL_INSPECT: real Blender solid studio shading with geometry cavity,
  shadow and curve ridge/valley cues; useful for face topology and microform
  when the mesh already contains them. Does not add geometry.
- LOW_NOISE: temporarily turns down expensive solid preview shadow/cavity
  effects without changing final render settings. This is NOT a temporal
  denoiser or a GPU-driver repair.
- SURFACE_DEBUG: solid shading with wire-overlay to detect coincident faces,
  actual mesh topology and weird normals; not a cinematic view.
- MATERIAL_REVIEW: actual material preview selected EXPLICITLY by the owner.
  Shader compilation/thermal load is never enabled silently. No hidden
  texture quality reduction.

### Precision and stability

When an exact object is supplied with precision_target_clipping:true, the
native viewer applies a near/far span scaled to that object's world bounds,
improving local depth precision. Since this can hide other objects outside
the range, the result reports that warning. It never changes the camera
render clip or world scale. Calling restore returns original settings.

The OLD legacy menu action blender.ui.stabilize_viewport no longer forces
a global highest anti-alias preference and no longer clips every scene to
2000m. It uses the reversible CLEAN_SOLID profile and actual diagnostic
evidence instead, maintaining its legacy response fields for compatibility.

### Genuine Blender artist controls

A separate Render Studio > Viewport Fidelity / Phase 1 panel in Blender's
3D View sidebar lets the owner choose a preset, explicitly approve costly
material preview, apply, restore and scan the selected object. These buttons
call the SAME bpy operations exposed to ChatGPT. Status text is derived
from actual scanned Blender data, not a fake hand or screen animation.

The underlying full Blender API remains intact and existing workspaces,
job checkpoints, native sculpt/IK tooling, reference VSE, asset discovery
and VideoStudio Render bridge are retained.

## Verification gates

1. Host contracts reject malicious Python/path parameters, unsupported
   profiles, stale SHA revisions and nonfinite values. Programmatic native
   dispatch and Android authenticated allowlist match exactly.
2. Actual headless Blender creates TWO coplanar meshes, an alpha material
   and 128px texture; inspect detects concrete risk conditions without
   deleting geometry or lowering quality. Background bpy must report that
   it has **no true drawn viewport**.
3. Actual windowed Blender (Xvfb + real Blender) registers the sidebar,
   changes genuine VIEW_3D shading, disables x-ray, displays wire
   diagnostics, enforces revision conflicts, tunes selected depth and
   restores exactly the prior settings, including far/near and AA unchanged.
4. Android JVM/JNI passes, full original Blender + VideoStudio agent
   components are staged into the same package com.rezox.render with
   increased monotonic versionCode 49 and original historical signer.
5. A physical owner's Android device acceptance remains essential:
   compare identical project/viewport screenshots before and after,
   inspect actual color/material/texture and face closeups,
   rotate/zoom smoothly for the following Phase 2, record thermal/GPU
   stability and validate final animation MP4 export. No CI desktop
   screenshot is adequate proof that mobile Vulkan tearing has been fixed.

**Phase 2 is intentionally separate:** character/face/hand/car focus,
human-like real-time turnaround and fixed-angle comparison. Phase 3 covers
visible human operator navigation and status; Phase 4 strengthens actual
Blender-native Maya/ZBrush/Houdini/Substance/Unreal/finishing workflows.
No premature claim that these later phases have been completed.

Source rationale:
- https://docs.blender.org/api/4.5/bpy.types.SpaceView3D.html
- https://docs.blender.org/manual/en/5.3/render/eevee/render_settings/sampling.html
  (TAA can leave ghosting; more samples cost throughput, not a guarantee
  against overlapping geometry).
