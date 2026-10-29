# Render Studio 0.61 — Dedicated MCP, no VideoStudio carrier

Render Studio 0.61 keeps the full Blender-based 0.60 Animation Studio
and its local sculpting, creation, rigging, frame rendering, project folders,
durable native receipts, checksums and Storage Access Framework imports.

## Connection and privacy
- Android package remains `com.rezox.render`; monotonic `versionCode 62`.
- The **only** remote command transport is the existing dedicated Render Studio
  Cloudflare Worker at
  `https://render-studio-direct-mcp.prakasharuntandon634.workers.dev/mcp`.
- No dependence on VideoStudio, its Binder service, MCP worker, private owner
  credential or shared registration. No unrestricted local HTTP server.
- The public Render app ID remains unchanged in app preferences; it is not a
  credential. Existing Android project files and local journals stay put.
- Direct MCP pairing uses the Worker's one-use enrollment secret; device token
  is encrypted with Android Keystore, session is explicitly started and stopped,
  and jobs are journaled before the phone executes native work.
- If the previous app was paired through VideoStudio, the old transport is
  **disabled** on first start. Pairing directly replaces only its credential
  after successful enrollment. Never uninstall or clear app data to migrate.
- The ChatGPT-facing MCP connector itself still must be authorized using the
  phone-generated short-lived link code.

## Owner sequence
1. Install the same-signed APK **as an update**, without uninstalling.
2. Open **Render > Agent Control > Pair this device**. The correct HTTPS MCP
   endpoint is already displayed. Enter the one-use enrollment code of the
   existing Render Studio Worker (not a VideoStudio or ChatGPT secret).
3. Authorize the Render Studio MCP in ChatGPT using the generated one-use
   link code and tap **Start Agent Session** on the phone.
4. In ChatGPT use `render_status`, `render_capabilities`, `render_submit`,
   `render_job` and `render_cancel`. Submit only supported native actions;
   an accepted job is not a completed Blender render. Inspect the device's
   journal and the job result for real completion evidence.

If an old one-time enrollment code was already consumed, that Worker must be
provisioned with a new one before another Android device can enroll. Never
embed enrollment secrets or credentials in the APK, commits or shared setup card.

## Build verification
The dedicated release workflow checks source identity, host contracts,
real desktop Blender semantics, Android unit tests, full pinned ARM64 engine,
compiler output, complete APK modules, historical development signing certificate,
and the absence of the obsolete Binder service and VideoStudio package visibility.
It publishes a development prerelease only after the verification gates pass.
A green workflow is **not** a physical Android installation or GPU/thermal
endurance test. In-place installation still requires a matching installed signer.
