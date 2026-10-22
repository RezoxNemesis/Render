# Render Studio 0.20 native production toolkit

This is an additive DEVELOPMENT upgrade, not a claim of complete Blender parity or a fully validated film-production release. All project creation, modeling, animation and user-scene rendering execute in the Android Render app. Desktop Blender in CI is used only for synthetic semantic regression fixtures, never as the user's production renderer.

## Preserve the existing installation

The original Render application and its unsaved scenes must not be removed, restarted, overwritten or migrated silently. Save/export current work before any owner-approved update. The `com.rezox.render.preview` APK is independently installed and has a separate project store and public UUID. It does not automatically copy the original project's data. The original-package development APK is NOT an in-place update guarantee: its signing certificate may differ from the installed app. Permanent owner signing remains in the existing manually approved release workflow; feature branches never receive that key.

The matching VideoStudio carrier is 3.5.5, based on the working 3.5.4 carrier. It preserves the original package, preference/Keystore namespace, private MCP endpoint and signing identity. Do not uninstall VideoStudio or clear its data to force an incompatible update.

## Connection recipe that must be used next time

1. Use the current owner-provided private VideoStudio credential through the existing connected MCP. Never substitute a public Render UUID as `deviceId`, and never fall back to an older remembered credential without verifying it targets the current device.
2. Read device/app status. Control-plane connectivity, Android-native availability and a ready Blender editor are distinct states.
3. Call `render.engine.status` through `queue_video_edit`, `projectId=active-native`, `action=autonomous_request`, explicitly setting the actual `target_package` in nativeParameters. Original is `com.rezox.render`; preview is `com.rezox.render.preview`.
4. Poll the exact command ID. Require a successful native response identifying `target_app=Render Studio`, the expected package and the public UUID from that installed app's share card.
5. Call `render.production.execute`, operation `capabilities`, payload `{}`, using the same target package. The carrier no longer needs a separate allowlist entry for every new typed Render production operation.
6. Every later production call must include `target_id=<verified Render UUID>` as well as `target_package`. Render rejects mismatched/stale identities before mutation.
7. Request `editor.open` if necessary, then verify editor readiness and `scene.inspect`. A launch request is not proof that Android foregrounded the editor; owner interaction can be required by Android.

The connection card now carries this procedure and the actual package. No private credential is included in source, cards or scene files. Unavailable commands are capability mismatches, not automatically offline-device errors. Do not repeatedly queue unsupported operations or silently replace detailed geometry with cubes.

Example native parameters (place inside the existing queue tool envelope):

```json
{
  "target_package": "com.rezox.render.preview",
  "target_id": "<UUID FROM THE VERIFIED PREVIEW APP>",
  "operation": "project.create",
  "payload": {"name": "DragonFight"}
}
```

The outer nativeAction is `render.production.execute`. Poll its returned command ID and inspect the actual native receipt before proceeding. A queue acknowledgment is never completion evidence.

## Implemented operation families

- Project lifecycle: create a separate scene without deleting prior scenes; checkpoint a copy of the native `.blend`; list owned checkpoints; restore the exact checksum-matched scene from a checkpoint while retaining the previously active scene.
- Scene inspection: paginated objects and transforms, parents, topology counts, frame range, fps and active camera. Do not infer visual quality from object count.
- Geometry: smooth UV/ico spheres, cylinders, cones, torus, planes and cubes, custom vertex/face topology, bounded precise vertex edits, bevel controls. These are actual Blender meshes, not a substitute UI drawing.
- Surface appearance: native Principled PBR base color, metallic and roughness, emission, packed image textures, world color/strength and camera target/lens.
- Hair/detail curves: editable tapered 3D curve strands. This is curve geometry, not automatic grooming or a physically simulated hair system.
- Animation: transform-preserving parent groups, batched object keys, facial shape keys and animated shape values, native armatures, explicit complete skin weights and pose-bone animation.
- Reference images: checksum-verified chunk import of owner-supplied PNG/JPEG assets, reference-image objects and packed texture attachment. This does NOT reconstruct unseen geometry automatically.
- Dense repeated scenes: three-level nested Geometry Nodes instancing without Realize Instances, exact grid counts, native memory preflight and explicit confirmation for large requests.
- Screenshots: PixelCopy of Render's own visible native Blender window, saved as full-resolution PNG with hashes. No other app or Gallery browsing. Viewport capture and final render are different artifacts.
- Output: immutable snapshot-based PNG frame jobs, requested-frame verification, resumable per-frame progress, Android MediaCodec H.264/MP4 fallback independent of Blender's FFmpeg, exact-file hash reads and verified Downloads export.

## Safe autonomous authoring sequence

Discover capabilities -> inspect active scene -> create a new scene when asked -> build real geometry -> assign materials -> create hierarchy/rig before animation -> add keys -> inspect several frames and actual screenshots -> checkpoint when authorized -> render a short quality-check range -> inspect the actual image/video artifacts -> render final range -> verify hashes/counts -> export the exact MP4.

Do not claim a finished film from native object/keyframe receipts. Do not group previously animated world-space objects and assume all existing keys were converted into a new local coordinate system. The new hierarchy path is intended before animation; complex reparenting requires an explicit bake/verification step.

## Resumable rendering and MP4

1. `render.plan` specifies exact width, height, fps, start/end, samples, engine and bitrate. It writes a separate snapshot and manifest without changing the source `.blend` path. Pack external images before planning; unowned/unpacked dependencies are refused rather than silently omitted.
2. Repeated `render.step` calls render one exact requested frame from the frozen snapshot. Each frame is written atomically and hashed. The active working scene is restored after rendering.
3. `render.status` reports actual completed frames, not expected success. On low memory or severe thermal pressure, work pauses without reducing requested resolution or samples. Resume only after inspecting state.
4. Once all frames exist and hashes match, `render.encode` streams the native PNG masters into Android's H.264 encoder at the requested size/fps/bitrate. Unsupported hardware formats produce an explicit error. PNG masters are retained; MP4 itself is a lossy delivery format.
5. `artifact.export` publishes only the exact expected-hash PNG, MP4 or `.blend` to `Download/RenderStudio`. `artifact.read` supports bounded authenticated chunks for explicit transfer into the chat.

No cloud render, fake video placeholder, unverified complete flag, automatic downscaling or silent engine-to-Workbench substitution is allowed. Current MP4 encoder is video-only; audio muxing and hardware-specific codec behavior still need acceptance work.

## Stability and limits

The carrier serializes native Binder work instead of flooding the Render worker. Requests and geometry batches are bounded; overflow returns an explicit error. Pause and identity checks remain active. Uncertain mutations must not be blindly replayed. Owner Stop/cancellation and filesystem scoping are protections, not restrictions to remove.

A request up to 10,000,000 repeated instances can be planned. This is not ten million separate objects or ten million unique detailed characters. The estimate reserves memory headroom but cannot guarantee driver/OS behavior. A physical-device ten-million-instance stress test has NOT passed, and crash-free operation at arbitrary scene complexity is NOT claimed.

The original Blender engine is retained. This toolkit does not expose every desktop Blender operator through MCP, nor validate every modifier, simulation, add-on, graphics driver or format. High-quality modeling still requires reference interpretation, appropriate topology, rigs, materials, lighting, composition and actual visual inspection—not merely a high block count.

## Verification gates

The regression suite checks typed argument boundaries, target identity, owned paths, symlink/traversal denial, chunk integrity, canonical manifests, exact instance plans, memory refusal, package/runtime inclusion, request sequencing and original command compatibility. Real Blender fixtures test detailed sphere topology, smooth shading, PBR, parent motion, tapered curves, facial shape animation, actual skin deformation, checkpoint restoration and exact frame rendering while preserving the editor scene.

Before claiming this candidate ready on the owner's phone, verify: installation/certificate compatibility; correct native handshake; editor launch; a real screenshot; project save/reopen; a short native render; Android MP4 encode/decode and export; background/Stop/recovery behavior; progressive memory/thermal stress tests. None of those physical-device gates is satisfied merely by a CI build.

## Reproducible build integration

Run `python tools/prepare_production_toolkit.py` before building. It applies exact-source, idempotent integration to the existing agent registry, Java schemas, native spool, startup dispatcher, version metadata, screenshot Activity hook and runtime packaging. It refuses source drift. The new production modules remain separate from the existing modeling and upstream engine code. Main/release branches are not changed automatically.
