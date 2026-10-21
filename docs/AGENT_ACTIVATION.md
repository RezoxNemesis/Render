## Direct local VideoStudio MCP → Render Android (no Worker deployment required)

This is the fastest transport to test. It requires UPDATED APKs for both VideoStudio and Render,
but no Cloudflare changes, new server, Railway, or extra ChatGPT connection.

1. Install both updated experimental Android builds. Back up app-owned projects
   before uninstalling a debug-signed app; the signing certificate can change.
2. In Render → ChatGPT × Render, choose ENABLE DIRECT VIDEOSTUDIO BRIDGE and
   approve the local prompt. This bridge defaults OFF and can be stopped locally.
3. Use the original VideoStudio MCP in ChatGPT. Request action
   render.engine.status using the existing app_execute or queue_video_edit
   compatibility action. The Worker sends it to VIDEO STUDIO's original queue.
4. The VideoStudio foreground Native Agent sends the typed command through
   an explicit Android Binder Messenger to Render. Render checks the Android
   kernel-reported sending UID against com.rezoxnemesis.videostudio and verifies
   the owner-enabled local bridge before executing actual Render operations.
5. Render sends native result/evidence back through Binder. VideoStudio returns
   the result through the ORIGINAL MCP command-result tool. A queued receipt
   is not a verified completed Blender operation.

Both applications retain independent project stores. VideoStudio owner keys
are never transferred to Render, and no Gallery browsing or arbitrary Python
execution is exposed. Render uses a durable job journal and does not replay
uncertain mutations after process death. STOP disables the on-phone bridge.

The existing Cloudflare Worker additive Render child-device route remains in
VideoStudio-MCP draft PR #142; deployment of that server-side route is NOT
required for this direct Android IPC mode. The original VideoStudio Native
Agent DOES need to be active and connected for direct IPC to execute.

Hardware and real end-to-end on-phone Binder execution remain unverified until
both APKs are installed and a native command result has been observed.

## Preferred connection: existing VideoStudio MCP v3 — no extra relay

Render shares the existing VideoStudio Cloudflare Worker and connected ChatGPT MCP,
but it keeps a SEPARATE Android device identity, queue, native execution service,
projects and encrypted credential. VideoStudio's original MCP URL, owner secret,
native editing and project data remain unchanged. Render never stores, asks for,
or displays the original VideoStudio private owner key.

One-time 10-minute code flow:
1. The existing VideoStudio Worker receives the additive Render channel update
   from VideoStudio-MCP draft PR #142. Without deployment, /api/v3/render/health
   reports 404, so phone pairing must not claim to work.
2. Via the existing VideoStudio ChatGPT MCP, request a Render pairing code.
   Compatibility tool: queue_video_edit with projectId=active-native,
   action=autonomous_request,
   parameters.nativeAction=render.pair_code, parameters.nativeParameters={}.
   The plugin's existing owner identity is supplied privately as deviceId.
3. On the Render phone, open ChatGPT x Render -> Preferred VideoStudio MCP,
   enter the 40-hex one-time code, and choose PAIR VIA VIDEOSTUDIO MCP.
   Render generates a new random Android UUID and owner key in memory and
   stores ONLY its own identity using Android Keystore encryption.
4. Tap Start Agent Session. Render polls the same Worker under its own device
   identity and executes validated native commands on this Android device.
5. ChatGPT can send a command using its existing queue_video_edit tool:
   action=autonomous_request, projectId=active-native,
   parameters.nativeAction=render.blender.scene.summary and
   parameters.nativeParameters={}. Then poll get_video_command_result with
   the returned command ID until an actual native result appears.
6. Render Stop/Revoke affects only Render, not VideoStudio.

The original VideoStudio native executor need not be awake for Render to work.
A queued command receipt is not proof that Blender executed it. This
same Worker contains only authenticated command metadata and results,
never remote Blender modeling or rendering. No Gallery enumeration, arbitrary
Python source, shell or unrestricted paths are permitted.

Legacy standalone relay setup is optional, not required by this design.
Phone pairing and a physical-device native result are pending even if all CI
builds pass. Back up app data before changing debug signing certificates.

# ChatGPT x Render activation and current implementation

The Android launcher now opens the user-owned native agent page. It supports one-time device enrollment, Android-Keystore encrypted credentials, temporary OAuth phone link codes, Start, Stop, revocation, journal history, and a local native self-check. Existing project import/inspection remains available through the project-inspector button. The native registry is shared with the actual JNI implementations and advertises unavailable Blender editing/rendering actions honestly.

The relay implements authenticated MCP HTTP, S256 PKCE OAuth, audience/scope binding, device isolation, refresh-token rotation/reuse revocation, durable SQLite command delivery, FIFO ordering, idempotency, cancellation, and result acknowledgments. It does not render or evaluate Blender scenes. A receipt is not native execution evidence.

## Legacy standalone deployment requirements

Deploy this repository's root Dockerfile from the feature branch, one replica, with a persistent volume mounted at `/data`. Set `DATABASE_PATH=/data/render-relay.sqlite`, `PUBLIC_URL` to the service's exact HTTPS origin, and `ENROLLMENT_SECRET` to a new cryptographically random value of at least 32 characters. Never put those credentials in Git or build artifacts. The enrollment secret is consumed once. A new device requires explicit rotation by the owner, not a public reset API.

Health is `/health`, OAuth resource metadata is `/.well-known/oauth-protected-resource`, MCP is `/mcp`. Health being online does not mean an Android executor is paired or available.

The owner installs the agent-enabled APK, opens ChatGPT x Render, enters the exact HTTPS origin and one-use enrollment secret, and pairs the phone. The app shows a temporary 10-minute ChatGPT link code. Connect ChatGPT's custom MCP integration to the `/mcp` endpoint and enter that temporary code on this relay's OAuth authorization page. Then enable the native session on the phone. Android notifications are required so Stop remains visible.

First real acceptance test: ChatGPT reads device status/capabilities, submits `engine.status`, polls that exact job until the phone returns a result, lists only imported Render projects, inspects one explicitly selected opaque project ID, and then proves Stop/Revoke prevents further work. No live end-to-end claim is permitted until this is observed on the owner's phone.

## Current deployment blocker

Railway connection is authenticated and workspace lookup works. The attempted new private project creation returned `Deploys have been paused temporarily`; no project, endpoint or deployment was created by that call. Code and APK build progress are separate from this hosting-provider blocker. Phone pairing and physical-device tests remain outstanding.

## Development APK caution

CI debug APKs are development builds. A debug signing certificate can differ between CI runners unless a durable signing key is provisioned. Do not uninstall an existing Render installation without exporting/backing up imported projects: app-specific files and encrypted credentials can be removed by uninstall. The current feature branch must not be merged into main or called a production release based on compilation alone.
