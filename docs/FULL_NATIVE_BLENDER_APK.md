# Render Full Native Blender APK — experimental unified installer

One Android APK containing the actual full Blender libblender.so and runtime files
plus Render's own ChatGPT command agent. Native 3D work stays on the phone.

## Pinned provenance
- Engine: simfeo/blender Android Full alpha-4, pinned source d93bd33cba768e19ee4387a31c0ea137ee2f0047.
- Release: https://github.com/simfeo/blender/releases/tag/android-alpha-4
- SHA-256: 3fe775a1e14470ebfcd3c25ae32b57003433f04552f896880631ae98b1f18aea
- Engine APK size: 286561495 bytes.
- Matching GPL-licensed Android Java/resources are taken from pinned source.

## What the integrated project does
The existing Render Android native JNI application is compiled, then the pinned upstream
Blender APK is validated byte-for-byte and its actual native arm64 libraries and assets
are staged into the Full Android Studio Gradle application under full-app/.
The original BlenderActivity is kept, and the launcher becomes RenderHubActivity.
An explicit button opens the complete native Blender editor, while the same APK also
contains Render's ChatGPT-agent Activity, service, project-import and diagnostics.

## Important limits
Native agent tools currently list and inspect app-owned Blender projects and query Vulkan.
They do not yet control Blender's bpy or render engine; that requires a separate native
engine-to-agent operation bridge with main-thread serialization and device verification.
This full editor is an unofficial upstream alpha and may be incompatible with some mobile
Vulkan GPUs, thermal conditions, and memory limits. It must be tested on a phone.

The applicationId is com.rezox.render, which replaces prior versions if certificates
match. Debug signatures may differ across CI runs; preserve project backups before
uninstalling any existing Android build. The original Blender Android editor requests
all-files access for linked assets; Android's platform permission prompt remains required.
Original Blender and all related GPL source remain available from the pinned source;
the Render agent source and packaging scripts are in this repository.
Do not claim full desktop parity or a production release solely from APK compilation.
## Native bpy main-thread command bridge
The Full-APK staging pipeline adds a Render startup Python module to Blender's normal scripts/startup directory and patches the pinned BlenderActivity to publish an app-private command-spool path. The module registers a Blender main-thread timer and accepts only typed scene.summary or object.add_cube commands, without exposing Python eval or a network listener. The agent and original Blender editor remain in the SAME Android APK and process. Python startup and Java commands require real on-device verification; CI verifies generated code and deterministic unit logic, not a physical Blender action.

## On-device animation command vocabulary
The typed native action registry now includes `blender.scene.set_frame`, `blender.object.set_transform` and `blender.object.keyframe`. Arguments are schema-validated in the authenticated relay, validated again in Java and inside Blender Python. The agent can create a cube, transform an object and insert location/rotation/scale keyframes in Blender's own scene database, with a native result. No arbitrary Python source, filesystem path or shell action can be submitted. No automatic project save or video rendering is implied. Actual Android GPU/device execution must still be tested.
