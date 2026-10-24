# Native command configuration across Android ABI translation

The Android workspace engine completes `WM_init` with the timeline counter fix.
The command heartbeat was initially absent. Read-only native debugger inspection
of the ARM guest libc environment confirmed that `RENDER_AGENT_SPOOL` and
`RENDER_MOBILE_UI_MODE` were absent, although the Java NativeActivity publishes
both before engine startup. The native bridge maintains a separate environment
snapshot. This workspace observation is not a diagnosis of the physical phone.

Version `0.28.4-native-launch-handoff`, Android code 34, adds a private file
handoff before NativeActivity starts. Java writes `render_native_launch.json`
with Android `AtomicFile`. The settings contain a schema version, package,
enabled flag and portrait/landscape mode. They contain no filesystem path,
command, credentials, script or operator ID.

The bundled Blender startup script derives the app's files directory only from
its exact `files/blender/<major.minor>/scripts/startup` layout. It validates the
small configuration and derives `render_bpy_jobs` locally. Invalid configuration
and a symlink spool are rejected. Existing environment configuration remains
usable when no private handoff exists. A host checkout without the handoff does
not gain a command executor. This adds no server, MCP, relay or cloud renderer.

Startup diagnostics distinguish a configured spool from the first actual
Blender timer heartbeat. Neither Java publication nor an editor launch receipt
is presented as completed native execution. The small artist cursor and render
HUD remain inside Blender and require actual editor validation.

Initial validation: 25 host bridge, packaging and pinned-engine guard tests pass,
including missing-environment recovery, wrong-package/schema/mode rejection,
symlink rejection and unchanged command validation. The build adapter passes
twice, and the complete Android APK builds and passes signature verification.
The exact production Java publisher also ran successfully inside the workspace
Android app and its configuration was read back. Subsequent Android 35 workspace
validation received the real Blender timer heartbeat, native viewport/scene
inspection results, and an actual Blender cube viewport screenshot. No debugger
pointer repair was used on that corrected cold start. The 0.28.4 test used exact
verified packaged engine/runtime overrides in the isolated workspace; it was
not an owner-phone update. Physical-phone validation remains pending.

Version 0.29.0 additionally publishes the recovered guest Python environment
before companion UI modules import it, and binds readiness to the live Android
process ID. Its whole APK was installed in the workspace emulator; see
[the 0.29.0 validation boundary](V029_NATIVE_STUDIO_UPGRADE.md).
Workspace APKs use a separate test
signer and are not owner-phone in-place updates. No animation or likeness pass
is claimed by these engineering tests.
