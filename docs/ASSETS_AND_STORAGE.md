# Asset and project storage architecture

## Actual created Google Drive folders

Root: https://drive.google.com/drive/folders/1pKA6P9kqQmw1Y37n-jePqUXxHgk9v4I0

- AssetLibrary: https://drive.google.com/drive/folders/18d3w6BF49Jk1L6PfRzuwdp_XQgr1Luko
  - Characters-and-Rigs
  - Animations-and-Mocap
  - Environments-and-Props
  - Materials-and-Textures
  - HDRI-and-Lighting
  - Geometry-Nodes-and-Brushes
  - Audio-and-Video
- Projects: https://drive.google.com/drive/folders/14F-0osE79qMhpzvDs7iqkwof-6A-z8oO
- Renders: https://drive.google.com/drive/folders/1tLpmiVbkSHp_gQfDSTPaBhkJ1kUnrRas
- Backups: https://drive.google.com/drive/folders/1pDwPKTViJbOtau25jj49T9L6kWtzwjjx
- Licenses-and-Manifests: https://drive.google.com/drive/folders/1CcG5_NkBjXvlr3nC1gYoP-JFUgDfK97m

These folders have been created; NO Blender factory assets have been uploaded and automatic synchronization is not yet implemented.

## Storage tiers

1. **Install-critical resources**: essential scripts, presets, fonts, nodes, shaders and Blender factory assets must be available on the installed phone (licensed assets packaged in base app or install-time Android asset packs). No internet needed to launch or use core functionality.
2. **Working data**: `getExternalFilesDir(null)/Projects` for actively imported .blend files; later `AssetCache/`, `RenderCache/`, `Autosaves/`. Stream through SAF/ContentResolver into local files; do not make remote Drive URIs the dependency graph for .blend content.
3. **Drive**: optional canonical user library, backups, archived projects and final rendered output; never used as a render server, process memory, virtual GPU RAM, or required runtime service.

## Planned asset system

- Catalog every asset with opaque ID, relative path, byte length, SHA-256, license, Blender compatibility version, required dependencies and origin Drive file ID. Verify before making content visible to Blender.
- Support user-pinned offline packages, resumable chunk downloads, durable in-use locks, versioning, offline edits and conflict-safe upload of updated projects.
- Persist proper Blender Link/Append and library-overrides semantics; resource paths should be relative to local .blend files or a local mounted asset-library root. Never substitute low-resolution assets without user choice.
- Keep all .blend project sources, original textures/meshes/rigs/HDRIs and final renders unaltered. Render proxies and caches are additional derived data.
- Google Drive 400 GB is remote capacity, not local free space, memory, rendering horsepower, or a substitute for an offline asset cache.
- Only distribute Blender Essentials and third-party assets after checking their individual licenses and required attributions. Blender binaries/source code belong in versioned build artifacts/repository history, not Drive's user asset library.
- Never upload cloud files automatically without the user enabling sync; importing through Android's Storage Access Framework is available without granting blanket Drive access.

## Current implementation status

Foundation importer copies a selected authentic `.blend` header/file into local Projects with a streaming SHA-256. This is storage-only: it does not yet parse, render or edit .blend and does not synchronize Drive.
