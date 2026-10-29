# Render Studio 0.37 — Live Sculpt, Rig Pose and Timeline Controls

This is a reviewable extension of 0.36 native Blender workspaces, authenticated
VideoStudio/Render MCP, F-Curve controls, and durable work-plan queue.
No proprietary ZBrush/Maya/Unreal/Houdini products are bundled.

## Native operations

- studio.sculpt.inspect: query a genuine Blender mesh, its SHA-256 coordinate
  revision, bounds, vertex and polygon counts. Original native Sculpt Mode
  remains available.
- studio.sculpt.brush: object-local XYZ center/direction, radius, bounded
  strength, PUSH/INFLATE/PINCH/SMOOTH, adjustable falloff and optional X mirror.
  Dry run computes predicted affected vertices but does not mutate. Requires
  exact revision token and vertex count, refuses stale/shared/shape-key data,
  caps the typed mobile brush at 250000 vertices and 25000 affected vertices
  by default. The original Blender high-detail sculpt tools are NOT reduced
  by this controlled convenience tool. Each real change receives a native
  BLEND checkpoint; material, UV, topology and quality settings are retained.
- studio.pose.inspect: actual Blender armature, pose-bone Euler values,
  current frame and evaluated 3D head/tail positions.
- studio.pose.key: direct native bone Euler/position keyframe insertion, with
  existing action protection, optional dry run, and frame preview.
- studio.timeline.scrub: sets the actual Blender scene frame, evaluates the
  dependency graph and optionally reports a bone's live world positions.

## Example visible agent workflow

1. studio.capabilities / studio.tool.search for current operations.
2. Activate Sculpt; import an authorized reference; inspect mesh and token.
3. Dry-run bounded brush; apply genuine vertex displacement with a source
   checkpoint; show real targeted mesh in native Blender HUD.
4. Yield to Blender UI. Reinspect mesh revision before another stroke.
5. Switch to Characters / Animation, key a real pose, inspect F-Curves and
   adjust timing with the expected revision token. Scrub actual scene frames.
6. Queue up to four work plans with 16 steps each. bpy scene mutations are
   serialized, never written simultaneously. An unreceipted step after process
   death requires manual review rather than blind replay.
7. Render real PNG masters and verified MP4 with existing Android foreground
   service, subject to OS limits. Android force-stop cannot be bypassed.

## Real verification boundary

Unit contracts, actual desktop Blender mesh/deformation/animation, and Android
authenticated production bridge are covered by CI. The signed APK must retain
com.rezox.render, original pinned ARM64 libblender.so, JNI librender_bridge.so
and historical signing certificate. CI is not proof of on-phone UI playback,
photorealistic acting, high-density full brush performance, IK physics or
render survival across a force-stop. Physical Android testing is needed before
release. Do not uninstall the old app or merge into main prematurely.

Next: native rig gizmos and IK/FK, retopology guidance, synchronized reference
playback, high-poly sculpt batching, per-action real stroke displays and
actual on-phone cinematic acceptance.
