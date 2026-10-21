# ChatGPT x Render implementation plan

> Execution: native inline work in the existing feature branch. No merge to main.

**Goal:** ship the authenticated relay and Android action executor, and advance genuine Blender native engine prerequisites.

**Architecture:** HTTPS MCP/OAuth relay is only a durable mailbox. Android owns project data and all native execution. A shared typed action registry exposes only existing implementations; missing Blender operations are reported unavailable.

**Tech Stack:** Java 17, Android API 28–35, NDK 27/C++20, Python 3.13, FastAPI, SQLite, PKCE OAuth and MCP 2025/2026 HTTP.

**Spec:** docs/superpowers/specs/2026-10-21-chatgpt-render-agent-bridge-design.md

## Constraints
No mandatory desktop or cloud Blender, no main merge, no secrets in source, no broad phone/gallery access. Relay enrollment is single-use. Commands must be scoped to app-owned imported projects. Stop/revoke and durable recovery are mandatory. Missing rendering/modeling engine handlers cannot be reported as implemented.

## Tasks
1. Restore the interrupted native action registry, secure credentials and durable command journal from the preserved Git tree. Add Java policy/path regression tests and real SQLite/HTTP relay tests.
2. Finish Android foreground-service executor, pairing/authorization UI, cancellation and JNI integration. The UI and native executor must use the same native handlers. Build ARM64 APK and run existing + agent unit tests.
3. Add deployment manifests, protected OAuth metadata and supported MCP request flows. Exercise enrollment, pairing, token renewal/revocation, queue idempotency, delivery, result acknowledgment and cross-device isolation.
4. Port original Blender guardedalloc and remove the temporary compressed-reader allocator shim where verified. Compile it on Linux and Android and exercise real allocator accounting/alignment/reallocation.
5. Run CI, update PR with exact evidence, deploy only if Railway permits. Verify live end-to-end only after owner installs APK and completes phone pairing. Keep deployment/phone verification explicitly blocked when unavailable.

## Review focus
Expired credentials must not execute; replay must not duplicate work; paused/revoked sessions must not start the next native call; project selection must reject symlinks and traversal; output labeled native must originate from native execution. A crashed non-interruptible native call requires recovery, not silent replay.

## Progress
- User approved architecture and requested direct execution with Blender work alongside it.
- Railway connector is now authenticated; list-projects returned no projects. create-project returned `Deploys have been paused temporarily`; no relay project or deployment was created.
- The prior branch still held only the design spec. Preserved orphan implementation trees are being integrated, not claimed as previously deployed.
- Baseline native version 0.8 was built in earlier CI; no new bridge APK or phone run is yet verified.
