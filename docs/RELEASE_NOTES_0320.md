# Render Studio 0.32.1 — native storage and assets

Package `com.rezox.render`, version code **41**, version name
`0.32.1-native-storage-assets`. Retains 0.31.3 and the previously committed
native engine, startup recovery, render profiles, durable render queue, thermal
policy, checkpoints, VideoStudio Binder connection and artist controls.

- Adds target-scoped storage operations through the **existing** VideoStudio
  MCP/Binder connection: discover granted locations, create/list nested folders,
  inspect explicit documents, stage original files and export verified copies.
  File work does not require a ready Blender editor. No additional server,
  relay, unrestricted storage permission or Gallery enumeration.
- Adds a system file picker for models, images and videos, plus working-folder
  selection. Android must grant access; read-only providers remain importable.
  Owner controls and transfer notifications expose real byte progress, pause,
  resume and cancel.
- Persists file-transfer identities/results, partial originals and progress.
  Reusing an ID observes its retained result; a conflicting payload fails.
  Resumed imports verify the existing prefix; exports verify the source and
  destination hashes and refuse a conflicting artist file. Interrupted or
  restricted work requires explicit resume. Android's data-sync foreground
  service limits apply separately from native rendering.
- Adds authorized HTTPS file-reference ingestion for connected Drive/chat files.
  Size and SHA-256 are required. Expired URLs can be refreshed for the same
  transfer without changing its expected content. Private URLs and account
  credentials are not returned in transfer status.
- Adds resumable dependency ZIP extraction on the file worker, preserving
  directory names, originals, per-entry CRC and SHA-256. Traversal, conflicting
  names, oversized bundles and checksum failures are rejected.
- Adds native `file.importers`, `file.inspect` and checkpointed `file.import`.
  Discover actual installed Blender operators for GLB/glTF, OBJ, STL, PLY, FBX,
  USD, Alembic, BVH and Collada. Availability varies by build. Append explicitly
  selected editable Blender objects/collections/materials; import image
  references, textures, HDR lighting, video and audio through native APIs.
  Missing decoders/dependencies are reported. Artist timing, camera, color,
  units and render settings are preserved; originals are never resized to pass
  a memory gate.
- Adds `asset.providers`, AmbientCG HDRI import and honest category filtering
  when an upstream model query returns unrelated materials. Poly Haven and
  AmbientCG remain finite sources with source/license/format/size metadata.
- Maps TLS, connection, DNS, timeouts and revoked storage grants to actionable
  transfer errors without exposing signed URLs. Retained 0.32.0 failures also
  receive these hints when inspected; no automatic retries or TLS bypass.
- Marks cached in-flight render-worker states as interrupted when that worker
  no longer exists, retaining saved frame counts and requiring exact native
  receipt inspection. A stale saved label cannot keep claiming live rendering.
- Connection diagnosis now explicitly distinguishes local dispatch from a
  verified end-to-end Binder authentication check.

## Verification and limits

Focused host checks cover file boundaries, changed-source recovery, duplicate
requests, checksums, archives, image admission, render-setting preservation
contracts and packaging. Android storage results and the exact APK identity are
reported separately in [workspace evidence](WORKSPACE_TESTING_0320.md).

Google Drive connector OAuth does **not** grant Android folder access. Drive's
document provider must support the selected operation, or ChatGPT must transfer
original bytes using an authorized file reference. Provider readback proves the
copy visible to that provider; it does not prove completed remote Drive sync.
There is no automatic two-way Drive synchronization.

Files are limited to **4 GiB**, dependency bundles to **2,048 entries / 4 GiB
uncompressed**, and transfer history to **512 records**. Image admission defaults
to an estimated **128 MiB** decoded working budget; explicitly request a larger
budget only when actual available memory permits. Decoder/header/importer
coverage is finite. Blender scene append keeps the active project's settings;
it does not replace the active scene with every scene in an imported `.blend`.

The workspace's x86 Android ARM translator has already aborted native EEVEE and
Workbench rendering on a missing F16C assertion. No additional render replay,
completed character render, sculpted likeness or animation output is claimed.
The saved Stage 1 body remains a coarse blockout. Native success on a physical
Dimensity 7300 device, performance gains and uninterrupted 24-hour execution are
unverified. Explicit force-stop prevents execution until the app is reopened.

The APK must use the pinned historical repository signer; installation as an
update also requires the device-installed certificate to match. No physical
phone installation is claimed.
