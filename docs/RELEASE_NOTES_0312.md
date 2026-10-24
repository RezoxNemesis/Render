# Render Studio 0.31.2 — native startup storage

Package `com.rezox.render`, versionCode **38**. Retains the 0.31.1 engineering
upgrades, native Blender libraries, project compatibility and render settings.

Real Android workspace testing exposed an input-dispatch ANR while the native
activity opened its startup log in shared Downloads storage on the UI thread.
Startup log/output storage is now prepared by the existing background loader.
The native activity publishes an already prepared private log path without
probing shared storage. The previous private startup log is retained, and both
current and previous logs are available to diagnostics. Existing explicit
Blender output paths and native output-directory overrides are preserved.

Runtime extraction now buffers archive reads and checks the free-space reserve
at bounded 4 MiB intervals instead of querying storage for every inflater chunk.
Progress updates include bytes during large files and are limited to one update
per two seconds. Archive validation, staging/rollback and the 64 MiB free-space
reserve remain. No scene detail, samples, textures or output quality is reduced.

The fixed workspace integration fixture creates an editable glazed ceramic mug,
metal base, lighting, keyframes and explicitly selected preview jobs through
Render's native operations. The build workflow emits a matching signed test APK;
a differently signed local runner was correctly rejected by Android.

Validation completed before the candidate build: Android foundation compilation
and seven focused native-assembly checks. Native modelling/rendering acceptance
remains pending until actual native receipts and output files are obtained.

The first software-emulator attempt reached Blender's Vulkan device checks.
SwiftShader lacks the geometry-shader feature required by the bundled engine;
the native engine then crashed. A Lavapipe emulator attempt follows. These
workspace results do not establish realme compatibility, performance, thermal
behavior or uninterrupted 24-hour execution. No owner phone was used.
