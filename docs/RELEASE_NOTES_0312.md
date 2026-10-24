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

Validation: Android foundation/full-native compilation, seven focused native
assembly checks, and two targeted Robolectric checks for the UI-thread guard,
retained failure log and preserved output-directory override. The OS environment
calls use an explicit host-test shadow. These checks do not establish native
modelling/rendering success; that requires actual receipts and output files.

The first software-emulator attempt reached Blender's Vulkan device checks.
SwiftShader lacks the geometry-shader feature required by the bundled engine;
the native engine then crashed. Lavapipe passed the geometry-feature check and
reached native Python, a timer heartbeat and the Blender Quick Setup UI. The
emulator later aborted in Mesa's software-GPU memory mapping; a recovery attempt
uses fewer software-GPU workers. No model or animation output is claimed. These
workspace results do not establish realme compatibility, performance, thermal
behavior or uninterrupted 24-hour execution. No owner phone was used.
