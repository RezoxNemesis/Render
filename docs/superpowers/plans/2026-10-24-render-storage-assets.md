# Render storage and asset extension

User steering: normal ChatGPT should create folders, save native projects, import
explicit files from device storage/Google Drive and download/use varied free
assets. Keep the prior quality-preserving, durable render requirements and existing
VideoStudio MCP/Binder; no new server/relay, Gallery scanning or external renderer.

- Preserve 0.31.3 code/native engine and the saved character review project.
- Add discoverable app-workspace and artist-granted SAF storage locations, opaque
  document handles, folder creation/listing and verified import/export copies.
- Keep storage usable while the editor is unavailable. Use durable, cancellable
  transfers with bounded streaming and visible Android work when permitted.
- Add direct authorized HTTPS file-reference ingestion for connected Drive/chat
  files without copying account credentials into Render. Preserve originals.
- Add structured native importer discovery/inspection/import for supported model,
  Blender, image/HDRI and video formats. Checkpoint before native changes; report
  unsupported build/add-on formats explicitly and preserve editable data.
- Broaden existing asset metadata/import coverage and support local/Drive libraries;
  expose finite provider/license/format limits without promising every asset.
- Verify storage/queue/error boundaries, build the next monotonically versioned
  historical-signer APK and exercise feasible Android I/O paths. Record native
  import/render and remote-auth limitations separately.

Android folder access requires its picker grant. Google Drive connector access
does not itself grant an Android ContentResolver permission. Both routes can
transfer original bytes, but neither provides Blender compute resources. The
workspace's repeated F16C render abort remains an environment limitation; do not
replay the claimed frame command or skip to character sculpting after that failure.
