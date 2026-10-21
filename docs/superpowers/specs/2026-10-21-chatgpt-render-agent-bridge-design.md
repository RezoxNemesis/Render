# ChatGPT x Render — Autonomous Native Agent Bridge

Status: PROPOSED DESIGN FOR USER REVIEW. This document does not implement or activate a connection.

Baseline inspected: `ac8606e3a7071a7204fb21d8103fe6f303bd483e`, Render foundation v0.8.0-zstd-native, draft PR #1. Do not merge into main as part of this feature.

## User intent and non-negotiable requirements

The owner wants to give natural-language commands in ChatGPT and have Render carry out complete workflows on the Android phone, rather than merely receiving instructions to operate the UI manually. They expressly authorize broad autonomous work inside Render, including access to every implemented app function. The interface must not become a deliberately reduced subset of the native app.

Render remains separate from VideoStudio. Computation, scene evaluation, animation, simulation and rendering must execute on Android when those engines are available. No required desktop computer, remote Blender instance, streaming desktop, or cloud renderer. An optional network service may carry commands, status and explicitly requested output; it must not substitute cloud execution for native execution. The existing VideoStudio private endpoint and pairing identity must not be changed or reused as Render credentials.

Google Drive remains an optional asset library and backup destination, not the command execution engine. Gallery browsing, broad phone filesystem access, and control of unrelated apps are outside this bridge. Imported app-owned projects and individually granted document-provider resources are the permitted file scope.

## Architecture decision

Recommended: authenticated remote MCP transport plus an Android-owned execution agent.

`ChatGPT -> authenticated HTTPS MCP service -> durable command queue -> outbound Android connection -> Render native action dispatcher -> native result/evidence -> ChatGPT`

A relay is a mailbox and transport service, not a rendering workstation. The phone initiates outbound authenticated connections, avoiding a publicly exposed Android port and working across mobile networks. The relay can retain authorized pending commands while the phone is offline, but cannot execute them in the phone's absence.

Alternatives considered:
- Phone-only inbound HTTP endpoint: simple local development, but not a reliable ChatGPT web connection across mobile NAT, network changes or Android suspension. Not the default.
- A separate in-app AI API client: optional future addition, but not a replacement for controlling the app from this ChatGPT conversation, and not required for the first bridge.

## Authentication and pairing

The app gains a `ChatGPT x Render` screen with `Connect`, connection identity, current permission scope, `Autonomous session`, activity history, and `Stop / Disconnect` controls.

Initial setup requires a deployed reachable HTTPS MCP endpoint, installation of a compatible APK, and a one-time owner pairing/authorization action. Pairing credentials are device-specific. Store private keys in Android Keystore and encrypt persistent access credentials. Never commit tokens, device identifiers, private endpoints containing secrets, or Google Drive folder identifiers to this public repository.

ChatGPT authentication must use the supported MCP OAuth flow: protected-resource metadata, issuer metadata, authorization-code flow with S256 PKCE, exact redirect URI validation, resource/audience binding, appropriate scopes, short-lived access tokens and refresh-token rotation/revocation. Prefer an established provider rather than an ad hoc login implementation. Do not assume ChatGPT can send an arbitrary custom API key. The Android device transport uses a separate device-bound credential, not the ChatGPT OAuth token.

Pairing must expire, be single-use, and be bound to the intended device and owner. Tokens must be revocable from the app. Account/workspace controls and Android's permission dialogs remain authoritative; this feature does not bypass them.

## Native action registry: full coverage, truthful availability

Add a versioned native action registry shared by touch UI and the agent. Each action descriptor contains an action ID, input/result schema, API version, availability, required engine/module, read/write effects, cancellation support, resource scope and recovery strategy.

Every app function must be registered as its implementation becomes available. Do not create an artificial agent-only miniature editor. Model/tool access must be data-driven through this registry, not a fixed list that permanently excludes modeling, rigging or other eventual Blender operations.

Immediately executable actions are limited to what the inspected build actually contains: engine/build status, app-owned project inventory, local project inspection through native BLO/SDNA/gzip/Zstd readers, saved datablock-name previews, and Vulkan hardware diagnostics. Native file selection still follows Android's document grants.

The baseline has no complete BKE/Main scene reconstruction, dependency graph, editable 3D viewport, modeling tools, rigging, simulation or renderer. Such actions must be advertised as `unavailable` with a concrete reason, not accepted as successful or simulated. Authentication and broad permission cannot supply missing engine code.

Future integrated actions include project creation/open/save, assets and linked libraries, mesh editing, sculpting, UV/materials/nodes, rigs and keyframes, camera/light control, simulation, compositing, export and quality verification. These become callable only when real handlers and tests exist.

## MCP tools and job contract

Stable externally visible tools:
- `render_status`: live or stale device heartbeat, build version, pairing/permission state and current task; distinguish relay availability from native executor availability.
- `render_capabilities`: paginated action descriptors from the installed device, including unsupported/missing engine modules.
- `render_submit`: validated action or ordered workflow, user-request scope, request ID, expected project revision and timeout policy. Return a job receipt, never a fabricated completion result.
- `render_job`: job state, native progress, errors, evidence and artifact references.
- `render_cancel`: authenticated cooperative cancellation and prevention of further steps.

Queued jobs contain immutable `request_id`, device/session identity, action/schema version, input digest, timestamps, project ID/revision, preconditions and required capabilities. Use idempotency keys: a repeated request ID with identical content returns the existing job; conflicting content is rejected. Validate schemas and capability/permission checks both at the relay and on Android.

States: `queued`, `awaiting_device`, `running_on_device`, `waiting_for_approval`, `paused`, `cancel_requested`, `cancelled`, `failed`, `recovery_required`, `succeeded`.

The phone serializes operations that modify the same project. Durable SQLite state records accepted commands, step checkpoints and terminal results. A lost acknowledgment must not duplicate a completed write. After an uncertain crash, mark non-idempotent work `recovery_required` rather than replaying it blindly. Leases alone do not guarantee exactly-once execution.

## Autonomous workflow behavior

An owner-enabled autonomous session authorizes routine Render project operations without an extra in-app confirmation for every low-risk step. ChatGPT can plan, inspect, invoke available native operations, check native results, revise parameters, and repeat within the authorized task.

Do not let instructions embedded in assets, filenames, project metadata or logs become commands. All command authority comes from the authenticated user task, never from imported media. Expose typed app actions, not an unauthenticated shell or arbitrary Android command execution. A future Blender Python interface requires its own explicitly scoped, audited design.

Before destructive project changes, create a recoverable checkpoint and verify the target project/revision. Sharing, publishing, purchases, credential access and crossing the approved file scope are not implicitly authorized by enabling the session. Explicit user intent and platform-required approvals still apply.

A persistent activity screen shows what was requested, what ran, native errors and produced results. Provide one-tap Stop and credential revocation. Stop prevents new jobs/steps immediately and requests cooperative cancellation of active operations. A non-interruptible native call must be shown as stopping, not falsely marked cancelled.

## Native-only background execution

The active connection must be user-visible and compatible with Android foreground-service and notification requirements. Respect Doze, force-stop, reboot, thermal throttling and network loss. Do not promise uninterrupted 24/7 processing or defeat platform restrictions. Persist work so a compatible app restart can resume at a safe checkpoint.

No thermal workaround may silently lower final render settings or overwrite full-resolution source assets. If the phone cannot safely continue, report a paused/blocked state and preserve recovery data.

## Evidence and privacy

A job is `succeeded` only after the Android handler reports completion and its expected output/postcondition has been checked. Distinguish command acceptance, relay delivery, Android execution, render completion and artifact verification.

Results should include action version, app version, project revision, output type/size/hash where applicable, and relevant native logs. A future viewport/render action may return a user-approved preview. Do not upload whole projects or original media merely to run a status request. Redact credentials and private paths from server logs and tool output.

Use one canonical project store shared by UI and automation. Do not create independent cloud copies masquerading as the current phone project.

## Implementation slices and acceptance gates

1. **Native command core:** registry, strict request validation, project-scoped dispatcher, durable journal, cancellation, truthful unimplemented capabilities. Unit tests cover invalid arguments, path traversal/symlinks, duplicate IDs, conflicting revisions, unsupported actions, missing permission and crash recovery.
2. **Private transport and OAuth:** separate Render relay, durable queue, owner/device pairing, supported MCP transport and authentication. Tests cover expired/replayed codes, incorrect audience/scope, unauthorized tool calls, cross-device isolation, token revocation, reconnect and out-of-order acknowledgments.
3. **Android connection screen and lifecycle:** encrypted credentials, opt-in session, visible status/Stop, native result reporting. Build and instrumented tests check reconnect, process death, token rotation and app updates without losing projects or identity.
4. **End-to-end activation:** deploy the authenticated HTTPS service, install APK, pair this phone, add/enable the Render MCP plugin in the user's supported ChatGPT environment, then execute a real command from ChatGPT and verify the native result on the phone. Only this gate permits the label `connected`.
5. **Engine-wide coverage:** each completed Blender module adds its actual actions to the same registry and gains native execution/evidence tests. This remains distinct from implementing the Blender engine itself.

The first acceptance scenario is: ask ChatGPT to list Render's imported projects, inspect an explicitly selected .blend, return saved Object/Scene/Mesh names from the phone's native parser, then stop/revoke and prove subsequent calls cannot execute. A rendered animation is a later gate requiring the real animation/render engine.

## Deployment and current status

Only the existing source and PR were inspected for this proposal. No Render relay has been deployed, no Render MCP plugin has been created or paired, no Android bridge service has been installed, and no live ChatGPT-to-Render command has been demonstrated. The public GitHub repository is not a remote control channel.

Do not change the existing VideoStudio deployment. This proposal adds no API key or cloud-compute dependency and no paid-service commitment. Deployment needs an actually available authorized hosting connection; current discovery did not expose a Cloudflare deployment connector in this session.

## Primary references checked 2026-10-21

- OpenAI: https://developers.openai.com/plugins/build/mcp-server
- OpenAI: https://developers.openai.com/plugins/build/auth
- OpenAI: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt

OpenAI's supported connection surfaces and workspace availability can change. Verify the user's actual plugin setup flow during activation; do not assume a subscription upgrade is necessary or that mobile ChatGPT supports every custom-MCP action.
