# Asset and project storage — 0.32.0

## Optional Google Drive folder structure

Recommended organization for an artist's optional private Drive workspace:

- Render/
  - AssetLibrary/
    - Characters-and-Rigs/
    - Animations-and-Mocap/
    - Environments-and-Props/
    - Materials-and-Textures/
    - HDRI-and-Lighting/
    - Geometry-Nodes-and-Brushes/
    - Audio-and-Video/
  - Projects/
  - Renders/
  - Backups/
  - Licenses-and-Manifests/

**Do not hardcode real Drive folder IDs, URLs, tokens, or private storage metadata in this public repository.** Let the artist choose folders and retain grants in private app configuration. NO Blender factory assets have been uploaded by the app. Automatic two-way synchronization is not implemented.

## Storage tiers

1. **Install-critical resources**: essential scripts, presets, fonts, nodes, shaders and Blender factory assets must be available on the installed phone (licensed assets packaged in base app or install-time Android asset packs). No internet needed to launch or use core functionality.
2. **Working data**: app-private `Workspace`, native `Production/Projects`, immutable originals in `Production/Imports`, extracted dependency bundles, native asset cache and checkpointed render jobs. Existing external-files Projects remain compatible. Stream through SAF/ContentResolver into local files; do not make remote Drive URIs the dependency graph for .blend content.
3. **Drive**: optional canonical user library, backups, archived projects and final rendered output; never used as a render server, process memory, virtual GPU RAM, or required runtime service.

## Storage through the existing ChatGPT connection

Keep the original VideoStudio MCP/native Binder path. `production.execute` uses
the public `target_id` returned by `capabilities`; that ID is **not** the private
VideoStudio device credential. Do not create a new server or relay.

1. Inspect `storage.capabilities` for field schemas and `storage.locations` for
   opaque granted location IDs. `workspace` is always app-private; it is not
   unrestricted phone storage. Each location starts at `parent_id: "root"`.
2. If external access is missing, use `storage.pick` for the Android folder
   picker, or `storage.file.pick` for one explicit file. The owner must select
   it. Connected Drive OAuth does not itself confer an Android grant. Read-only
   provider grants can import; folder creation/export requires write access.
3. Use `storage.folder.create` with `location_id`, `parent_id`, and `name` to
   create or reuse a folder. `storage.folder.list` returns bounded pages of
   opaque document handles; no Gallery or broad-media enumeration is used.
4. `storage.import` copies a selected `document_id` into an immutable SHA-named
   original. `storage.fetch` ingests an authorized HTTPS original-file reference
   from a connected Drive/chat tool; supply its exact original size/SHA-256 and
   filename, plus license information when known. Do not pass OAuth tokens.
5. Each transfer requires a unique `request_id`. Retain the returned
   `transfer_id` and poll `storage.task.status`. An uncertain reply is resolved
   by polling that exact ID; do not submit a new mutation blindly. Identical
   request IDs retain results; conflicting payloads fail. Pause/resume/cancel
   use `storage.task.*`; interrupted work requires explicit resume.
6. A transfer result's `file` and `sha256` become `filename` and
   `expected_sha256` for `file.inspect` / `file.import`. For dependency ZIPs,
   first call `storage.unpack`, poll completion, inspect the bundle and choose
   an explicit `entry`. Original files, paths and checksums stay separate from
   previews. Hash-verified completed ZIP entries are reused after interruption.
7. Native `file.importers` and `artist.capabilities` report available operations
   and schemas for this Blender build. Format discovery is not decoder success.
   Native imports checkpoint before changes, preserve artist render/timing/
   camera settings, and report missing images rather than claiming complete
   output. `.blend` append requires explicit objects, collections or materials;
   it preserves editable meshes, rigs and actions and the active scene settings.
8. Save through native `project.checkpoint` or `project.export`, then use
   `storage.export` with its `category`, `filename` and `expected_sha256`, the
   destination location/parent and desired name. Poll for independent provider
   readback verification. A different existing destination is never overwritten.
   Native projects and rendered originals remain intact.

The owner can also choose files/folders and pause/resume/cancel transfers on the
connection screen. File transfers use a visible `dataSync` foreground service
when Android permits. It has Android time limits; it is separate from native
render services. It does not promise execution after explicit force-stop. A
completed provider readback does not establish completed remote Drive sync.

An expired original-file URL can be refreshed with `storage.task.refresh` using
the same transfer ID and a fresh authorized URL. Its expected size and digest
cannot change. Poll and explicitly resume afterward. Transfer status omits the
private source URL. Supply a new request ID when the actual source file changes.

Transfer limits: 4 GiB per file; 2,048 ZIP entries and 4 GiB uncompressed per
dependency bundle; 512 retained task records. Archive extraction is bounded,
checksum-verified and performed on the file worker, outside Blender's UI thread.
Image admission estimates decoded working memory and refuses an oversized image
without shrinking it. Its default 128 MiB budget can be explicitly raised when
actual device memory permits. Native decoder/header and add-on coverage varies.

## Free asset sources and originals

`asset.providers` reports the supported catalog and explicit-file routes even
without the editor. Existing native `asset.search`, `asset.details`,
`asset.preview`, `asset.download`, `asset.download.status` and `asset.import`
remain available inside Blender. Poly Haven supplies models, materials and
HDRIs. AmbientCG supplies supported PBR texture and HDRI archives. A mismatched
upstream model filter does not return materials as models. Both catalogs are
finite: grass, mountains, birds or any other query may have no matches. Source
URLs, license, preview and available format/size metadata are exposed; use
details before downloading. Unknown explicit-file licenses are not assumed CC0.

Self-contained GLB/packed Blender data, supported model files, image references,
textures, HDRI and supported video/audio can also arrive from artist-granted
storage or connected Drive originals. Dependency ZIPs preserve sibling resource
names. glTF external URLs/paths cannot substitute for explicit dependency files.
Scripts and arbitrary Python are not remote import operations. Missing native
importers/codecs must be resolved in the app build; there is no desktop/cloud
fallback or external generator.

## Further asset-system work

- Add richer local/Drive library indexing, compatibility metadata and dependency management beyond the current explicit handles and checksum manifests.
- Support user-pinned offline packages, resumable chunk downloads, durable in-use locks, versioning, offline edits and conflict-safe upload of updated projects.
- Persist proper Blender Link/Append and library-overrides semantics; resource paths should be relative to local .blend files or a local mounted asset-library root. Never substitute low-resolution assets without user choice.
- Keep all .blend project sources, original textures/meshes/rigs/HDRIs and final renders unaltered. Render proxies and caches are additional derived data.
- Google Drive 400 GB is remote capacity, not local free space, memory, rendering horsepower, or a substitute for an offline asset cache.
- Only distribute Blender Essentials and third-party assets after checking their individual licenses and required attributions. Blender binaries/source code belong in versioned build artifacts/repository history, not Drive's user asset library.
- Never upload cloud files automatically without the user enabling sync; importing through Android's Storage Access Framework is available without granting blanket Drive access.

The earlier foundation-only file inspector remains a separate utility. The full
APK bundles native Android Blender; verification of storage, decoding, import,
rendering, remote authentication and output quality must be reported separately.
