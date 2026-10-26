# Render Studio Direct MCP (Cloudflare Worker)

This Cloudflare Worker is **separate from the VideoStudio MCP**. It reuses the standalone Render Studio Android agent's existing /v1/device protocol and runs its command mailbox in a SQLite-backed Cloudflare Durable Object.

- **Deployed origin:** https://render-studio-direct-mcp.prakasharuntandon634.workers.dev
- **ChatGPT MCP URL:** https://render-studio-direct-mcp.prakasharuntandon634.workers.dev/mcp
- **Health (relay only):** /health
- **OAuth:** RFC 9728 protected-resource metadata, OAuth authorization-server metadata, S256 PKCE, dynamic client registration (DCR), access and rotating refresh tokens, device-linked authorization and token revocation
- **Tools:** render_status, render_capabilities, render_submit, render_job, render_cancel
- **Android API:** POST /v1/device/enroll, /v1/device/link, /v1/device/poll, /v1/device/result and /v1/device/revoke
- **Execution:** all Blender operations execute on the paired Android app; this Worker never runs Blender or manipulates the phone directly

## Install on Android (one-time)

A compatible Render Studio Android build is required. In Render Studio → ChatGPT × Render, expand **Optional Cloud Pairing / Advanced** (older APKs call it **Optional / Old Independent Relay**). Paste the **HTTPS origin WITHOUT /mcp** into the Relay field. Paste the private, one-use enrollment code provided by the Cloudflare Worker owner, then tap **Pair This Device**. Do not share that enrollment code, the device token, or the resulting temporary ChatGPT link code in a conversation.

**The Worker cannot activate Android permissions or install an APK remotely.** Pairing must be approved on the device. No VideoStudio app, VideoStudio key, or VideoStudio service is needed for this standalone relay transport. If the Render app currently holds a different active pairing, the user needs to revoke it locally before pairing this new endpoint.

## Connect in ChatGPT (web)

1. On ChatGPT web, navigate to Plugins → (+) → Add custom MCP server. Enter the **/mcp** HTTPS URL above.
2. Choose **OAuth** authentication, using dynamic client registration (DCR) if the UI asks. Do not choose unauthenticated access.
3. Begin authorization. In Render, tap **Generate ChatGPT Link Code** (10-minute single-use).
4. Enter that **link code in the Worker's OAuth authorization page**, not into the chat conversation. Finish ChatGPT OAuth connection.
5. On Render, tap **Start Agent Session**; Android notifications must be enabled for the foreground service.
6. Test: render_status → render_capabilities → render_submit(request_id, action=engine.status, args={}) → render_job(job_id) until there is a native result. Stop/Revoke controls remain available in Render.

Notes:
- ChatGPT full read/write MCP access depends on the user's subscription/workspace permissions. Custom MCP setup is currently on ChatGPT web, not Android native UI.
- OAuth and the persistent relay can remain online while the device is offline, but **commands cannot run without the compatible Android executor**. A queued job is NOT execution evidence.
- Jobs are restricted to actual native capabilities, validated again by Android; no arbitrary shell, Python, Gallery browsing, or control of other Android applications.
- New enrollment secrets are one-time. To pair a second/replaced device, rotate the ENROLLMENT_SECRET Worker secret and redeploy/enable a fresh enrollment (old enrolled secret stays consumed).
- Cloudflare Workers and Durable Objects may incur usage-based billing depending on account plan and usage. No paid AI inference service is used.

## Worker configuration

The source is in src/index.mjs, and the Wrangler configuration is in wrangler.jsonc. The Worker uses one SQLite-backed Durable Object. Set the enrollment secret using Cloudflare's secrets interface; never commit it.

To deploy manually after updating source:

    npm install --global wrangler
    wrangler deploy
    wrangler secret put ENROLLMENT_SECRET

For REST API deployments the Durable Object migration v1 is represented by the multipart metadata object's new_tag/new_sqlite_classes structure. Wrangler uses migrations array instead.

## Security invariants and acceptance gates

- HTTP clients and native Android phone use **different credentials**.
- OAuth access binds device, resource (= exact /mcp URL), scope and expiry.
- Registration accepts only ChatGPT HTTPS OAuth callback URIs.
- Device enrollment requires a single-use 32+ character random secret.
- Consent requires a temporary code generated on the enrolled Render device.
- MCP tools are authenticated; /mcp rejects anonymous access with 401.
- Execution checks actual installed action capability and Android-side permissions.
- Jobs have stable request IDs, canonical SHA-256 digests, FIFO ordering, durable results, retry-safe final receipt handling and recovery states.
- Before claiming connected, verify an actual native result from the phone; /health alone only establishes deployed relay availability.
