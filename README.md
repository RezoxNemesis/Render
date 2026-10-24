# Render — Native Blender for Android

**Goal:** bring Blender's real feature set to a phone-native Android application, with on-device computation and rendering. This project is separate from VideoStudio.

## Non-negotiable product contract

- Blender's upstream C/C++ implementation is the intended engine source. A visually similar editor is not a substitute for genuine Blender functionality.
- Android-only operation: no required desktop workstation, remote Blender, streaming, cloud rendering, or cloud login.
- Keep native project semantics and `.blend` compatibility. Preserve modeling, sculpting, UV, shaders, Geometry Nodes, rigging, animation, simulation, compositing, rendering, scripting, and extensions as acceptance targets.
- Adapt UI/input to touch, stylus, and optional keyboard/mouse without silently removing operations.
- Downloadable Google Drive asset libraries and backup are optional; active resources must be local when offline.
- Do not advertise feature parity until real Android device tests against upstream Blender show it.

**Current build target:** the full ARM64 Android Blender application in `full-app/`,
including the existing VideoStudio native Binder connection. The `app/` project
also supplies the JNI bridge and project inspector; building only that module
emits the smaller foundation APK, not the full editor.

The 0.31.1 candidate retains the latest native-control and storage improvements.
See [release notes and limitations](docs/V031_RELEASE_NOTES.md). Following the user's
workspace-testing request, 149 Android/JVM tests and 118 Python checks passed.
Host tests and APK builds do not establish native success, phone compatibility,
performance or 24-hour endurance; emulator results are separate evidence.

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

### Genuine Blender file compatibility CI
A second CI job creates actual Blender scene and animation fixtures with upstream `bpy` on a temporary Linux runner, then tests our native Android-targeted reader against the saved files and gzip envelope. The CI desktop binary is a development **test generator only**, not an app dependency or remotely hosted engine. No complete BKE scene reconstruction is claimed.

## Shared VideoStudio MCP control
Render can reuse the existing VideoStudio v3 Cloudflare Worker and ChatGPT plugin as an isolated second native device. It generates a new Render-owned Keystore identity via a one-use VideoStudio pairing code, and adds native Blender work to a separate queue. No new Railway or Render.com server or second ChatGPT connection is required; real on-phone pairing and actual Blender execution remain to be verified. See docs/AGENT_ACTIVATION.md.

## v0.14 VideoStudio-style Connect / Share with ChatGPT
Render's UI now offers a direct on-phone bridge using the SAME VideoStudio MCP v3 connection, with a one-tap Connect / Share action and a stable NON-SECRET Render app UUID. A command result includes target_app=Render Studio, target_package=com.rezox.render and render_public_id, so ChatGPT can distinguish Blender work from VideoStudio timeline work. No second relay, developer key or Cloudflare redeployment is needed for this direct native mode; on-phone APK pairing and actual result verification remain outstanding. See docs/AGENT_ACTIVATION.md.

## Permanent signing and backup-first updates
The private Render Studio release PKCS12 keystore and recovery record are stored in the owner’s private ChatGPT Library /Render/Signing (NEVER in this public source repository). Stable owner-signed release APKs require configuring four protected GitHub Actions secrets, detailed in docs/RELEASE_SIGNING_AND_BACKUP.md. Earlier CI debug-signatures may not be upgradeable in place; export saved .blend projects with the new Project Inspector ZIP backup feature before uninstalling.


## Full native APK (build only)

Requires JDK 17, Gradle 8.11.1, Android SDK 35, build-tools 35.0.0,
NDK 27.2.12479018 and CMake 3.22.1. Prepare sources using
`python3 tools/prepare_production_toolkit.py`, build `:app:assembleDebug`, then
stage the pinned engine with `tools/assemble_full_native.py` and build
`gradle -p full-app :app:assembleDebug`. Exact pinned download/source references
and a build-only path are in `.github/workflows/render-031-build-only.yml`.

Use the existing owner/historical signing identity. A newly signed local debug
APK cannot replace an installation signed by another key; never uninstall or
clear artist data to force an update. The build-only job fails when the pinned
historical key is unavailable. Permanent owner release signing stays private.
