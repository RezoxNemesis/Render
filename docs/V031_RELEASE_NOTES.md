# Render Studio 0.31.1 follow-up (versionCode 37)

The user subsequently authorized workspace testing. **149 Android/JVM tests and
118 Python checks passed** (45 contracts, 68 behavior checks and 5 archive/catalog
recovery checks). These include SQLite migration, exact-ID interrupted command
recovery, render queue cancellation, safety-preserving scheduling, launch identity,
preview/final isolation, download finalization and temporary-path safety.

Testing found and fixed a missing `catalog_is_finite` field in federated metadata
and a HUD that showed a measured zero when timing was unavailable. Test fixtures
now publish the complete process-and-launch readiness handshake, retain fractional
profile settings, and expect queued work/pause-aware pacing rather than old behavior.
An emulator-only, read-only native diagnostics phase was added; it creates no model,
render job, animation or benchmark scene. Actual runtime outcomes are recorded in
the workspace test evidence separately. Host passes do not establish native success,
phone compatibility, speed or endurance. The historical signing identity is retained.

The following records the original 0.31.0 engineering candidate and its limits.

# Render Studio 0.31.0 — native engineering candidate

Package: `com.rezox.render`; versionCode **36**; versionName
`0.31.0-native-reliability`; ARM64; minimum Android 12 (API 31).

## Implemented

- Retains the latest native-control/configuration/runtime cleanup, Vulkan dispatch,
  artist HUD, original Blender engine and OMEGA modules. Merges the separately
  committed SAF project-folder, verified backup and post-restart export work.
- Native readiness requires the actual Blender timer, current process and current
  NativeActivity launch identity. Reopening a live editor reuses it; overlapping
  launches are blocked. Preparation checks storage, preserves the sealed old
  runtime until replacement succeeds, and optional studio UI failures do not
  disable the executor. Launch request and editor readiness remain separate.
- Binder acceptance is committed to the migrated SQLite journal before dispatch.
  Up to 12 queued commands survive service/process loss. Claimed commands become
  recovery-required after interruption and are never automatically replayed.
  `ipc.command.status` and `native.command.status` inspect exact IDs; retained
  results and structured native failures include checkpoint recovery information.
  Status/cancel controls bypass the busy native worker. The existing VideoStudio
  connection, private Android credentials and distinct public Render ID remain.
- Ordered render intentions persist independently of native immutable manifests.
  Start/resume/retry, pause, cancellation and a 64-entry queue retain completed
  frames and checkpoints. Queue handoff recovers after process death. A resume
  during pause waits for the outstanding frame before restarting the worker.
  Notifications and editor/Hub controls expose real frame progress and cancellation.
- Separate preview/final profiles preserve every unspecified artist setting.
  Profile settings are saved with the scene and applied only to new immutable
  render jobs. Performance settings cannot modify quality settings. New frames
  avoid redundant engine/settings writes and frame evaluation; production modules
  and verified snapshots are reused. Finished snapshot caches release unreferenced
  owned data conservatively, without a global orphan purge. No speedup is measured.
- Native per-frame timings persist in render manifests. UI/HUD and status expose
  completed/total frames, accumulated native render time and estimated remaining
  frame time when calculable. Estimates exclude encoding, cooling and export.
  The pointer reflects actual touches/confirmed native actions, stays in editor
  UI and is excluded from camera-render output.
- Real Android thermal status and memory drive frame admission. Headroom calls
  are limited to Android's 10-second cadence. Battery temperature is explicitly
  separate from unavailable CPU temperature; absent memory telemetry is not a
  fabricated zero-memory failure. Users/ChatGPT can increase the memory reserve
  and add frame pacing; these controls cannot disable thermal protection.
- Discoverable `artist.capabilities`/`artist.inspect` add checkpointed sculpt masks,
  native brush strokes, facial shape-key expressions, duplication/removal,
  light/camera edits, explicit image/video imports and BLEND/available GLB exports.
  Existing modelling, materials, textures, rigging, animation, saving and rendering
  tools remain. Destructive existing operator/import/restore/bind/edit paths also
  checkpoint first. Native failures retain exact result IDs and actionable details.
- Poly Haven and AmbientCG search provides source/license information, original
  formats and byte sizes, cached previews and explicit-resolution downloads.
  Downloads retain original files separately; interruption resumes partial bytes
  or retained archives. ZIP paths, sizes, CRCs, local hashes and storage budgets
  are checked. Poly Haven publisher MD5 and local SHA-256 are retained; AmbientCG
  does not supply a publisher digest, so its receipt explicitly distinguishes
  HTTPS/size/ZIP CRC/local SHA-256 from publisher verification. Native PBR imports
  keep editable material nodes and original maps; displacement is not auto-applied.
- Explicit Android document/share import checks free storage and supports images
  up to 100 MiB/80 MP and MP4 up to 2 GiB/24h. Copies are labeled as inbox copies,
  separate from successful native Blender import. No Gallery enumeration occurs.

## Remaining limits

**Runtime testing and all test suites were skipped at the user's request.**
No app installation, native modelling/import/render/capture/encoding, generated
animation, benchmark or physical-phone validation was performed for this release.
Compilation and APK inspection are build evidence only. No measured performance
increase, Dimensity 7300 thermal result, native success, output-quality comparison,
24-hour endurance or uninterrupted background operation is claimed.

Android may stop the process; explicit force-stop prevents execution. Android 15+
media-processing service budgets and vendor power policies still apply. The native
engine remains owned by NativeActivity, rather than an independently restartable
headless process. A blocking native frame may finish before pause/cancel is applied;
quota expiry can interrupt that frame. Verified completed frames remain recoverable,
but sample-level progress and mid-frame resume are unavailable.

The durable render pipeline masters PNG frames and optionally produces lossy H.264
parts. New jobs retain PNG 8/16-bit precision and color mode. HDR/32-bit source output
fails explicitly in this pipeline; use Blender's native render menu for those formats.
That native route retains Blender capabilities but has no new durable-job guarantee.
Existing job manifests remain readable. Encoding estimates are not provided.

Catalogs are finite and network dependent; specific birds, terrain or models are not
guaranteed. AmbientCG direct import currently supports PBR material ZIPs; other
catalog formats are marked unavailable for direct import. Native sculpt strokes need
an available brush and a valid visible native viewport. GLB requires its native
exporter to be bundled/enabled. Video sequencer import is video-only; it does not
silently add or change audio. Arbitrary Blender add-on/operator parity is not claimed.
Checkpointing and asset verification can be expensive for very large projects.
Checkpoints and originals are retained rather than automatically deleted.

The build-only CI workflow attempts the repository's historical private signing
cache and verifies its pinned certificate. It must fail rather than create another
key if that identity is unavailable. A historical fingerprint alone does not prove
compatibility with the currently installed phone APK. No uninstall or data clear
is part of this upgrade. See the delivered build/signature evidence for the actual
APK certificate and source commit.

## Primary automation entry points

Use existing `production.execute` with `operation`, `payload` and the exact
`target_id` returned by capabilities. The public ID is not authentication.

- Discover: `capabilities`, `artist.capabilities`, `operator.describe`.
- Settings: `render.profile.inspect/configure` (profile `preview` or `final`, sparse
  `settings`), `render.quality.inspect/configure`, `render.performance.inspect/configure`,
  `render.scheduling.inspect/configure` (`memory_reserve_mib`, `minimum_frame_gap_ms`).
- Work: `render.plan` (`profile` optional), `render.job.start/status/pause/resume/cancel/retry`,
  `render.queue.status`. Start/resume/retry/cancel identify `job_id`.
- Recovery: poll `ipc.command.status` with the original Binder `command_id`, then
  `native.command.status` with its exact native ID before considering another mutation.
- Assets: `asset.search` (`provider`: all/polyhaven/ambientcg), `asset.details`,
  `asset.preview`, `asset.download/status/pause`, `asset.import`.
- Native media: `reference.pick/list/metadata` then `media.import` with an exact owned
  `asset` and mode `IMAGE_REFERENCE` or `VIDEO_SEQUENCE`.
- Save/export: `project.checkpoint`, `project.checkpoint_export`, `project.export`
  (BLEND/available GLB), `artifact.read/export` with category `Exports`.
