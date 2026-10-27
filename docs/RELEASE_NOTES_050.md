# Render Studio 0.50.0 — Creator Studio

Build: `0.50.0-creator-studio`, Android version code 60.
Baseline: `10af26a08c77c69d7da2ab5e6f30c25d461be4e6`, including the standalone
Render MCP integration and previous native sculpt/artist tools.

## Creation and usability

- New Android home screen with direct Creator entry, concise guidance, full
  Blender portrait/landscape entry, recovery and ChatGPT connection controls.
- Native Blender Create sidebar and menu for seven kinds of guided work:
  modeling, terrain, instancing, materials, motion, cameras and deform rigs.
- Eight parametric props, four terrain styles, six procedural materials,
  four motion presets, four camera presets and weighted chain rigs.
- Ten offline brief recipes with explicit step previews and complexity estimates.
  The planner does not claim to be an embedded language model.

## Agent execution

- Eleven new typed operations, advertised schemas, descriptions and read-only
  metadata through existing authenticated capability discovery.
- Preview hashes bind recipes to relevant scene state, installed operations,
  requested parameters and queued work. Changed state requires a new preview.
- Durable, serialized plans with actual native receipts and idempotent retries.
- Plans bind to their accepting scene/session. A scene switch or restart cannot
  silently redirect pending edits into another project.
- `.blend` checkpoints before Creator edits, native failure rollback, frozen
  render-snapshot protection and bounded instance/geometry workloads.

## Security and packaging

- Disable script auto-execution for automated `.blend` recovery and native agent
  startup without persisting a change to the owner's global Blender preferences.
- Validate binary GLB JSON dependencies as well as text glTF, including traversal,
  symlinks, malformed chunks and misleading file extensions.
- Reject local/private IP literals and alternative loopback spellings in remote
  file-transfer URLs; retain HTTPS, hash and size verification.
- Add regression checks around the standalone relay's request-body size limits.
  See the security review for deployment scope and residual boundaries.
- Verify the full APK's historical signer, package/version, native engine and
  byte-for-byte Render runtime source contents before publishing a prerelease.

The native Android Blender engine remains pinned to the existing source/binary
provenance. No new rendering engine, fivefold performance result, unlimited
world-generation capability or malware-free certification is claimed.
