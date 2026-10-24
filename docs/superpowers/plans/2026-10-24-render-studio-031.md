# Render Studio 0.31 Implementation Plan

Goal: harden the existing native Android Blender studio without changing the engine, project semantics, artist quality, private credentials or existing VideoStudio transport.

Architecture: retain the latest native-control branch and merge the existing storage/export improvements. Extend the current app-private Python spool, SQLite command journal, immutable render manifests, Android foreground service and in-Blender panels. All artist work stays on native Android Blender. No runtime, scene generation, benchmarks or test suites are authorized for this task.

- [x] Retain branch improvements and repair deterministic build preparation; version the original package monotonically.
- [x] Strengthen startup diagnostics/readiness and prevent overlapping launch/extraction attempts.
- [x] Persist queued Binder work before dispatch, retain exact-ID results and protect against duplicate/uncertain mutations; expose status and cancellation without blocking behind a render.
- [x] Add durable render queue controls and truthful elapsed/estimated remaining progress; retain completed frames on pause/cancel/retry and obey Android foreground-service quotas.
- [x] Separate preview/final settings, preserve omitted settings, avoid repeated scene setup and cache invalidation, and improve Android thermal telemetry sampling and memory admission.
- [x] Broaden discoverable structured native artist operations with checkpoints, and retain the actual-action pointer/HUD.
- [x] Extend existing free asset catalog discovery/metadata/previews, robust downloads and explicit file import without Gallery access.
- [x] Build the full ARM64 APK, verify package/version/native payloads/signature, deliver source/release notes and disclose signing and runtime limitations.

Verification: compile Java/C++/Python, assemble APK and inspect its manifest, runtime payload, ZIP integrity and certificate. Do not run test suites, install the app, execute Blender, model/import/render/capture/encode, or claim measured performance/24-hour success. If the original private signer is unavailable, label any separately signed installable artifact as a development build that cannot update the installed app; also retain an unsigned original-package APK for owner signing.

Review focus: process death between queue acceptance and dispatch; uncertain native mutations; same-process activity replacement; output-quality preservation; unavailable thermal/memory signals; long frames at Android quota expiry; interrupted asset downloads; symlink/path boundaries; provider failures with original data retained.


Execution record: existing branches retained in merge 89a6b6b. New engineering
implementation d098f49 and recovery/quality fixes 861934c. A fresh static review
found six recovery/quality issues; fixes were inspected and compiled without
executing prohibited tests. Both foundation and full-native APK assemblies passed
locally. Historical signing is attempted by the dedicated build-only CI job; the
artifact evidence, rather than this plan, records its final certificate/result.

Rulings: the explicit user instruction overrides test/benchmark/runtime workflows;
all validation is compilation, static review and package/signature inspection.
Native Activity ownership, Android quota/force-stop behavior, context-dependent
operators, finite catalogs and HDR durable-job limits are disclosed in release notes.
