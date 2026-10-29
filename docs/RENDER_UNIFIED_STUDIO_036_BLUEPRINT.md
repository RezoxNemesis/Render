# Render Studio 0.36 — Unified Native Blender Workspaces

Source: RezoxNemesis/Render, branch upgrade/render-studio-036-unified-workspaces-20261025, draft PR #35.

This describes an implementable native Blender framework, NOT nine proprietary programs being bundled. Full Unreal, ZBrush, Maya, MetaHuman, Houdini, Substance, Cascadeur, or Toon Boom parity is not currently delivered.

## Nine linked workspaces

| Area | Actual native Blender entrypoints in this phase | Next quality milestones |
|---|---|---|
| Sculpt & Anatomy | Sculpt mode, existing sculpt/mesh tools, real viewport orbit and zoom | Anatomical base meshes, high resolution brushes, retopology |
| Characters & Rig | Armatures, weight painting, face shape keys, reference alignment | IK/FK, corrective shapes, face rig and expression presets |
| Animation & Motion | Dope Sheet, Graph Editor, NLA, SHA-revisioned real key/handle edits, pose keys | Contact-aware motion, animation retargeting, intelligent interpolation |
| Cinema & Lighting | Scene cameras, native lights, compositing, checkpointed rendering | HDRI, atmosphere, physically accurate shot lighting and grading |
| Procedural & Physics | Geometry Nodes and physics editors where bundled | Richer fluid, cloth, smoke and procedural simulation |
| Materials & Paint | Native Shader Editor, UV and texture painting, PBR assets | Layered texture work, skin imperfections, baking |
| 2D & Story | Grease Pencil if bundled, camera and 2D timing | Storyboarding, onion-skin and hybrid 2D/3D rigs |
| Assets & References | Original authorized images/videos, native imports, CC0 providers | Extensive indexable offline asset cache |
| Agent & Jobs | Discoverability, real HUD, durable typed work plans, activity and recovery | Visual review loop, dependency scheduling |

These are genuine Blender windows/panels, not claims of installing another software company's binaries. Actual availability varies by bundled Blender version, hardware capability, and loaded add-ons.

## Agent workflow: no old-method guesswork

Use the existing authenticated Render target, not a new unrestricted remote relay.

1. Query studio.capabilities for nine workspaces, Blender version, exact operations, and limits.
2. Query studio.tool.search for available operations and parameter schemas, then use studio.workspace.activate.
3. Use studio.editor.open to open native Graph Editor, NLA, Shader/Geometry Nodes, compositor or image editor.
4. Use studio.view.orbit for actual object-focused viewport rotation, angle and zoom changes. This is a bpy operation, not a synthetic touchscreen click.
5. To edit motion, use studio.curve.inspect for the real key location and SHA revision, then studio.curve.adjust for bounded frame, value, interpolation or handle changes. Stale SHA revisions fail.
6. Submit up to four independent plans through studio.plan.submit, each containing up to 16 typed, allowlisted operations. Query studio.plan.status, studio.plan.list and studio.activity. Android can read sanitized plan progress while Blender is busy rendering a frame.
7. A mid-operation crash or unreceipted mutation becomes needs_review. Never silently rerun an edit on reopening. A plan is resumed automatically only at an already checkpointed step boundary.

For scripting scenes, normal ChatGPT uses reviewed Python modules, typed scripts and existing Blender Python API. The native Text Editor also remains available to the artist. No remote client may send arbitrary Python eval/shell commands.

## Performance and background

- Scene edits execute SERIALIZED on Blender's main thread, one work-plan step per timer tick. This preserves data integrity. Separate plans may wait in parallel, but multiple writers must not edit the same bpy scene simultaneously.
- Download and Android media-processing workers remain distinct, subject to device memory, rendering load, and thermal limits.
- Each step gets an fsynced, atomically moved app-private progress receipt, with source plan fingerprint. Consequential mutations receive native .blend checkpoints.
- The timer reduces idle wakeups: two seconds when idle; three seconds while Blender is rendering; short delay only between actual editor steps.
- A stale saved running label is never treated as proof of active work.
- Android 15+ mediaProcessing foreground-service background budget is generally 6 hours per 24 hours. Force-stop and system termination cannot be overridden by a Blender script. See https://developer.android.com/develop/background-work/services/fgs/timeout

## Verification before any release

Host contract tests: nine accurate workspaces, bounded commands, no arbitrary paths/code, idempotence, fair plans, crash recovery and no blind replay.

Real Blender tests: create a mesh; key two poses with the durable plan; edit an actual F-Curve under a revision token; validate the evaluated animation and checkpoints.

Android tests: authenticated native operations; target identity; out-of-band status during a long render; denial of traversal; no disclosure of private payloads.

Full release build: original ARM64 libblender.so and librender_bridge.so, monotonic version number and unchanged historical signer. No APK installation or main merge without owner acceptance.

Real-device acceptance STILL REQUIRED: genuine mobile viewport display and tab switching, sculpting, camera orbit, editing graph curves, job-status presence, safe recovery after interruption, thermal behavior, and final H.264 MP4 playback.

## Realistic quality boundary

The benchmark goal of photorealistic humans, convincing cloth/fluid effects, natural movement and rich scenes requires significant future work: topology, texturing, IK/FK, advanced animation, simulation, lighting and compositing. This 0.36 phase is the shared foundation to build those capabilities efficiently, not a claim that full proprietary software functionality has already been achieved.
