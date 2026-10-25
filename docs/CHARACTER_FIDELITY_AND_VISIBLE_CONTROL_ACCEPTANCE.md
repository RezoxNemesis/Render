# Render Studio — Character Fidelity & Observable Artist Work

Date: 2026-10-25. This file records the owner's review criteria and is not a
claim of commercial Maya/ZBrush/Houdini/MetaHuman parity.

## Ground truth from current Blender and supplied videos

The user's current Android screen recording (1000072546.mp4) shows the
IslandHeroBenchmark040 scene, but visual editing is not at the intended level:
body parts are simple disconnected volumes, the face/hand anatomy is missing,
the imported turnaround sheet lies flat alongside a tiny figure, and camera
movement / repeated status polling dominate actual mesh changes.

Reference examples:
- 1000072551.mp4: close-up face, body and costume modeling that progressively
  changes the shape, rather than only adding spheres
- 1000072554.mp4: real shader node editing, character assembly and rig work
- 1000072523.mp4: posing, visible rig controls, facial expression animation
- 1000072449.mp4: full workflow from sculpt/blockout to shaded character
  motion, including body, cloth, and deformation

Those videos represent desired artistic processes. They are NOT available
as a 3D mesh inside the Render APK and are not evidence of current parity.

## Mandatory acceptance gate for the Island Hero benchmark

1. REFERENCE: owner-authorized SHA-verified full-resolution source, upright
   front/side comparison in actual Blender Image Editor / 3D scene.
   A 240x180 compressed JPEG alone is NOT enough to validate face likeness.
2. MESH: joined/anatomically continuous editable surface, stable proportions,
   modeled fingers, toes, face geometry and retopology. Blender body.blockout
   is explicitly an early proxy stage. Object shape names do not prove anatomy.
3. FACE: nose, eyelids, eyes, lips, jaw, ears, cheeks and bangs that survive
   real close-up view changes, plus verified eye/head facial expressions.
4. COSTUME: independently identifiable green top, realistic overlapping leaf
   skirt, multiple flowers, bead-and-shell necklace, painted markings.
   Check materials, alpha mode and z-fighting. Do not hide missing costume
   details beneath reference screenshots or background textures.
5. ACTING: real armature deformation and IK/FK, eye look, blink and a small
   acted head turn. Camera-only zoom/rotation is NOT human acting.
6. LIGHTING: real lights and physically reasonable materials / normal maps,
   detailed enough to distinguish pores/cloth/leaf veins where geometry or
   textures actually supply these. Never infer textures from material labels.
7. EVIDENCE: every important native action has a verified object/bone name,
   actual before/after geometry or F-Curve data, a matching checkpoint,
   and a real editor view where one was actually displayed.
8. SMALL BENCHMARK FIRST: 72 independent frames at 24 fps (3 seconds),
   with close-up, bust and full-body motion. Verify native PNG receipts,
   decoded MP4 frame count and model movement. Do not extrapolate from one
   still or queue another minute of weak animation.
9. HUMAN REVIEW: show real front, side, 3/4 and rear comparisons; owner
   confirms identity/realism/motion before long final-quality render.
10. PHONE SAFETY: reuse original Android Binder, current signed Render
    target, checkpointed Blender operations, thermal and storage admission.
    No Gallery browsing, uncontrolled Python execution, new MCP, cloud
    Blender, fictional hand controls or unsafe parallel scene writes.

## Explicit current baseline and honest blockers

Native body creation returned:
- 2,720 base mesh vertices, 2,360 polygons, 12 anatomical volumes
- render_sculpt_union_pending=true
- render_likeness_verified=false
- fingers_face_clothing_rigging_completed=false
- 240x180 JPEG imported to native Assets as a reference, not a 3D reconstruction
- Hair/top/skirt work exists at prototype level, not finished costume detail
- No reviewed 3-second close-up facial-animation MP4 yet

The assistant MUST label this state as BLOCKOUT / NEEDS REVIEW, regardless
of queue success or a saved .blend receipt.

## Integrated corrective controls / tests

- studio.character.qa.inspect: read actual Blender connected mesh shells,
  facial shape key names, armature binding, reference orientation/size,
  transparency and frame occupancy; report factual blockers.
- studio.character.qa.upright: dry-run by default, revision-checked native
  empty-image orientation, restores original and never changes source pixels.
- existing reference.workspace.open / viewport.focus should present a
  useful side-by-side composition, with real UI evidence (not screenshots
  pretending to be a high-quality 3D mesh).

The final visual result is not automatically verified by these structural
tests. Physical Android visual acceptance remains required.

## User-visible autonomy: what success actually looks like

A live work indicator must show actual Blender operation and target, then
actual resulting geometry/bone/timeline change and truthful verified status.
Scene edits must be serialized, high-resolution reference accessible, and
the camera should stay on the face or feature being sculpted. A status list
cycling through "checking command" cannot substitute for modeling.

Distinct stages: queued -> native executed -> structurally verified ->
visually approved. Never collapse them into one "completed" label.
