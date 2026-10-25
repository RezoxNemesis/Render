# Render Studio v0.24: resumable editor and honest animation production

## Source and compatibility
- Branch: `feature/024-resumable-render-continuity-assets-20261022`; preserve prior native Blender and VideoStudio MCP integration.
- Original Android package remains `com.rezox.render`; staged APK version is `versionCode 26`, newer than 0.22 `versionCode 25`. **Never uninstall or clear app data.**
- CI checks certificate SHA-256 `f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30` before advertising the original in-place install candidate. A build alone does not prove the device supports sustained film rendering.
- No arbitrary Python execution, universal filesystem access, secret export, Gallery enumeration, or silent cloud rendering. Typed `production.execute` operations and user-granted Storage Access Framework backup remain the boundaries.

## Native UI implemented
- Blender's **File > Render Studio / Local and Recoverable** now includes:
  - Save & Keep Session (atomic `.blend` with SHA-256 and last-good backup)
  - Open Last Saved Session (does **not** overwrite a dirty/current project)
  - Render Animation (Safe Frames) (freeze native source scene, create resumable job)
  - Resume Render / MP4 (same job ID and verified existing PNGs)
  - Fix Viewport Flicker (changes *view* depth clipping, disables X-ray/wire overlays, audits identical meshes; does not alter final render settings or delete geometry)
- Blender statusbar and Android overlay show **completed / total** frames and current stage. Android overlay additionally allows pause at frame boundary, explicit resume, and MP4 export to `Downloads/RenderStudio`.
- When returning to Render Hub, Save & Return waits for a successful save receipt; when a frame is running, the UI instead offers Pause After Frame. Autosave and session restore preserve work across ordinary navigation and many recoverable process restarts.
- Genuine small hand overlay is driven by `AgentWorkPresence` state from Render's own executor. On long frames, scheduled heartbeats keep work visible. It never simulates mouse/menu taps or claims GitHub commits happened inside Blender.

## Crash, thermal and pixel stability
- ProductionBatch now tests `next_frame > spec.end` instead of `next_frame > frame_count`. For a frame range 101–105 this fixes false completion at the very first frame.
- Immutable `snapshot.blend`, manifest fingerprint and per-PNG SHA receipts provide bounded frame retries without removing completed masters.
- Device temperature is read from Android's actual thermal status; if severe/critical, memory-limited, cancelled, or executor-busy the worker pauses. No hidden reduction of output dimensions, samples, or encoding bitrate.
- H.264 MP4 is created from verified PNG masters using Android MediaCodec. Failed encoding does not delete PNG masters; encode can be attempted again.
- Input video `1000071948.mp4` (29.09s, 864 × 1920) and accompanying car screenshots show speckling/flicker on/through car meshes. Potential causes: viewport X-ray/wire overlays, coincident coplanar meshes (Z-fighting), clipping depth ratio, transparent material sorting, and model normals. This is **not proven to be final-output aliasing**. The viewport fix deliberately cannot repair actually overlapping/deformed meshes automatically without risking scene destruction. Inspect identified object overlaps and final still renders.
- The screenshot explicitly flags **non-uniform scale** on a selected wheel; audit modifiers/parent transforms prior to applying scale. Applying transforms automatically can break animation/rigs; it is *not* part of this one-click fix.

## Free editable starter assets
Blender **Add > Render Studio Free Assets** and typed `production.execute` with `{"operation":"asset.create","payload":{"preset":"TREE"}}` generate editable native geometry. Presets:

| Category | Presets |
|---|---|
| Architecture | COLUMN, ARCH, STAIRS, WALL, WINDOW, ROOF |
| Landscaping | TREE, SHRUB, ROCK, GRASS, TERRAIN |
| Props & look development | BENCH, LAMP, WATER, STUDIO |
| Animation rig construction | HUMANOID, QUADRUPED |

All 17 are **original in-app procedural Blender geometry**, not downloaded paid models or claims of CC0 third-party licensing. The armatures and figures are **starter rig proxies**, not fully skinned, photoreal characters. WATER is a reflective starting plane, not a liquid simulator. Save the generated collections in your `.blend` projects and use the app's existing owner-authorized Drive backup as storage; Google Drive does not run Blender rendering.

## Ten reference videos → supported workflow
1. Movement blocking: Blender native timeline, animation curves, frame-by-frame preview and editable keyframes.
2. Dog/wolf rig controls: QUADRUPED Blender armature starter; advanced IK/skin weighting remains Blender manual work.
3. Railway cinematic scenery: TERRAIN, TREE, STUDIO lighting/camera, native materials and scene files.
4. Temple/monument environment: COLUMN, ARCH, WALL, STAIRS, ROOF, instance workflows.
5. WIP → Raw → Final: render snapshots, manual per-frame progress, native materials and PNG masters (advanced VFX not one-click).
6. Modular architectural model building: Add menu modular generators and native Blender instancing.
7. Waterways/fluid: curved ARCH and WATER materials; advanced LiquiGen-style simulation must still be built or imported separately.
8. Character design: HUMANOID starter armature, native modeling/sculpt/UV tools; **not** automatic likeness from a photograph.
9. Bridge-edge-loop curved arch: true segmented curved mesh asset; Blender's native mesh edit tools remain available.
10. Punch choreography: humanoid armature and Blender animation tools; no claim of turnkey martial-arts choreography.

## Acceptance gates (before any install)
1. Python compile/imports and contract tests; real bpy suite validates all 17 asset generators.
2. Android JVM unit tests incl. 101–105 resume, controlled job cancellation, cold restore, release package identity.
3. Full native APK must contain the startup modules and pass Android `aapt`, signer verification, `unzip -t`.
4. **On-phone checks still needed**: return navigation from a dirty `.blend`, overlay hand visible during real native command, frame 101–105 render survives process restart, render progress honest during >60s frame, 5-minute sustained render at unchanged quality, encoder resulting MP4 visually inspected, car flicker before/after in both solid/material preview and a render still, thermal stress, memory pressure, Drive backup/restore.
5. Only after evidence, install **original** APK in-place if the installed certificate matches. Never use the preview APK to overwrite original package. No claim that unlimited memory, unconstrained Blender plugins, or failure-proof rendering exist on Android.
