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

## Verified-copy project saving (pending physical-phone test)
The native action `blender.project.save_copy` uses actual Blender `bpy.ops.wm.save_as_mainfile` with `copy=True` and lossless compression, saves a new UUID-named `.blend` in Render's app-private Projects directory, verifies that the open project's path remains unchanged and hashes the resulting bytes. The action never takes a caller-supplied absolute path and never overwrites an existing named project. After native success, the Android agent resolves the file to an opaque `project_id` for later `projects.inspect`. Relative external dependencies are remapped by Blender, but not automatically packed. Importantly this is a saved .blend scene, not an MP4 render, and scenes that take over the action's 120-second Android timeout can require recovery; no automatic replays of uncertain writes are permitted.

## Editor black/empty screen recovery — Android preloader
A separate `EditorLaunchActivity` now runs native-library preflight and extracts Blender's full Python/scripts/assets bundle on a worker thread **before** launching the upstream Vulkan NativeActivity. The original upstream launcher extracts synchronously before `super.onCreate`, which can look like a black/frozen screen on first launch; the new loader shows progress and builds the exact installed-version marker upstream expects. It stages updated runtime files before swapping them into place, and keeps startup-state breadcrumbs. Native editor logs can be viewed, copied or explicitly shared from the new diagnostics screen. The loader **does not claim to fix unsupported GPU/driver crashes**, which require a real device log; if the viewport remains black after resource extraction, collect the new diagnostic report. No resolution/texture/quality downscaling was introduced.


## v0.12 VideoStudio MCP shared transport
Native Render is a second authenticated Android executor beneath the existing VideoStudio v3 Worker and connected ChatGPT MCP. The owner enters a one-use code obtained from the existing VideoStudio MCP; the original private owner key never leaves VideoStudio. The Worker runs no Blender code, and VideoStudio's original projects and queue remain separate. The Worker additive channel must be deployed and the Render phone paired and started before native command results are possible. See docs/AGENT_ACTIVATION.md.

## v0.13 — same-phone VideoStudio Native Agent IPC
An owner-enabled Binder Messenger in Render receives typed operations only from Android's UID-verified VideoStudio package. The existing VideoStudio MCP v3 Worker needs no update for this fallback: ChatGPT talks to the installed VideoStudio Native Agent, which forwards authorized Render actions on-phone. Render does all Blender modeling, animation and file handling locally and returns results to VideoStudio for its MCP completion. No VideoStudio owner credential or project media is transferred. The separately queued Cloudflare Worker Render child-device feature remains experimental until deployed. Device smoke testing is still required.


## v0.14 professional connection screen and app identity
The Render native connection screen exposes CONNECT / SHARE WITH CHATGPT, SHARE RENDER CONNECTION, COPY RENDER APP ID, CHECK VIDEOSTUDIO APP and STOP VIDEOSTUDIO BRIDGE. It can query only the known VideoStudio Android package via an explicit package visibility declaration, requiring v3.5.0+ for the typed Binder forwarding route. The public Render UUID is preserved across compatible APK updates and included with native receipts, while the original VideoStudio MCP owner key is never copied to Render. A local ready switch is not proof of remote/native completion: only the first authenticated native result confirms the bridge actually executed. Screen recording remains enabled, while enrollment secrets stay masked. See docs/AGENT_ACTIVATION.md.

## v0.16 Blender-native ChatGPT operations
The bridge now supports real Blender mesh primitive creation, native cameras, point/sun/spot/area lights, subdivide/bevel/solidify/mirror modifiers, Principled BSDF material assignment, exact render resolution/sample/engine settings and PNG still rendering to Render's app-owned `Renders` folder. These are actual `bpy` actions, not illustrative mockups. Validation runs at the shared MCP Worker, in Android Java and inside Blender Python. The phone must run the editor for bpy actions, and rendering remains entirely on the device. Timeouts and CPU/GPU limitations still apply. VideoStudio and Render project stores remain separate. Not all Blender GUI/Python capabilities are automated yet; actions are registered as their native handlers gain tests.
