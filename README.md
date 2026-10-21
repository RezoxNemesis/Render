# Render — Native Blender for Android

**Goal:** bring Blender's real feature set to a phone-native Android application, with on-device computation and rendering. This project is separate from VideoStudio.

## Non-negotiable product contract

- Blender's upstream C/C++ implementation is the intended engine source. A visually similar editor is not a substitute for genuine Blender functionality.
- Android-only operation: no required desktop workstation, remote Blender, streaming, cloud rendering, or cloud login.
- Keep native project semantics and `.blend` compatibility. Preserve modeling, sculpting, UV, shaders, Geometry Nodes, rigging, animation, simulation, compositing, rendering, scripting, and extensions as acceptance targets.
- Adapt UI/input to touch, stylus, and optional keyboard/mouse without silently removing operations.
- Downloadable Google Drive asset libraries and backup are optional; active resources must be local when offline.
- Do not advertise feature parity until real Android device tests against upstream Blender show it.

**Current status: Android application/NDK foundation with native .blend framing preflight, Vulkan capability probing, and real upstream Blender BLI FP16 and BLO header/BHead decoding modules cross-compiled for Android. The full Blender scene engine is not integrated: only a genuine upstream math module is compiled. This is not a full Blender port or a render-capable APK. No BKE/Main scene reconstruction or dependency-graph evaluation; gzip header/schema preflight uses the upstream reader, zstd remains unavailable.**

## Repository layout

- `app/` — native Android shell, Storage Access Framework `.blend` import, JNI bridge, native file-format preflight, Vulkan hardware probe (not a renderer).
- `docs/ENGINE_PORT_CONTRACT.md` — technical port plan and release gates.
- `docs/BLEND_FILE_PREFLIGHT.md` — detailed v0/v1 binary format coverage and strict limitations.
- `docs/DNA_CATALOG.md` — diagnostic SDNA schema indexing, limits, and remaining full engine blockers.
- `native-tests/` — host C++ tests for structural file preflight and Blender FP16 math.
- `third_party/blender_half/` — actual version-pinned upstream Blender math code (GPL) plus narrow Android guard patch.
- `docs/BLENDER_UPSTREAM_PORT.md` — upstream source provenance and next core engine integration.
- `docs/ASSETS_AND_STORAGE.md` — Google Drive and offline asset architecture.
- `docs/PARITY_MATRIX.md` — feature acceptance tracking.
- `tools/check_contract.py` — static checks that guard against silent remote-compute substitution.

## Build the foundation

Prerequisites: JDK 17, Android SDK Platform 35, Android NDK, CMake 3.22.1, Gradle 8.11.1.

```bash
gradle :app:testDebugUnitTest :app:assembleDebug
cmake -S native-tests -B /tmp/render-format-tests
cmake --build /tmp/render-format-tests
ctest --test-dir /tmp/render-format-tests --output-on-failure
python3 tools/check_contract.py
```

The project deliberately does not include a checked-in Gradle wrapper binary; a pinned Gradle version is installed in CI.

## Blender upstream and licensing

Blender official source: https://projects.blender.org/blender/blender and public mirror https://github.com/blender/blender .
The eventual integrated Blender-derived app must fulfill Blender's GNU GPL and all third-party asset/component licenses, include license/attribution notices, and provide corresponding source. This foundation includes genuine Blender BLI FP16 source and its GPLv2 license text under third_party/blender_half; it does not bundle Blender factory assets. Full GPL/copyleft and bundled third-party license obligations will apply to distributable releases.

See the documents for blockers and milestone gates. Do not mark core features implemented based on this scaffold.
