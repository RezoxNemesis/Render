# Render Studio 0.50 targeted security review

Review date: 28 October 2026 (Asia/Kolkata). Baseline: `10af26a`, with the 0.50 creator-suite working changes on `upgrade/render-studio-050-creator-suite-20261028`.

This review found and corrected source-level security weaknesses. It did **not** identify intentionally malicious code in the paths examined, and did not establish that the app, a device, every dependency, or the precompiled Blender engine is free of malware. No user project was deleted, no credentials were uploaded, and no executable was removed merely because it was unfamiliar.

Release integration subsequently deployed the tested Cloudflare request-reader
fix as relay version **1.0.2**. The deployed source matched the repository
baseline before replacement and matched the corrected source afterward. The
existing enrollment-secret binding, Durable Object namespace and compatibility
date were preserved through strict binding inheritance. Live probes returned
200/version 1.0.2 for `/health`, 401 for an unauthenticated `/mcp` request and 413
for a 524,289-byte enrollment request. These probes do not establish a paired
phone session or native execution. Deployment ETag:
`01efec0ae5e02a114b5e951d2ffbdca47b861cb9271404dd699e6935f416a3ed`.

## Corrections

| Boundary | Finding and evidence | Source correction | Verification |
| --- | --- | --- | --- |
| glTF/GLB import dependencies | `render_file_ops._gltf_dependencies` previously returned immediately for `.glb`. Binary GLB can contain external buffer/image URIs, and the native glTF importer identifies its container by magic bytes. Traversal, absolute paths, symlinks and renamed JSON could bypass Render's dependency preflight. | Both extensions now receive bounded, magic-based JSON inspection before the native importer. The GLB header/version/length and JSON chunk are checked without loading the binary payload. External URIs receive the existing scoped-file validation. Embedded buffers remain supported. | New fixtures first failed against the old guard, including absolute/traversal/symlink GLB references. File operation and file contract tests pass after the correction. This is a preflight test, not a native decoder exploit test. |
| Download URL literals | The old Java guard compared `getHost()` with `::1`, but Java preserves IPv6 brackets. It also accepted `localhost.`, private/link-local literals and alternative numeric IPv4 forms. The existing intended policy was `LOCAL_NETWORK_SOURCE_UNAVAILABLE`. | `FileTransferSources` normalizes brackets/root dots, rejects local/reserved literal ranges and ambiguous numeric IPv4 forms, and is called for enqueue, URL refresh and each redirect hop. It does not perform hostname DNS lookups during offline validation. | Four tests compile and run the production helper on JDK 17. Three test groups demonstrably failed before correction and pass afterward. A separate Android transfer test covers rejection through enqueue/refresh; Android execution of that test is not part of the local evidence below. |
| Cloudflare request bodies | `bodyJson` and `bodyForm` called `req.text()` before checking size. Oversized unauthenticated requests could be buffered beyond the application limit before returning 413. | A streaming reader enforces the 512 KiB JSON / 16 KiB form byte limits before decoding/retaining each chunk, cancels oversized streams, and rejects excessive declared lengths early. Missing or false Content-Length does not bypass the byte counter. | Eight Node tests run the production `fetch` handler with only the Cloudflare base class/storage adapter stubbed. Four streaming cases failed before correction. All eight pass, including split UTF-8, exact-limit input, anonymous authorization denial and foreign-origin consent denial. The source review itself did not deploy the Worker; the subsequent verified 1.0.2 deployment is recorded above. |
| Embedded `.blend` scripts | Automatic execution depended on existing native preference/default behavior. This is a hardening finding, not evidence that an imported malicious script actually executed. | Startup explicitly sets `use_scripts_auto_execute=False` and refuses to register the executor if that switch is absent or cannot be set. Both automated session-open calls explicitly use `use_scripts=False`. No `save_userpref` operation was added. Owner-invoked trusted scripting remains a separate native-editor action. | Host tests verify the preference transition and rejection before timer registration. The final native APK still requires device verification of startup and imported-file behavior. |

The creator-suite queue's additional session/scene binding was also reviewed. An accepted plan is checked against the current in-process session and retained Blender Scene ID before checkpointing or native mutation. A mismatch becomes `needs_review`; the existing crash barrier still prevents automatic replay. The real creator integration test includes post-submission scene-switch and simulated-session-change cases. This source review does not itself count that Blender integration test as executed.

## Scope and retained protections

The review followed the Android-to-Blender command boundary, explicit file imports, dependency ZIP extraction, asset download/resume paths, native runtime extraction/packaging, Binder callers, relay authentication and credential storage. Relevant modules include `VideoStudioNativeBridgeService`, `AgentPolicy`, `AgentHttp`, `VideoStudioMcpTransport`, `AgentSecrets`, `FileTransfers`, `FileBundles`, `ProductionFiles`, `EditorLaunchActivity`, `EngineRuntimeSeal`, `render_file_contract`, `render_file_ops`, `render_asset_library`, `render_asset_sources`, `render_agent_startup`, `render_session_tools`, `relay/core.py`, `relay/app.py`, and the direct Cloudflare Worker.

Observed protections retained by these changes:

- Native command routes use typed allowlists and bounded arguments; no remote Python source, shell command or arbitrary `bpy` operator route was introduced. Fixed bundled modules still load through Python's normal import mechanisms.
- The Binder bridge uses Android's system-supplied sender UID, resolves it to the installed VideoStudio package, and requires the owner-enabled local bridge. Queues are bounded and results are journaled.
- Android relay transports retain HTTPS certificate verification, finite timeouts, bounded replies and no redirect forwarding of device authorization headers. Device credentials are encrypted with Android Keystore AES-GCM; the app disables backup. Public Render IDs are not authentication credentials.
- The Python relay retains S256 PKCE, allowlisted callbacks, single-use link/enrollment codes, hashed bearer credentials, device/resource/scope binding, refresh rotation/reuse revocation, CSRF-bound consent and per-device job authorization. The relay does not execute Blender.
- Explicit originals remain content-addressed and hash-checked. Bundle paths reject traversal/symlinks; Java extraction checks entry counts, expanded size, CRC and hashes. Asset downloads restrict HTTPS hosts/redirects and preserve original bytes, size checks and available provider digests. SHA/CRC prove identity or corruption detection, not that content is harmless.
- Runtime installation uses a private staging directory, canonical path containment, an expanded-byte ceiling and atomic activation. Runtime seals are cache-identity evidence; the existing fast path does not re-hash every unpacked file.

## Packaging, dependency and secret observations

The engine assembly pins the upstream Android engine APK to SHA-256 `3fe775a1e14470ebfcd3c25ae32b57003433f04552f896880631ae98b1f18aea` and size 286,561,495 bytes. It pins the source checkout to `d93bd33cba768e19ee4387a31c0ea137ee2f0047` from `simfeo/blender`. These checks prevent silently substituting different input bytes. They do not establish that this precompiled engine was reproducibly built from that source, or that its native libraries contain no vulnerabilities or malicious behavior.

At the time of inspection there were no tracked APK/SO/JAR/AAR/ZIP/BLEND or signing-keystore files in this repository. The external precompiled engine was not available for a binary malware/signature scan in this review. Runtime source searches found the expected fixed native library loads and Vulkan dynamic-library discovery; no command-derived shell/process execution was identified in the inspected application modules.

The five direct Python relay requirements are version-pinned. Their transitive dependencies are not fully hash-locked. Tests installed those declared requirements into an isolated temporary environment; this was not an advisory-database or dependency malware audit. Gradle/test dependency declarations and engine-origin pins were inspected without replacing the trust policy or changing owner signing.

A working-tree signature search for PEM private keys and common GitHub/AWS/OpenAI credential formats returned no matches. This narrow search is not a complete secret scanner and did not audit Git history, external CI secrets, the live relay, the installed VideoStudio app or the owner's device. No credential values were printed by the review.

## Verification performed

```sh
PYTHONPATH=full-app/scripts:tools python -m unittest \
  tools.test_asset_library tools.test_asset_sources \
  tools.test_file_contract tools.test_file_ops \
  tools.test_blender_bpy_bridge tools.test_native_autonomy_security \
  tools.test_transfer_source_policy -q
```

Result: **63 passed**. This includes the real JVM literal-address policy checks; the Blender bridge tests use `bpy` fixtures and do not prove Android execution.

```sh
PYTHONPATH=relay /tmp/render-security-050-venv/bin/python \
  -m unittest discover -s relay/tests -v
node --test tools/test_direct_mcp_security.mjs
node --check cloudflare/render-studio-direct-mcp/src/index.mjs
```

Results: **41 relay tests passed; 3 PostgreSQL tests skipped** because no integration DSN was supplied. **8 Node tests passed**, and Worker syntax passed. Edited security files passed `git diff --check`.

The Android/Robolectric suite, a signed final APK, hardware/ADB execution, authenticated live Worker behavior, PostgreSQL integration, native decoder fuzzing, engine binary analysis, network penetration testing and a complete dependency advisory scan are outside this local evidence. Build/packaging and creator-native integration evidence belong to the release's separate QA record.

## Remaining boundaries

- Download hostname resolution still belongs to `HttpsURLConnection`. A public-looking hostname can resolve or later rebind to a private address. The literal guard is **not a complete SSRF sandbox**; it intentionally keeps public hostnames queueable offline.
- Package-name/UID validation does not pin the VideoStudio publisher's signing certificate. A trusted installation source remains part of the existing local bridge trust model; no certificate identity was invented during this review.
- Native `.blend`, OBJ, FBX, USD and other importers run in Blender's process and may resolve file dependencies themselves. These app-level controls are not an OS sandbox for native decoders or all external references. Disabling automatic Python does not make malformed native files safe and does not prevent an owner from explicitly running a script.
- Startup policy takes effect when Render's bundled startup module runs. This review does not claim protection against code that executes earlier in a modified native engine or a compromised existing runtime. APK pins, signatures, source review and runtime seals have different scopes.
- The corrected Cloudflare body reader protects only a deployment containing the corrected source. The 1.0.2 deployment above contains the corrected source; no live authentication state was changed.

Upstream behavior reference: the Khronos glTF importer reads both JSON and GLB and resolves URI resources in [`gltf2_io_gltf.py`](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/addons/io_scene_gltf2/io/imp/gltf2_io_gltf.py). Blender documents `use_scripts` on [`wm.open_mainfile`](https://docs.blender.org/api/current/bpy.ops.wm.html). These references explain the relevant format/API behavior; they are not an audit of the pinned Android binary.
