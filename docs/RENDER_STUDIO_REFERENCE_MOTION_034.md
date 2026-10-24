# Render Studio 0.34.0 — Native Reference + Motion Director

> Source implementation candidate, not a claim of photorealism or Android
> hardware acceptance. The same full native ARM64 Blender core is retained.
> Package: `com.rezox.render`. Version code: `43`.

## Benchmark-driven purpose

Improve the path from a flat Android body blockout to an editable, animated
character shot and a layered cinematic environment. The benchmarks require
better anatomy, topology, UVs/PBR materials, rigging, facial acting, real camera
motion, NLA, atmosphere and compositing. **A single photo cannot prove the
shape of surfaces the camera never sees**. The new tools measure projection
rather than inventing a universal likeness score.

## New native operations (inside the running Blender project)

All commands use the **existing** VideoStudio MCP > authenticated Render target >
`production.execute` > Blender main-thread spool. No arbitrary Python, shell
commands, Gallery enumeration, new agent relay, APK package rename or background
access to private files.

1. `artist.capabilities` now publishes input schemas for the new operations.
2. `reference.workspace.open`: select a SHA-256-named asset already imported
   into the app's Assets folder. `mode:"SPLIT"` attempts a genuine live
   Blender Image Editor beside the still-active 3D viewport. Existing
   reference editor is reused where present. `mode:"REUSE"` requires an
   already-open reference editor; `mode:"CAMERA"` adds non-rendered camera
   reference background. If an Android viewport is too small, native split
   fails explicitly with `VIEWPORT_TOO_SMALL_FOR_SPLIT_USE_CAMERA_MODE`.
   Original still is packed into the editable .blend and not used as final
   rendered geometry.
3. Original MP4 footage is admissible as a reference. If the native Blender
   Image Editor cannot decode MP4, use `preview_asset` with a separately
   sampled, SHA-verified PNG/JPEG/WebP frame. The full MP4 remains in private
   Assets and can also be inserted into the native VSE with existing
   `media.import`. A single sampled frame is **not** video scrubbing.
4. `reference.workspace.inspect`: actual open native editor types, dimensions,
   tracked reference, model and frame; no fabricated visual UI.
5. `reference.compare.multiview`: up to six named scene cameras with
   normalized reference landmark maps and actual mesh vertex indices. Reports
   real Blender camera-projected RMS error and outlier magnitude. Supports
   front/side/three-quarter reference comparisons without swapping the user's
   active camera.
6. `reference.fit.landmarks`: bounded, real vertex adjustments in the active
   mesh. Performs a local numerical camera-projection fit while keeping the
   original camera-depth coordinate and capping each vertex displacement.
   Requires exact vertex count. Use `dry_run:true` first, then perform a
   checkpointed edit. Refuses meshes with shape keys to avoid silently
   corrupting existing facial morph targets. Never changes unseen geometry.
7. `animation.clip.create`: create native rig-bone and facial shape-key
   keyframes from 2–96 ordered poses. Explicit rotation Euler/quaternion,
   location, scale and bounded blendshape values. Configurable
   BEZIER/LINEAR/CONSTANT F-Curve interpolation; optional genuine NLA tracks
   and action strips. Existing active actions must be stashed by the artist
   rather than overwritten. Preserves original frame/timing after changes.
8. `animation.clip.inspect`: report actual active armature action, keyframe
   point count and NLA track/strip ranges.
9. `animation.motion.audit`: evaluate actual armature bone-head world
   positions across 2–128 user-selected frames, reporting displacement path,
   largest per-sample step and restoring the previous scene frame.

### Example multi-angle refinement

The owner imports the original front/side images via the existing Android
system file picker (not Gallery scanning). With a figure mesh and verified
cameras, the agent calls `reference.workspace.open` using the exact source
hash, annotates landmarks, calls `reference.compare.multiview`, and runs
`reference.fit.landmarks` with `dry_run:true`. Apply only if the predicted RMS
falls and the movement budget is anatomically reasonable. **2D RMS never
equals an identity/likeness percentage.**

### Example performance sequence

Model and UV first. Then build a working armature with weighted influences,
create shape keys, and use `animation.clip.create` for eye shift, blink,
head turn and root placement on real frame positions. Sample
`animation.motion.audit` for abrupt jumps; polish curves/NLA. Finally
execute the real native render-to-PNG and MediaCodec MP4 export pipeline.
Never substitute a camera zoom or static slideshow for character movement.

## Verification matrix

- Host contracts reject unknown keys, uncontrolled paths, NaNs, invalid
  rotations, unsafe mesh displacement and conflicting keyframe schedules.
- A Blender bpy fixture creates original synthetic imagery, two real cameras,
  an editable mesh, an armature, face shape keys, interpolated keys, two NLA
  tracks and sampled pose movement; it measures mesh landmark fit in dry-run
  and edit modes. This is not a 3D model matching a person's photograph.
- Android JVM checks verify the native authenticated operation allowlist.
- The ZIP build must contain both new Blender runtime modules and the original
  native libblender.so and librender_bridge.so, without changing the historical
  signer.

## Genuine remaining work

Physical Android dual-view display, native MP4 decoder support, exact
high-detail reference likeness, rig controls/IK/FK, motion-capture retargeting,
hair/cloth simulation and cinematic water/fog/compositor acceptance still need
dedicated device tests. This candidate does **not** deliver a finished
animation of the attached benchmarks. For large renders, Android foreground
service quotas and severe thermal pressure still apply; a force-stopped app
cannot be guaranteed to continue rendering. Do not uninstall or clear data
to test a differently signed APK. Preserve owner reference media outside the
public source repository.

Next milestone: active Android phone screen test — visible split, reference
frame selection, deterministic pose keys, a real 24-frame character turn and
playback-verified MP4 — then benchmark-level asset/rig/lighting upgrades.
