# ChatGPT x Render activation and current implementation

The Android launcher now opens the user-owned native agent page. It supports one-time device enrollment, Android-Keystore encrypted credentials, temporary OAuth phone link codes, Start, Stop, revocation, journal history, and a local native self-check. Existing project import/inspection remains available through the project-inspector button. The native registry is shared with the actual JNI implementations and advertises unavailable Blender editing/rendering actions honestly.

The relay implements authenticated MCP HTTP, S256 PKCE OAuth, audience/scope binding, device isolation, refresh-token rotation/reuse revocation, durable SQLite command delivery, FIFO ordering, idempotency, cancellation, and result acknowledgments. It does not render or evaluate Blender scenes. A receipt is not native execution evidence.

## Deployment requirements

Deploy this repository's root Dockerfile from the feature branch, one replica, with a persistent volume mounted at `/data`. Set `DATABASE_PATH=/data/render-relay.sqlite`, `PUBLIC_URL` to the service's exact HTTPS origin, and `ENROLLMENT_SECRET` to a new cryptographically random value of at least 32 characters. Never put those credentials in Git or build artifacts. The enrollment secret is consumed once. A new device requires explicit rotation by the owner, not a public reset API.

Health is `/health`, OAuth resource metadata is `/.well-known/oauth-protected-resource`, MCP is `/mcp`. Health being online does not mean an Android executor is paired or available.

The owner installs the agent-enabled APK, opens ChatGPT x Render, enters the exact HTTPS origin and one-use enrollment secret, and pairs the phone. The app shows a temporary 10-minute ChatGPT link code. Connect ChatGPT's custom MCP integration to the `/mcp` endpoint and enter that temporary code on this relay's OAuth authorization page. Then enable the native session on the phone. Android notifications are required so Stop remains visible.

First real acceptance test: ChatGPT reads device status/capabilities, submits `engine.status`, polls that exact job until the phone returns a result, lists only imported Render projects, inspects one explicitly selected opaque project ID, and then proves Stop/Revoke prevents further work. No live end-to-end claim is permitted until this is observed on the owner's phone.

## Current deployment blocker

Railway connection is authenticated and workspace lookup works. The attempted new private project creation returned `Deploys have been paused temporarily`; no project, endpoint or deployment was created by that call. Code and APK build progress are separate from this hosting-provider blocker. Phone pairing and physical-device tests remain outstanding.

## Development APK caution

CI debug APKs are development builds. A debug signing certificate can differ between CI runners unless a durable signing key is provisioned. Do not uninstall an existing Render installation without exporting/backing up imported projects: app-specific files and encrypted credentials can be removed by uninstall. The current feature branch must not be merged into main or called a production release based on compilation alone.
