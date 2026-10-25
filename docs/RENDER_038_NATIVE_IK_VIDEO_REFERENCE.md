# Render Studio 0.38.0 — Native IK/FK and synchronized reference footage

**Package:** com.rezox.render | **Android versionCode:** 47 |
**Engine:** unchanged original ARM64 native Blender runtime.
**Status:** signed-development candidate, draft feature PR #39. No main merge or
physical Android installation is implied.

## What is genuinely new

### Native character acting controls

- studio.ik.create adds a REAL Blender PoseBone IK constraint, target Empty
  parented to the current armature and an optional separately editable pole
  Empty. It checks bone ancestry, chain length (2–8), unique names and
  conflicts with pre-existing constraints, and retains the original FK pose
  values. A dry run makes no changes. Visible Blender objects can be selected
  and adjusted locally by the user as well as through the authenticated agent.
- studio.ik.inspect evaluates the actual Blender armature at a chosen frame,
  reading effector world-space tail, controller world position, chain count,
  target error, IK influence and a SHA-256 revision containing source action
  keys. It restores the user's prior scene frame.
- studio.ik.target accepts an inspected SHA revision and real WORLD-SPACE 3D
  controller target. It inserts actual Blender location keyframes at a
  specified time; existing controller actions cannot be changed without
  an explicit allow_existing_action flag. Dry run reports local target but
  does not key anything.
- studio.ik.blend animates Blender Constraint.influence between 0 (FK),
  1 (IK), or any supported intermediate blend. It protects an existing rig
  action and keys the real constraint channel.
- Existing studio.pose.key and studio.curve.adjust are used to shape FK poses
  and refine their native Graph Editor motion curves after adding IK.
  This is standard Blender solver behavior, not a claim of physics-informed
  Cascadeur motion or MetaHuman-grade facial performance.

### Owner-imported video reference workflow

- studio.reference.timeline.bind accepts only a SHA-256 verified MP4 already
  authorized and imported into Render's PRIVATE Assets folder. It creates or
  reuses a REAL Blender movie strip in the native Video Sequencer. The
  original MP4 remains untouched; no Gallery browsing or arbitrary
  filesystem path is permitted.
- If the phone supports movie preview, Blender's Image Editor can show the
  original film beside the 3D viewport. Otherwise the existing
  reference.video_frame Android operation can extract a SHA-verified sampled
  still and studio.reference.timeline.bind can show that native reference
  still through preview_asset. A sampled still is NOT moving video.
- studio.reference.timeline.inspect lists only verified owner-owned video
  strips, channel and Blender timeline ranges, never unknown external paths.
- studio.reference.timeline.scrub advances the actual native scene frame,
  coordinates the original movie strip timeline and the posed character,
  optionally updates the reference still in an active Image Editor, and
  clearly reports that pixel-level MP4 decoding was NOT independently verified.
- Scene FPS, render samples, Blender engine, original meshes and animation
  keys are never silently altered by these reference tools. If a source
  video has a different frame rate than the scene, the native VSE mapping
  needs a separate artistic timing review.

## Reliable ordinary ChatGPT procedure

1. Query the existing authenticated Render target using studio.capabilities
   and studio.tool.search ("ik", "reference", "curve"). These return exact
   tools and input JSON schemas; never guess old commands.
2. Inspect the source armature and mesh; choose two or more correct parented
   bones. Create the IK controller with studio.ik.create.
3. Inspect its per-frame SHA with studio.ik.inspect, then move the controller
   with studio.ik.target and updated SHA at each requested frame. A stale
   SHA fails before moving the artist's rig.
4. Change from IK to FK and back by using studio.ik.blend with a verified
   SHA, then pose the bones using studio.pose.key. Inspect final Graph
   Editor F-Curves before changing handles or easing.
5. Import the owner's chosen MP4 via Android's system file picker, not
   Gallery enumeration. Use studio.reference.timeline.bind to create a
   native sequencer guide, alongside the 3D work area when actually supported.
6. Scrub the movie/3D timeline with studio.reference.timeline.scrub,
   comparing key poses to the actual reference. Use the current source asset
   hash or a verified sampled still rather than an unbounded URL.
7. Save editable .blend checkpoints and render genuine PNG frames to
   the existing resumable MP4 encoder. Do not substitute slideshow zooms,
   unverified output or pretend a timed effect is a character deformation.

## Tests and limits

- Host contracts: strict names, world vectors, camera/pose/key ranges,
  honest tool discovery and package determinism.
- Genuine desktop Blender: two-bone IK target actually moves a limb,
  real target action keyframes, real animated constraint influence,
  FK pose and IK reactivation, stale revision refusal, native checkpoints.
- Actual Blender VSE: synthetic original SHA-verified movie imports,
  follows the source scene timeline, owner path is checked, sampled
  image is packed as Blender camera reference. Separate windowed
  Blender UI test proves an Image Editor appears beside an editable
  VIEW_3D area while original film remains in VSE.
- Android JVM: authenticated native command allowlist and package build.
- Historical signed APK: keep native libblender.so, librender_bridge.so,
  com.rezox.render, original signing certificate and monotonic version 47.

**Not yet verified:** actual user's Android viewport/touch behavior,
native H.264 frame decoding/side-by-side performance on the device,
facial mocap, realistic muscle deformation, real-time IK on very complex
characters, simulation realism, long 10GB output, or continuation after
Android force-stop. Those require physical-device testing with captured
screenshots and a playback-verified film before any main merge.

**Next:** a humanoid rig preset with IK/FK arms/legs and constraints, pose
library/contact management, realistic corrective facial shapes, and
continuous reference-guided acting review. Mobile hardware limits will be
managed with device-native performance profiles and optional external GPU
rendering only when expressly supported and selected.
