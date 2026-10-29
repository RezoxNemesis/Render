# Render Studio 0.39.0 — ChatGPT Agent Fast Lane

**Source:** RezoxNemesis/Render, draft feature PR #41, built atop 0.38
IK/FK and owner-imported movie timeline. Native ARM64 Blender engine and
Android package com.rezox.render unchanged. Android versionCode 48.
This phase optimizes control and inspection overhead, NOT renderer GPU speed
or artist output quality.

## Current first-party Blender/Android operations

### studio.agent.bootstrap — one-call introduction after reconnect

A single authenticated Render production.execute call returns the current
Blender versioned capability digest, nine workspace entries, active workspace,
optionally real scene summary and queued-plan state, and ranked tool matches.
Agents can supply known_manifest_sha256 on subsequent requests and receive a
smaller manifest_unchanged response when the exact same runtime is installed.
The digest is an API cache hint, NOT user identity, file hash or proof that a
future Android process is still alive.

Inputs: optional query, workspace, limit <=12, known_manifest_sha256,
include_scene and include_queue booleans. No arbitrary shell/Python.
Tools and JSON schemas derive from the installed runtime rather than stale
conversation memory.

### studio.agent.batch.inspect — six safe reads, one authenticated IPC

Accepts one to six exact items with operation and payload. Only a closed
allowlist of read-only registered Blender operations is supported, including
scene.inspect, pose/IK/curve/mesh/reference inspections, native plan status,
render settings and recent activity. Results retain original order and have
per-operation native success or failure, a sanitized error code and measured
Blender milliseconds. all_succeeded is false if any item fails; no fabricated
success. Maximum request 32 KiB and full batch reply 64 KiB; oversized
outputs fail rather than misleadingly truncating geometry data.

This reduces the number of ChatGPT-to-Android/Blender round trips needed to
inspect several things. It DOES NOT execute multiple Blender RNA operations
concurrently, and it cannot edit a mesh, keyframe a pose, open a project or
start an export: those remain serialized through existing checkpointed tools.

### studio.agent.plan.preview — inspect a multi-step plan before running

Reviews 1–16 allowlisted native steps, fingerprints the plan, reports
read-only vs mutating operations, queued slot counts and warnings about
rollback/recovery limits. It creates NO queued job, does not simulate Blender
and explicitly discloses that detailed domain payload preflight remains the
responsibility of the actual command executor. Not an IK physics optimizer.

### studio.agent.metrics — measured Blender-local durations

Returns a bounded ring of up to 64 command durations. These are actual
Python/Blender-side milliseconds from completed operations, not Android
screen FPS, remote IP latency, network round-trip or a fabricated speedup.
The record contains no owner prompts, media paths, secret credentials or
geolocation. A performance claim requires a controlled same-device baseline.

### studio.agent.status — Android out-of-band lightweight check

The original Android production.execute still requires the correct Render
target_id. An authenticated studio.agent.status request reads actual
NativeHeartbeat, work stage, last accepted operation and time spent in the
Android status handler. Optional flags append sanitized private plans,
on-device thermal/memory telemetry and the existing durable render queue.
Unlike a Blender timer request, this can run when the native editor thread is
busy inside a long frame. The response distinguishes a heartbeat from a
proven executing command, and never claims that a force-stopped app is still
running.

## Source performance changes

- The ordinary studio.tool.search now builds approved tool name/schema
  definitions once per actual native Blender process using a bounded
  function cache. Queries score actual operation names, disciplines and
  simple natural-language synonyms; no web/LLM search, external downloads or
  arbitrary Python. The original exact command IDs are still returned.
- Durable StudioPlans JSON receipt objects use an in-memory, maximum 96-item,
  2 MiB cache. Every read first checks the file's inode, size, nanosecond
  modification time and change time; external writes or atomic renames force
  revalidation against the original plan fingerprint. Cached dictionaries
  are deep-copied to prevent caller changes. App-private fsynced disk files
  remain authoritative; cache loss cannot drop a queued job.
- Existing timer yields between bpy edits and backs off while idle.
- Every mutation still gets source checkpoints and refuses unreceipted
  crashes / automatic replays. No parallel writes to Blender's RNA data.

## Recommended normal ChatGPT invocation flow

1. Check studio.agent.status when only a quick readiness/update check is
   needed; do not repeatedly wake GPU/Blender merely to ask for a status.
2. Call studio.agent.bootstrap with a natural-language tool query and
   include_scene as needed. Cache the manifest SHA only while the process or
   app version is unchanged; requery after upgrade or conflicting output.
3. Call studio.agent.batch.inspect for <=6 currently relevant read-only
   object/rig/timeline inspections. Verify every result.state succeeded.
4. Use studio.agent.plan.preview for substantial plans, inspect warnings,
   then studio.plan.submit for actual checkpointed work. Mutations NEVER
   enter the read-only batch endpoint.
5. Query studio.plan.status or quick-status for progress; use
   studio.agent.metrics for measured native timings. Recover interrupted
   tasks by inspecting receipts and the actual scene, never blind retry.
6. When real visual judgment matters, use actual Blender window UI/media
   reference inspection, not numerical "look-quality percentages".

## Performance claims and release criteria

Speed claim supported by architecture: N requested read operations can now
be inspected with ONE authorized native IPC (N <= 6), compared with N
individual calls. Saved calls can reduce overhead on slow networks.
Actual speedup depends on Blender execution, Android app availability,
network and load. A 6-read batch is NOT guaranteed 6x faster.

Host tests cover strict allowlisting (including rejection of write ops),
nonfinite/oversize input, plan preflight, natural-language retrieval, queue
cache invalidation after external atomic modification and crash recovery.
Real Blender tests verify versioned bootstrap, cached schema reuse, one-call
inspection of an actual mesh/scene/workspace and queue, true error state and
no changed engine settings. Android JVM tests enforce target credentials,
strict input flags and data minimization while Blender is not ready.

The signed test APK must preserve original libblender.so, JNI bridge, runtime
modules, signer, project files and performance/thermal safeguards. User's
installed device certificate and local project data are NOT accessed in
GitHub Actions. Do not uninstall the existing app or merge into main merely
because desktop tests and APK compilation pass.

### Still pending beyond this upgrade

Actual phone before/after IPC latency measurements; touch-screen sculpt/IK
visual feedback, natural human movement, facial/muscle/cloth physics,
large high-poly workloads, 10GB+ exports and OS-constrained background
rendering all require dedicated future work and physical Android validation.
