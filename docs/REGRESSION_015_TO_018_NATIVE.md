# Render Studio 0.15 screenshot regressions — no downgrades

This document maps known failures in owner-provided screenshots from old
Render Studio 0.15.0 to native Android acceptance tests. Those screenshots
are historical reports, not evidence that the upgraded APK exhibits them.

| Old failure / misleading state | Updated behavior | Proof required |
|---|---|---|
| `waiting_native` while VideoStudio Native Agent is offline | The existing VideoStudio MCP v3 queue remains the source of pending command state. Render's diagnostics now explicitly distinguishes local Binder queue depth from unknown remote pending work. Do **not** claim Render executed a waiting command. | Real `get_video_command_result` must return a matching Render Studio package and public ID, `ok:true`, native bpy receipt and `native_execution_verified:true`. |
| `create_lively_project` action unavailable on installed APK | `render.agent.capabilities` is now a read-only handshake on upgraded APKs. It reports installed typed actions, editor readiness, and executable-now state, without assuming CI source code is already installed on the phone. If unsupported/old APK, report update required rather than inventing a fallback. | Compare the installed app's `render.engine.status` app version and supported action list against the feature branch build. |
| Default cube/light/camera mistaken for saved building | Separate app-owned project checkpoints with opaque IDs can be restored without deleting previous scenes. `render.blender.scene.visual_audit` reports the active scene's mesh, materials, animation, camera, sunlight and named assets and fails its lively-video readiness gate when missing. | Native scene summary & visual audit on **restored** checkpoint, not on another Blender tab. |
| Hundreds of individual window/cube commands stall and time out | `render.blender.scene.batch_assembly` accepts 1–96 validated primitive parts with positions, scales, colours, roughness, metallic and bevel modifiers as ONE main-thread bpy transaction. It prevalidates everything; its scene-owned collection is rollback-safe after errors. Identical payloads return an idempotent receipt. Conflicting same-name revisions are rejected. | Test real Blender primitives, PBR material nodes, bevels, collision/replay guard and rollbacks. |
| Gray architecture reported as cinematic/complete | Native audit checks material node presence, sun/sky/camera, people/dog/cat, animation, ground and minimum duration. It never equates geometry success to video rendering. | Real rendered frames inspected visually on device plus valid MP4 probe/playback. |
| Rendering command stalls while Android screen sleeps | Partial CPU wake lock has a finite timeout, progress is derived from Blender frame callbacks, and Android work notification shows actual activity. The owner can request Stop. | Device logs + actual native output; thermals, GPU driver and Android lifecycle may still interrupt. |
| Old Blender EEVEE constant incompatible with new engine | Runtime inspection selects supported `BLENDER_EEVEE_NEXT` or `BLENDER_EEVEE`, and scenery is located by a scene-owned version tag, tolerating Blender's `.001` suffix on globally unique data names. | Real Blender engine and multi-scene regression checks. |
| Temporary signing identity silently breaks app upgrades | Production certificate remains owner-held, pinned and checked; debug builds are isolated from production secrets. No automatic uninstall or destructive update. | Compare device-installed signer with protected signed release before attempting upgrade. |

## Anti-downgrade acceptance

- Do not remove upstream native editor tools to fake a mobile-only Blender
  replacement. PBR geometry, materials, animation, rendering, camera and
  existing Blender asset/project functions must remain available.
- Do not run operations in cloud Blender or on VideoStudio's original editing
  projects. Android Binder is the isolated control transport.
- Do not scan the phone Gallery or invoke arbitrary Python/commands.
- A waiting, queued, claimed, or timed-out command is **not success**.
  Report native recovery-required if execution outcome is uncertain.
- Preexisting .blend checkpoints and user-authored scene objects are not
  overwritten by upgrade tests.
- For large native operations, the Android device may still need the Blender
  editor foregrounded and its GPU/driver operational; this cannot be
  overridden by MCP.
- A build artifact proves compilation, not signature compatibility, phone
  installation, practical animation quality or a completed user video.

## Required live-device acceptance sequence

1. `render.engine.status` → confirm target package `com.rezox.render`,
   public ID, installed version, signer certificate, editor bridge readiness.
2. `render.agent.capabilities` → confirm `blender.scene.batch_assembly`,
   `blender.scene.visual_audit`, `blender.scene.populate_lively` and
   `blender.scene.render_video` are installed and whether Blender is currently
   executable; if unavailable, do not queue unsupported tools.
3. With a saved checkpoint, restore and query scene summary/audit; verify
   Blender's actual active scene, not just a pending queue result.
4. Issue a tiny new batch assembly with 3 independent coloured objects and
   inspect each native material in the real Blender scene. Replay the identical
   request and assert no duplicate objects. Send a conflicting revision and
   confirm refusal.
5. Test a deliberately under-detailed gray scene and assert visual audit
   returns `ready_for_lively_video:false` with missing-check codes.
6. Test the enriched scenery and animation with actual rendered frames, native
   Android progress, recovery after accidental tab switch and non-destructive
   project saving.
7. Render to MP4 only after the scene is verified; inspect decoded video,
   resolution, frame rate, content and device-local output hash.
8. Test stopping the direct Binder bridge and resuming VideoStudio MCP
   executor; never fabricate offline completion.

Real on-device completion remains the release gate.
