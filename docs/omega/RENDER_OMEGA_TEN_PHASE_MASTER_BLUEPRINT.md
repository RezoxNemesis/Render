# RENDER OMEGA — ONE MASTER ENGINEERING BLUEPRINT
### Thirteen independent phases · Thirteen ChatGPT engineering agents · One frozen master contract

**Contract:** RENDER-OMEGA-13P-20261022 / revision 2.0  
**Established:** 22 October 2026  
**Repository:** https://github.com/RezoxNemesis/Render  
**Frozen source baseline:** e334d7b6bc5a60f4cc6b5ca0029fa973007cb7e0  
**Baseline branch:** feature/025-no-downgrade-render-recovery-20261022  
**Integration branch:** integration/render-omega-ten-phases-20261022  
**Canonical document:** docs/omega/RENDER_OMEGA_TEN_PHASE_MASTER_BLUEPRINT.md  
**Primary target:** genuine Blender capabilities on native Android, controlled by human touch or ChatGPT through verified native actions, without silent reduction of final output fidelity.

> THIS IS THE ONE AUTHORITATIVE ENGINEERING CONTRACT. All thirteen agents read this exact file and receive only their assigned phase number in the launch message. Do not fork another master blueprint, rename phases, quietly alter shared contracts, or claim success from a proposed design instead of working code.

---

## 0. Mission and scope

Make Render Studio a self-maintainable Android production environment using its existing genuinely native Blender port, real bpy and Blender scene data. Support substantially better character anatomy, sculpting, topology, rigging, motion, environments, materials, VFX, assets, stable rendering, and safe hands-on/ChatGPT control. Fit expensive operations to Android using *execution scheduling, durable data, profiling, scoped interfaces, and device-specific reliability engineering*. Never silently replace a requested render with a lower-resolution, lower-sample, lower-polygon, fake-preview result.

This blueprint turns ten externally supplied Blender reference videos into reproducible native workflows rather than pretending those videos document Android bugs. The mobile defects are independently evidenced by screenshots and recordings of Render: a badly proportioned human silhouette, a speckled car viewport, missing quit.blend recovery, 0%-render interruptions, checkerboard Render Results without confirmed output, and inconsistent project continuity. A screenshot alone cannot prove a Vulkan driver defect or that a renderer produced blank file bytes; retain that uncertainty until instrumentation proves it.

### 0.1 Immutable inputs that every phase must read

- The **same** canonical master document at the above GitHub path.
- docs/V024_RENDER_CONTINUITY_ASSETS.md and docs/V025_NO_DOWNGRADE_RENDER_RECOVERY.md; read existing source rather than copying features already implemented.
- Ten_Video_Engineering_Findings.md and Ten_Video_Technical_Analysis.pdf supplied by the owner. These are references and validation targets, not unambiguous bug reports.
- Existing PR #7 (Render 0.24) and PR #8 (Render 0.25) as inherited, unmerged implementation work. Neither is permission to merge into main.
- Source and test suites under app/, full-app/, tools/, native-tests/, relay/ and .github/workflows/.

**Important evidence separation:** footage supports modeling, animation and artistic techniques. It does not establish actual Android frame rates, thermal behavior, hardware limits or that an entire pipeline can be reproduced in one automated command. Each agent must separate (a) source observation, (b) tested implementation, and (c) unverified quality ambition.

### 0.2 Reference-to-phase map (all ten examples accounted for)

| Original MP4 | Required native capability | Primary owner | Independent verification |
|---|---|---|---|
| 1000071894 | Block → polish, obstacle interaction, root motion and feet contact | P7 | Repeatable motion path and stable planted feet |
| 1000071896 | Quadruped skin, controllers, FK/IK, action curves/NLA | P6 + P7 | Paw contact and action-loop tests |
| 1000071898 | Train/track/field scene, lights, sky and camera | P8 | Reopenable, instanced cinematic scene |
| 1000071903 | Monumental ruins, detail instancing, vegetation, fog | P8 + P9 | Measurable scene geometry and render pass |
| 1000071904 | WIP / raw render / final grade, glow and compositing | P9 | Same scene with reproducible separate outputs |
| 1000071905 | Modular architecture, asset library, placement/snapping | P8 + P4 | Accurate reusable arch/column scene |
| 1000071906 | Procedural waterways plus separately generated fluid mesh/cache | P9 + P8 | Explicit simulation import/export; no false native LiquiGen claim |
| 1000071923 | Human anatomical sculpt, face/hair/clothes/UV and rig | P5 + P6 | Three-view human artifact, not primitive blockout |
| 1000071924 | Genuine bridge edge loops and topology modification | P4 | Manifold joined arch, edge/normal and undo proof |
| 1000071925 | Strikes, jab/cross/hook, rig, NLA and dual views | P7 + P6 | Contact/guard/retime motion fixture |

### 0.2a Six additional real-artist workflow references (supplied later)

These six videos strengthen the autonomy requirement: Blender artists repeatedly select specific modes, use real brushes, make corrections, inspect from several cameras and choose when to save or render. The recordings demonstrate workflows, not a universal one-click generator.

| MP4 | Observed/desired workflow | Primary phase owners | Evidence requirement |
|---|---|---|---|
| 1000072028 | Character hair geometry, modifier conversion and hair control | P05 + P11 + P12 | Editable groom and silhouette validation |
| 1000072032 | Urban destruction, vehicle/debris staging, camera/VFX | P13 + P09 + P11 | Real collision/simulation cache or explicit unsupported status |
| 1000072033 | Monumental 3D landscape, compositing, atmosphere, camera | P08 + P09 + P11 | Native object/terrain counts and validated output |
| 1000072034 | Tree trunk and root sculpt-brush operations, leaves/branches | P11 + P08 + P12 | Brush stroke creates measurable native mesh changes |
| 1000072035 | Terrain sculpt, influence painting, animated grass/trees | P08 + P11 + P13 | Evaluated scatter and time-varying native animation |
| 1000072036 | Character pose controllers, Graph Editor and polished timing | P06 + P07 + P11 + P12 | Real actions, pose changes, evaluated quality checks |

A phase must not simply copy a rendered frame from a reference and label it editable Blender output. Success means real native objects and repeatable edits, tested from a saved scene.


### 0.3 Hard prohibitions — nonnegotiable

1. **No quality downgrade by stealth.** Preserve source mesh topology, requested output dimensions, output frame rate and fps base, Cycles/Eevee engine choice, render sample settings, materials, texture source and color management. Interactive proxy/LOD is acceptable **only when explicitly flagged as preview-only** and original scene data remains intact. Unsupported final settings return a typed error, not guessed replacement.
2. **No fake Blender.** No Android canvas pretending to execute sculpting, no screenshot presented as a 3D asset, no fake success receipt, no skeleton-free “rig,” no flat boxes as “finished characters,” no simulated ChatGPT finger taps or invented output files.
3. **No unsandboxed agent access.** Typed allowlisted actions only; never remote Python eval/exec, arbitrary bpy operator name, arbitrary shell or external filesystem path. Keep explicit user-controlled Android permissions and native execution receipts. No Gallery enumeration.
4. **No loss of projects.** Save snapshots atomically; preserve last-known-good SHA-bound .blend; no silent new project on return, destructive cleanup, app uninstall, package rename, UUID reset, keystore rotation or broad storage deletion.
5. **No silent fallback to remote rendering.** Native rendering stays on the device. Google Drive is optional user-authorized storage, not Blender computation. No surprise upload of private media.
6. **No imaginary unlimited hardware.** Severe thermal state, memory shortage, unsupported Vulkan feature or driver crash is a genuine blocker; pause or fail with evidence and resume semantics, without secretly changing requested final quality.
7. **Respect Blender/copyleft and assets' licenses.** Preserve GPL and corresponding-source obligations for distributed Blender builds; track third-party mesh/textures/animations license and attribution. Do not bundle unknown or proprietary video assets as “free.”
8. **No main merge, release or APK install by phase agents.** PR to integration only. Retain existing original package com.rezox.render and require the exact installed signing certificate for any later approved in-place update.
9. **No rewriting other agents' modules**, even to “fix” them. Report an interface mismatch to the integrating agent; put a non-invasive compatibility stub or test in your own owned directory.
10. **No automatic “Complete” on a clock.** Status is evidence-based, explained below.

---

## 1. Parallel delivery operating system

### 1.1 Ten agents and assignment

Each ChatGPT instance is assigned **exactly one integer N from 1 through 13** in the user's phase launch message. There is no negotiation, re-planning, or dependency on previous chat state. It follows this blueprint's phase N, owns only those paths, and publishes one PR against the shared integration branch.

**Thirty-minute target:** 0–4 min inspect baseline, 4–20 min code a bounded usable vertical slice, 20–25 min run focused tests and fixtures, 25–28 min commit/push + PR, 28–30 min produce an evidence report. These are scheduling targets, not physical guarantees. Full photoreal character automation, production fluid solving, comprehensive Blender parity and five-minute phone thermal runs may take more than one sprint. The agent must implement the highest-value independent slice and report residual tasks as outstanding, not mark the full capability complete.

### 1.2 Frozen topology

All thirteen branch heads MUST start at the **same single commit containing this completed master blueprint** (not the changing main branch, another agent's head or an unsynchronized PR). The integrator creates/announces that seed SHA after publishing this document. Every phase PR has:

- **Head:** feature/omega-PNN-<slug>-20261022, where NN is 01..13 (exact ready branches named in §2).
- **Base:** integration/render-omega-ten-phases-20261022.
- **Allowed changes:** the phase ownership paths in §2 only; one unique phase report path.
- **No direct push to integration or main.** A PR may be rebased only by its owner and only onto the frozen seed until integration review.
- **No self-merge.** PR merge is centralized after diff, tests, signing checks and ownership checks.

If the owner starts phases in different chats at different times, phase agents must not infer assignments from timestamp or user name. The explicit N always wins.

### 1.3 Output states and the word Complete

There are exactly three report statuses:

- **Complete** — all mandatory acceptance tests for the assigned 30-minute *phase slice* passed, real committed code exists on the correct branch, a PR targets integration, required artifacts are linked, no unauthorized paths changed, and known limitations are listed. Complete does **not** mean every future film-quality ambition is finished.
- **Partial** — some usable, tested code exists but at least one mandatory slice criterion is unmet. Push a draft PR, give accurate evidence and blockers. NEVER write “Complete.”
- **Blocked** — missing rights/device/Blender runtime/signing key or genuine technical barrier prevents a verified slice. Provide the exact failing command/log and a proposed correction; do not modify another phase.

Mandatory final report fields: phase number/title, branch, PR URL, commit SHA(s), changes by file, real Blender/bpy test results, Android/unit results or explicit NOT RUN reason, validated artifact paths, unexpected errors and what remains for integration. The final word **Complete** is permitted only for Complete status; otherwise end in Partial or Blocked.

### 1.4 Shared engineering tests and invariants

1. Python compilation; pure validation and unit tests; no import-time effects on unavailable Blender modules.
2. Actual Blender bpy tests where a Blender runner is available, with synthetic meshes/poses/materials. A mock-only “tests passed” is not a native engine claim.
3. Android JVM/Robolectric tests for owned Java behavior, plus actual ARM64 device tests when available. Desktop CI cannot prove Vulkan phone behavior.
4. Deterministic synthetic fixture for every new native operation. Save/reopen and compare topology count, transforms, material slots, action curves or cache hashes as appropriate.
5. Idempotent command replay: same job idempotency key cannot duplicate assets, frames or payments; results tied to a source revision.
6. Persist through process kill mid-operation when that operation is declared resumable; an unverified output is NOT a completed artifact.
7. Explicit optional capabilities: report missing modules/drivers as unsupported; do not crash startup or silently use an inferior renderer.
8. No modification of render quality by preview controls, viewport clipping, thermal policy, asset browser thumbnails or proxy LOD.
9. GitHub CI status plus test/log excerpts must support claims. Source screenshots are never proof that a future APK fixes a device-specific failure.
10. If an existing test fails at baseline, record its preexisting failure, then demonstrate the phase does not introduce a new regression.

### 1.5 Exact freeze rules

Only the integrator/Phase 10 may change these **shared entry points** after seed:

- full-app/scripts/render_agent_startup.py
- app/src/main/java/com/rezox/render/agent/ProductionBridge.java
- app/src/main/java/com/rezox/render/agent/AgentActions.java
- app/src/main/java/com/rezox/render/agent/AgentPolicy.java
- app/src/main/java/com/rezox/render/agent/BlenderSpool.java
- tools/assemble_full_native.py
- tools/prepare_production_toolkit.py and tools/prepare_v23_reference.py
- app/build.gradle.kts, full-app/app/build.gradle
- .github/workflows/**, signing utilities, AndroidManifest sources
- this master blueprint.

Phase teams may read these and propose changes in their PR text; they cannot edit them. Phase 10 must not rewrite owned Phase 1–9 implementation files and can only add reversible adapters around their exported interfaces.

Existing versioning: 0.24 and 0.25 are open drafts; pinned 0.25 baseline versionCode is 27 in its staged build adapter. Phase agents cannot guess currently installed version. Any eventual release must have a versionCode greater than the actually installed original and reuse its signer, with signed metadata verification.

### 1.6 Review gates before merging

G0: Frozen source+blueprint recorded.  
G1: Phase's changed-files diff matches ownership exactly.  
G2: Phase's isolated tests pass.  
G3: Phase 10's combined operation registry imports without missing-module crashes.  
G4: Native bpy, Android bridge, JNI and full Blender packaging tests pass, including original package/signature.  
G5: On-phone smoke tests record crash, thermal, memory, render checksum, project continuity, UI input and quality against reference scenes.  
G6: Owner approves installing a **verified** original-package in-place APK. No release solely from a successful desktop mock test.

---

## 2. File ownership / merge topology (STRICT)

**Existing shared core remains readable to everyone. New phase modules live in an omega namespace.** A phase owns no file simply because it depends on that file. Existing source may differ; agent must verify it on its frozen seed before editing.

| Phase | Scope | Exclusively writable files / directories | Forbidden competing edits |
|---|---|---|---|
| **01** | Android engine, Vulkan/UI stability, native editor accessibility | full-app/app/src/main/java/com/rezox/render/EditorLaunchActivity.java; full-app/app/src/main/java/org/blender/blender/BlenderMobileControls.java; app/src/main/java/com/rezox/render/omega/engine/**; full-app/scripts/omega/phase01_engine.py; app/src/test/java/com/rezox/render/omega/engine/**; tools/omega/test_phase01_*.py | ProductionBatch, Agent bridge, signing, startup registry |
| **02** | Render snapshots, native job reliability, encoding/restore | app/src/main/java/com/rezox/render/agent/ProductionBatch.java; RenderManualJobs.java; RenderRecoveryStatus.java; ProductionVideoEncoder.java; full-app/scripts/render_production.py; render_session_tools.py; render_v25_recovery.py; full-app/scripts/omega/phase02_render.py; app/src/test/java/com/rezox/render/omega/render/**; tools/omega/test_phase02_*.py | BlenderMobileControls, AgentWorkPresence, shared launcher/registry |
| **03** | Typed planning, honest live hand, journal, recoverable autonomy | app/src/main/java/com/rezox/render/agent/AgentJournal.java; AgentWorkPresence.java; StudioLiveHandOverlay.java; app/src/main/java/com/rezox/render/omega/agent/**; full-app/scripts/omega/phase03_agent.py; app/src/test/java/com/rezox/render/omega/agent/**; tools/omega/test_phase03_*.py | AgentActions, ProductionBridge, AgentPolicy, renderer core |
| **04** | Mesh/curve topology, reliable bridge/loop operations | full-app/scripts/omega/phase04_geometry.py; tools/omega/test_phase04_*.py; native-tests/omega/phase04/** | All existing shared Blender scripts |
| **05** | Anatomically useful character/surface pipeline | full-app/scripts/omega/phase05_character.py; tools/omega/test_phase05_*.py; native-tests/omega/phase05/** | Phase 6 rig, Phase 8 assets, bridge |
| **06** | Humanoid/quadruped rig/weights/IK | full-app/scripts/omega/phase06_rig.py; tools/omega/test_phase06_*.py; native-tests/omega/phase06/** | Phase 5 character creation, Phase 7 motion |
| **07** | Animation curves, contact, NLA/action choreography | full-app/scripts/omega/phase07_motion.py; tools/omega/test_phase07_*.py; native-tests/omega/phase07/** | Rig generator, renderer, bridge |
| **08** | Free assets, instanced worlds, camera/terrain/scatter | full-app/scripts/render_assets.py; full-app/scripts/omega/phase08_world.py; tools/omega/test_phase08_*.py; native-tests/omega/phase08/** | Geometry ops, VFX shader code, shared registry |
| **09** | PBR/lookdev/compositing, simulation cache interchange | full-app/scripts/omega/phase09_vfx.py; tools/omega/test_phase09_*.py; native-tests/omega/phase09/** | Render core, world generator, bridge |
| **10** | Exact typed registry, Android/native packaging and release gates | all explicitly listed **shared entry points** in §1.5; full-app/scripts/omega/__init__.py; full-app/scripts/omega_registry.py; app/src/main/java/com/rezox/render/omega/integration/**; tools/omega/test_phase10_*.py; docs/omega/phase10-interface-test-data/** | No rewriting P1–9 implementation modules |
| **11** | Observable artist-like tool executor, viewport, sculpt brushes and native UI workflow | full-app/scripts/omega/phase11_artist.py; app/src/main/java/com/rezox/render/omega/artist/**; app/src/test/java/com/rezox/render/omega/artist/**; tools/omega/test_phase11_*.py; native-tests/omega/phase11/** | Existing mobile controls, Phase 1, shared bridge or startup, other phase files |
| **12** | Vision/geometry inspection, iterative self-critique and actionable repairs | full-app/scripts/omega/phase12_quality.py; app/src/main/java/com/rezox/render/omega/quality/**; app/src/test/java/com/rezox/render/omega/quality/**; tools/omega/test_phase12_*.py; native-tests/omega/phase12/** | Character, rig, animation and artist executor implementation files |
| **13** | Native physics/destruction/cache interchange and deterministic simulation | full-app/scripts/omega/phase13_simulation.py; app/src/main/java/com/rezox/render/omega/simulation/**; app/src/test/java/com/rezox/render/omega/simulation/**; tools/omega/test_phase13_*.py; native-tests/omega/phase13/** | Render core, VFX implementation, P8 world generator and shared registry |

All thirteen phases can additionally create/update ONLY their own evidence file at **reports/omega/PHASE_NN_RESULT.json**. That is a result report, not a competing blueprint. Do not commit downloaded binary source videos, private project .blend files, secrets, signing keystores, ADB dumps with owner data or large cache artifacts to GitHub.

**Special note:** P4–P9 and P11–P13 code modules MUST run in headless real bpy tests independently before the shared registry is wired by P10. They cannot introduce ad hoc startup monkeypatches to “make features visible” before integration. P1/P2/P3 can own carefully scoped existing Java/Python files as specified. Ownership violations are an automatic G1 failure, irrespective of how good the feature seems.

---

## 3. Frozen cross-agent operation contract

The following interface is authoritative. Agents MUST implement to it rather than invent different payload envelopes. It allows thirteen agents to develop independently while P10 wires the native dispatcher.

### 3.1 Transport envelope and object identity

The existing transport stays: VideoStudio MCP -> authenticated Render Binder/bridge -> typed production operation -> app-private bpy spool -> Blender's main-thread timer -> native bpy result. No separate remote code interpreter, cloud Blender session or uncontrolled Android intents.

Outer request fields: operation (exact string, max 96 chars), payload (JSON object, bounded <= 131072 UTF-8 bytes including envelope), target_id (the existing authenticated Render public UUID where required). Do not use arbitrary file paths, generic operator strings or media IDs that were never owner-authorized.

Each phase exposes **static operation names**:

- P01: omega.engine.diagnose, omega.engine.viewport_profile
- P02: omega.render.preflight, omega.render.job_status
- P03: omega.agent.plan_validate, omega.agent.journal_status
- P04: omega.geometry.bridge_loops, omega.geometry.inspect
- P05: omega.character.create, omega.character.audit
- P06: omega.rig.bind, omega.rig.audit
- P07: omega.motion.create_actions, omega.motion.audit
- P08: omega.world.build_scene, omega.world.audit
- P09: omega.vfx.create_grade, omega.vfx.cache_inspect
- P10: omega.integration.capabilities, omega.integration.audit
- P11: omega.artist.inspect_ui, omega.artist.execute_tool
- P12: omega.quality.inspect, omega.quality.revise_plan
- P13: omega.simulation.bake, omega.simulation.inspect_cache

**New operations are optional if the phase cannot implement them safely in its sprint.** Never advertise an unimplemented one. The exact names above are reserved: other phases may not reuse them. P10 builds a static allowlist containing only operations that actually passed their tests.

### 3.2 Python native module interface

Each Python phase module exports the following, using a **Blender-main-thread-only** executor where bpy is accessed:

    CONTRACT_VERSION = "RENDER-OMEGA-1"
    OPERATION_NAMES = ("omega.<domain>.<verb>", ...)
    def validate(operation: str, payload: dict) -> dict:
        """Pure input validation, no project mutation. Raise ValueError(code)."""
    def execute(operation: str, payload: dict, context: dict) -> dict:
        """Operate on context['scene']; return JSON-serializable native receipt."""
    def audit(operation: str, payload: dict, context: dict) -> dict:
        """Read-only, verifiable project state and quality checks."""

Context keys supplied by P10: scene (actual bpy.types.Scene); production_root (canonical app-owned directory); job_id (validated 32-char hex or None); available_memory_bytes (measured on Android if available, never client-controlled); dry_run (bool); cancellation_requested (bool or callback checked between safe units); capability_revision (string). The dispatcher validates type and scope; modules MUST NOT trust any user-requested filesystem path.

Python module files can be imported without an Android runtime for *pure tests*; native bpy operations must fail clearly if bpy is absent rather than silently returning fake geometry. No phase may import another phase module directly; communicate only through native Blender scenes/data blocks, documented object names/metadata and neutral validated JSON contracts.

Standard success receipt fields:

    {
      "operation": "omega.<domain>.<verb>",
      "state": "succeeded",
      "scene": "NativeSceneName",
      "source_revision": "<stable hash or available revision>",
      "created": ["native bpy object/action names"],
      "artifact": {"kind": "blend|png|mp4|cache|none", "sha256": "... or null"},
      "native_execution_verified": true,
      "visual_quality_verified": false,
      "quality_reduced": false,
      "warnings": []
    }

A success receipt MUST be truthful. It is not enough for an operator to return FINISHED; verify object/data presence or artifact hash. An absent file stays null, and visual_quality_verified is false until actual image-based acceptance. Use explicit error codes (INVALID_ARGUMENTS, UNSUPPORTED_NATIVE_FEATURE, OUT_OF_MEMORY_PAUSED, THERMAL_PAUSED, CHECKPOINT_CONFLICT, MISSING_REFERENCE, NATIVE_RENDER_UNCONFIRMED) with logged evidence; never return success after a partial write.

### 3.3 Visual quality and output contract

- **Preview:** may use explicit proxy meshes, reduced viewport sampling or culled instances only in a clearly labelled preview mode; source .blend and final render settings remain unchanged.
- **Final:** preserve geometry, textures, actual output width/height, engine identity, samples, frame_start/frame_end, fps/fps_base, color-management settings and passes; if unsupported, stop with an honest diagnostic.
- **Storage:** atomic write → fsync where supported → rename → checksum → durable manifest. Every completed frame has absolute frame number, checksum and width/height receipt; on restart, skip only hashes that validate.
- **Undo:** each geometry or scene action is undoable in the real Blender UI or wrapped in a project checkpoint/rollback transaction with no surprise permanent edit.
- **Session:** preserve active project and existing user scenes; never treat a new default scene as proof that recovery succeeded.
- **Benchmark scene:** a stylized human, 2-column bridge arch, canine gait, boxing strikes, train field, ruin temple, and transparent/opaque lookdev panel must all be reproducible with deterministic synthetic test inputs.
- **Animation:** preserve action curves/retime metadata, root motion and useful contact tests; a screenshot of an action is not a playback test.
- **Renderer:** the checkerboard Render Result is an unverified buffer until a real populated PNG/EXR has been checked. F12 aborting at 0% requires native event+Android process-exit evidence, not a guess that GPU crashed.

### 3.4a Autonomous artist working principle

**Control requirement:** A user can issue a high-level production goal, and the installed Render agent should translate it into authentic edit operations—select a real object, set Blender mode, invoke allowlisted geometry/sculpt/pose/graph/nodes actions, inspect native data or captured viewport, make corrections, save and render using real receipts. P11 owns the observable tool executor, P12 owns evaluation/revision proposals and P03 owns multi-step orchestration. P10 connects them; no phase accesses arbitrary raw bpy Python from the network.

**Human-observable, not forged:** In-editor indicator/hand shows real active steps and where confirmed UI interactions occurred; an API operation with no physical touch must not display an invented click position. The dashboard must distinguish QUEUED, EXECUTING, OBSERVED RESULT, NEEDS CORRECTION, PAUSED, FAILED and DONE. It may run a native deterministic bpy operation without simulating a finger gesture, but it must explain which real operation and objects were involved.

**Autonomous quality loop:** owner prompt -> asset/scene plan -> command execution -> scene/viewport inspection -> metric-based or image-based critique -> bounded correction -> independent confirmation -> snapshot -> next stage. A visually attractive screenshot without editable geometry cannot pass; a well-formed rig with visibly deformed limbs cannot pass character quality review merely because bone names exist.

**Permission boundary:** The owner's broad intent authorizes work on the selected Render project, not unrestricted access to all Android apps, contacts, secrets or private gallery. Initial app installation, Android document-tree grant or account authorization may require a real owner gesture. Afterwards, permitted app-native operations should minimize manual intervention.

### 3.4 Android + packaging boundary

The source uses a pinned full Android Blender port, app-private startup Python runtime zip, Java NativeActivity, an Android JNI/Binder agent and a build adapter. P10 is the sole owner of bundling omega modules into scripts/startup/omega, registering allowlisted actions and checking startup on real Blender. New phases MUST NOT overwrite the upstream Blender .so, re-sign with a different key, or replace the native engine with a toy renderer.

The build adapter tools/prepare_production_toolkit.py may mutate staged working-tree copies. Run on a dedicated disposable checkout; do not accidentally commit its generated rewrites into other phase branches. P10 checks adapter idempotency and ensures packaged modules are actually imported in the Android APK. A local headless Blender run is not an Android GPU certification.



---

# PART II — THIRTEEN PARALLEL PHASE HANDOFFS

Each of the 13 sections is an actual engineering workstream, not a feature wish list. Every ChatGPT instance reads this entire contract, receives its phase number N from the user, and implements ONLY phase N. No agent relies on another agent's unmerged code. Self-contained synthetic Blender fixtures and the neutral interface in §3 are the only allowed substitutes while collaborating in parallel.

**Required phase-agent opening procedure:** Verify repository and exact phase branch HEAD against the frozen seed. Read the source and existing tests. Run a focused baseline test and record existing failures. Create a bounded real vertical slice in phase-owned files. Commit source, deterministic tests and the PHASE_NN_RESULT.json report. Open a draft PR from its phase branch to integration/render-omega-ten-phases-20261022. Report Complete only when the phase-slice gates pass, otherwise Partial or Blocked.

## PHASE 01 — NATIVE BLENDER ENGINE / ANDROID VIEWPORT RELIABILITY

**Assigned agent:** 1. **Branch:** feature/omega-P01-native-engine-20261022. **Owned files:** see P01 in §2.

**Mission:** Keep the full native Blender engine accessible and stable on an Android phone; no simplified editor, preview model presented as final, or changes to requested final output resolution.

**Implementation requirements:**
- Measure native bootstrap stages, runtime asset readiness, Vulkan support (where discoverable), Activity changes, and actual first displayed frame evidence. Do not claim successful GPU drawing based on an Activity onCreate event.
- Improve native portrait/landscape viewport accessibility: safe cutout insets, consistent orbit/pan/zoom and modifier-key behavior, movable/collapsible buttons, no overlay covering core Blender controls.
- Add reversible viewport diagnostics: near/far clip ratio, explicit AA selection, X-ray/wireframe, transparency sorting candidates, z-fighting/coincident geometry and nonuniform transform warnings. Never silently apply scale to a rigged wheel mesh or change final renderer settings.
- Validate preserved user projects across configuration changes, foreground/background and runtime re-extraction. Save no credentials in logs; run long file checks off the UI thread.
- Publish truthful native diagnostic operation omega.engine.diagnose and viewport profile operation omega.engine.viewport_profile, without modifying the shared production registry.

**30-minute verified slice:** a bounded native engine diagnostic and one reversible viewport or Activity continuity correction, demonstrated by Android tests and real-device evidence if available.

**Pass evidence:** screenshot/telemetry of settings before/after; UI scaling/rotation stays consistent; native scene untouched; no final render quality change; test for preserving Production/Projects files across Activity transitions. Remaining device-driver jitter is reported as unresolved unless reproduced and actually fixed.

**Failure traps:** holding a stale native Window reference, assuming first frame was drawn, changing preview clipping and unexpectedly affecting final render, native library loading before packaged asset verification.

## PHASE 02 — CRASH-SAFE FULL-QUALITY RENDERING / ENCODING / RECOVERY

**Assigned agent:** 2. **Branch:** feature/omega-P02-render-recovery-20261022. **Owned files:** see P02 in §2.

**Mission:** Render full-quality Blender PNG frames and H.264 video reliably, make every frame resumable, diagnose the recorded 0%-renderer interruption and preserve current and previous .blend project states.

**Implementation requirements:**
- Maintain a durable state machine: SNAPSHOT → FRAME_PENDING → RENDERING → FILE_VERIFIED → FRAME_COMMITTED → FRAMES_COMPLETE → ENCODING → VIDEO_VERIFIED, with explicit FAILED/PAUSED reasons. A Blender FINISHED flag alone is not proof of valid file bytes.
- Correct absolute start/end frame handling (e.g., 101–105); save frame number, source revision, width/height, samples/engine, checksum, checkpoint fingerprint and time evidence. Resume first missing/corrupt frame, never duplicate validated ones.
- Preserve engine, native requested samples, materials, color management, dimensions, fps and fps_base; fail explicitly when unsupported. No silent downgrade or Eevee backend substitution.
- Do not delete verified PNG masters on failed video encoding. Protected one-frame PNG does not require one-frame MP4. Handle missing camera, driver errors, partial files, unsupported codec and thermal/memory pauses with readable status.
- Restore projects from independent SHA-bound snapshots; an absent Blender quit.blend after a crash is not proof of destroyed data. Never overwrite dirty current project without rollback checkpoint.
- Read Android historical exit reasons and Blender native render lifecycle receipts, clearly marking cause unknown when the logs cannot prove a GPU problem.

**30-minute verified slice:** fix one reproducible render/resume defect with real bpy and a power-loss/corrupt-file simulation.

**Pass evidence:** 101–105 interruption after 103 renders only 104/105 on resume; invalid PNG cannot be committed; full-size still PNG tested; codec claims require an actual Android encoder test; project save/open equality proven; no reduced final quality. A checkerboard Render Result is not a valid output artifact.

**Failure traps:** active frame compared with frame_count rather than absolute end, fsync omitted before renaming, infinite retry on GPU crash, codec frame metadata different from requested timing.

## PHASE 03 — AUTONOMOUS JOB PLANNING / LIVE WORK HAND / DURABLE JOURNAL

**Assigned agent:** 3. **Branch:** feature/omega-P03-autonomy-planner-20261022. **Owned files:** see P03 in §2.

**Mission:** Accept an artist-level goal and coordinate real native operations from planning through delivery, with no fabricated activity or unsafe remote code interpreter.

**Implementation requirements:**
- Declarative DAG of stage IDs: PLAN → CREATE/IMPORT → MODEL → VALIDATE → (RIG/MOTION/WORLD/VFX) → SNAPSHOT → RENDER → EXPORT. Define dependencies, bounded retries, idempotency keys, typed arguments and project-revision preconditions.
- Durable local journal for accepted, claimed, executing, paused, completed, failed and interrupted native calls; after process death, inspect native receipt before replaying any potentially destructive step.
- Honest live hand: indicate Blender native command, real object, current stage, frame count and genuine touch coordinates ONLY for observed interactions; API-based bpy actions must not pretend to move a finger. Support notification permission denial without interrupting a render.
- Pause, stop new commands, resume, rollback and recovery. Keep Android owner permissions scoped to selected Render project; no global file-system or unrelated app control.
- Provide plan validation and journal inspection operations omega.agent.plan_validate and omega.agent.journal_status; P10 will register them after tests.

**30-minute verified slice:** persist a three-stage synthetic native job, force restart, prevent duplicate object creation and display honest state transitions.

**Pass evidence:** idempotency test, journal-replay test, truthful hand while running, stop/new-command test, recovery of stale busy state; do not mark queued or mocked work as a completed native operation.

**Failure traps:** native frame lasts longer than heartbeat timeout, duplicate retry after a lost response, wrong project UUID, leaking commands/media in Android notifications, arbitrary Python requested via generic action.

## PHASE 04 — ACTUAL MESH TOPOLOGY / RETOPOLOGICAL EDITS

**Assigned agent:** 4. **Branch:** feature/omega-P04-topology-20261022. **Owned files:** see P04 in §2.

**Mission:** Expose real Blender/BMesh vertex-edge-face operations, including accurate edge-loop bridging and topology audit; not a pile of rectangular meshes shaped to resemble an arch.

**Implementation requirements:**
- Typed selection, closed/open edge loop validation, bridge edge loops, merge/weld, correct face winding and normals, subdivision/bevel, edge transforms and smooth shading. Use actual bmesh or native Blender operator with correct context and a bounded vertex budget.
- Validate topology before mutation and report before/after vertex/edge/polygon counts, manifoldness, degenerate faces and nonzero area.
- Support rollback via undo transaction or verified snapshot. Error leaves the original untouched. Avoid realizing millions of geometry nodes instances simply to count them.
- Expose omega.geometry.bridge_loops and omega.geometry.inspect with pure validation and native bpy audit.

**30-minute verified slice:** construct the two-column connected arch from 1000071924 using true bridge operation; persist, reopen and verify manifold topology.

**Pass evidence:** actual Blender mesh data and geometric connectivity; real operation recorded, winding/manifold and undo tests. No claimed 3D model from an image alone.


## PHASE 05 — ANATOMICAL CHARACTER AUTHORING / SCULPT / HAIR / CLOTHING

**Assigned agent:** 5. **Branch:** feature/omega-P05-human-character-20261022. **Owned files:** see P05 in §2.

**Mission:** Fix the unacceptable early 0.24 human: overly round shoulders, poorly modeled neck, flat torso, simplistic hands/feet, weak face and hair. Primitive blockout may be a step, never a completed professional character.

**Implementation requirements:**
- Stage explicit proportion/landmark → anatomical shape → facial features → retopology/UV → hair/clothing → rig-ready audit. Every stage must have honest state metadata such as BLOCKOUT, SCULPTED, RETOPO_READY, RIG_READY and FAILED_QUALITY_GATE.
- Build native editable mesh topology with head/neck, shoulders, thorax, hips, knees, hands, feet, eye sockets, nose, mouth and at least interpretable hair geometry/curves. Geometric symmetry and anatomical landmarks are measurable; subjective beauty is not automatically provable.
- Support genuine Blender sculpt modifiers, brush capability or mesh-refinement operations where supported by the pinned engine. Do not claim a textured primitive or connected blob has completed facial topology.
- Provide front, side and three-quarter editable camera/viewpoint audit artifacts; actual raytraced images only count if rendered and inspected. Preserve reference-image provenance and exact source revision.
- Output neutral mesh object names, joint landmark positions, topology/UV groups and optional material/hair component manifest so P06 can bind without importing P05 code.
- Implement omega.character.create and omega.character.audit. Flag missing details openly; no invented facial similarity scores or image-to-rig magic.

**30-minute verified slice:** a significantly improved stylized anatomical character over the crude 0.24 baseline, with native mesh, visible head/facial parts and believable silhouette from three angles. If only a blockout exists, mark Partial and retain actual work.

**Pass evidence:** vertex/face count; mesh continuity or explicit seam annotation; symmetry/proportion checks; usable rig landmarks; saved and reopened .blend; images only from real native viewport/render. Evaluation cannot claim “film-ready” from a unit test alone.

**Failure traps:** duplicated coincident surfaces at shoulders, scaled overlapping spheres, detached head, hand stump with no fingers when claiming finished hands, UV claims without layers, texture missing upon reopening, excessive density causing out-of-memory failures.

## PHASE 06 — DEFORMING HUMANOID AND QUADRUPED ARMATURES

**Assigned agent:** 6. **Branch:** feature/omega-P06-rigging-20261022. **Owned files:** see P06 in §2.

**Mission:** Actual skinned, articulated Blender characters, not cosmetic armatures or unweighted child meshes. Enable film-capable motion editing, jaw/face controls when supported and stable human/dog/wolf posing.

**Implementation requirements:**
- Real ARMATURE objects and sensible hierarchy: hips/spine/neck/head, clavicles, shoulders, elbows, wrists, knees, ankles, hands/feet, and quadruped spine/tail/hips/paws where appropriate.
- Armature deform modifier and normalized vertex groups: no zero-weight vertices, disallowed >1 total influence, reversed mirrored joints or explosive stretching under normal bending.
- IK/FK control bones and pole targets with correct axes and stable bind/pose transformations. Face controls/shape keys remain optional but, if advertised, require real geometry movement.
- Rigging must work on an independent synthetic mesh fixture if P05 output is not yet available. Publish required landmark/object metadata in the Blender scene so future character outputs bind through the neutral contract.
- Use omega.rig.bind and omega.rig.audit; inspector must report bones, deform groups, max weights, evaluated before/after vertex positions and unsupported controller features.

**30-minute verified slice:** one weighted humanoid or quadruped that visibly deforms under native pose changes and survives save/reopen.

**Pass evidence:** Blender armature+modifier+vertex group test, joint bend displacement, normalized weight check, at least one constrained IK chain if offered, reusable pose without joint explosion. Static skeleton plus nondeforming body is NOT Complete.

**Failure traps:** bones only for decoration, bone-parenting every solid mesh and calling it smooth skinning, invalid bind transforms, weight bleeding into nearby limbs, unspecified unit scaling, destructive duplicate armatures.

## PHASE 07 — ROOT MOTION / GAIT / STRIKES / ACTION CURVES / NLA

**Assigned agent:** 7. **Branch:** feature/omega-P07-motion-20261022. **Owned files:** see P07 in §2.

**Mission:** Enable editable choreography in Blender's real Graph Editor/Dope Sheet/NLA with believable weight, timing, contact and camera-independent motion.

**Implementation requirements:**
- Native action creation and keyframing for walk/run/idle and named jab/cross/hook strikes where the rig channels exist. Root-motion and foot-plant data must be distinguishable from arbitrary translation.
- Native F-curves, interpolation handles, cyclic transitions, NLA action strip start/end/scale metadata and non-destructive retiming. Keep fps/fps_base exact.
- Body mechanics: hips lead striking torso; shoulder-elbow-wrist sequence; guard returns; optional target contact and foot-contact constraints. For quadruped, paw contact and four-foot gait phasing, not human biped animation renamed wolf.
- Read scene rig metadata; never import or modify P06 module. Use an independent minimal humanoid/quadruped test armature so implementation can begin before P06 merges.
- Provide omega.motion.create_actions and omega.motion.audit with native object/action names, root curve sample data, foot drift/penetration heuristics and clear unverified artistic aspects.

**30-minute verified slice:** one native rig-driven walk cycle or a set of jab/cross/hook action clips, evaluated from two viewpoints, with saved Blender action and inspector data.

**Pass evidence:** real action/strip objects, bone rotation varies over frames, loop seam and retiming assertions, contact audit tied to actual evaluated transforms, no unexplained pose reset on reopen.

**Failure traps:** setting an object's location instead of pose bones, zero keyframes for advertised NLA, action overwritten on retime, bogus foot contact, exponential animation curve keys, poor arm joint bounds.

## PHASE 08 — FREE ASSET LIBRARY / WORLDS / SCATTER / CINEMATIC STAGING

**Assigned agent:** 8. **Branch:** feature/omega-P08-assets-world-20261022. **Owned files:** see P08 in §2.

**Mission:** Provide a useful, reusable, independently licensed native 3D asset and environment authoring system for train landscapes, ornate buildings, ruins, vegetation and terrain.

**Implementation requirements:**
- Upgrade existing 17 in-app editable procedural presets without deleting legacy names. Build searchable categories, asset provenance/license metadata, stable persistent filenames and reuse/linked datablocks. Do not download or redistribute assets with uncertain licenses.
- Native terrain, tracks, columns, walls, bridges, vegetation, roots, architectural modular pieces, wind-ready grass/tree data, functional cameras, world sky, scatter/instancing and fog-ready scene composition.
- Explicitly distinguish preview proxy/culling from unchanged final mesh and material data. Scene scalability through instancing, bounding-box budgets, chunking and user-selected preview quality; no silent polygon decimation in final.
- Actual scene assembly and snap/alignment; save/reopen deterministic transforms, material inheritance and verified asset presence. Prepare neutral scene names/collections for P09 VFX and P13 simulation.
- Implement omega.world.build_scene and omega.world.audit with counts, instancing/proxy details, light/camera/world state, scene resource admission and provenance.

**30-minute verified slice:** one deterministic railway/temple or landscaped courtyard with reusable geometry and camera, no missing textures, seeded scatter and saved Blender project.

**Pass evidence:** true material/mesh/geometry-node instances, persistent scene hierarchy, zero unlicensed downloaded dependencies, assigned camera and world, reopening transform accuracy and scene count regression. Captured image is an illustrative output only, not an asset.

**Failure traps:** full realization of million-element instances, memory estimates treated as guarantees, unrelated copyrighted reference models bundled as “free,” changing final quality because preview proxies exist, camera without useful composition.

## PHASE 09 — LOOK DEVELOPMENT / RENDER PASSES / COLOR / SIM-CACHE INTEROP

**Assigned agent:** 9. **Branch:** feature/omega-P09-lookdev-vfx-20261022. **Owned files:** see P09 in §2.

**Mission:** Reproduce the iterative WIP → RAW RENDER → FINAL workflow with persistent native PBR shading, lighting, atmosphere, render-pass settings and repeatable compositing. Provide honest import/export bridges for external simulation caches.

**Implementation requirements:**
- Native Principled materials, texture/node graph templates, emission/roughness/normal/displacement nodes where available, lights/volumetrics, camera depth-of-field, world atmosphere and color-management presets with reversible settings.
- Multi-view-layer/render-pass workflow and editable compositing nodes for bloom, contrast, grade, fog/mist and glow. Output named passes and exact scene revision. Do not bake post effects into final geometry without owner request.
- WIP/RAW/FINAL comparison must use the same scene and frame, record engine/exposure/look/OCIO configuration; if any requested pass is unavailable in the Android engine, return UNSUPPORTED_NATIVE_FEATURE.
- For waterways, support importing/validating owner-authorized cached mesh/particles/animation/foam assets and material surface; do not claim to run a proprietary simulation engine. P13 independently implements Blender-native physical simulations.
- Provide omega.vfx.create_grade and omega.vfx.cache_inspect and validate safe file names, cache completeness, bounds and frame range. No arbitrary network/path import.

**30-minute verified slice:** native Blender scene with a real Principled material, world/camera lighting, a functioning compositor and reproducible RAW/FINAL settings. Optional small cache schema smoke test.

**Pass evidence:** material nodes and links inspected, scene pass settings saved/reopened, gamma/grade operation truly affects pixels if actual rendering available, raw original unaltered, no hidden renderer replacement. EXR/pass output is complete only when real file bytes and metadata were inspected.

**Failure traps:** unsupported shader sockets silently ignored, compositing with wrong color space, viewport-material preview called final raytracing, image artifact without scene revision, wrong fluid provenance.


## PHASE 10 — CROSS-PHASE API REGISTRY / PACKAGING / TEST AND RELEASE GATES

**Assigned agent:** 10. **Branch:** feature/omega-P10-integration-20261022. **Own:** exact shared entry points in §1.5, omega_registry.py and app/src/main/java/com/rezox/render/omega/integration/**, owned tests. Only P10 edits the shared operation dispatch, Blender startup packager, permissions schema, build adapters and release/CI wiring.

**Mission:** Allow all independent phase modules to become discoverable, strictly validated, safely dispatched native tools without merging incompatible code, degrading existing Blender or disturbing stored user projects. Preserve ABI/package/installed signer while verifying combined behavior.

**Implementation requirements:**
- Create a static allowlisted capability registry for phase module names and reserved operation IDs in §3; validate schema and operation presence and expose only verified installed modules. During independent development, modules may be absent: absence must show NOT_INSTALLED, not crash native Blender startup.
- Package full-app/scripts/omega and omega_registry.py into the actual Blender runtime startup zip, ensure Python paths/import order work in the native Android process and correctly bridge typed JSON args through existing authenticated Render MCP/Binder/spool. Do not expose arbitrary Python, OS paths, shell or generic bpy operator IDs.
- Implement cross-phase adapters for P03 planner → P11 tool executor → P12 evaluation loop, with stage IDs, expected revision, bounded iteration and receipts. Honor P02 atomic job storage, P05 rig-ready neutral model contract and P13 simulation caches without directly mutating phase-owned implementation code.
- Add source ownership CI gate comparing changed files against §2. Reject unexpected phases editing another phase's module or common startup, build files, signing and UI. Integrator may propose corrective new adapter, not stealth-rewrite other agent work.
- Preserve com.rezox.render package, existing bridge ID, owner data, pinned real Blender native libraries, and exact installed certificate. Read actual installed/version metadata when accessible. No downgrade or accidental preview APK replacing original app.
- Require signed APK certificate and version checks, runtime ZIP contents, Blender startup health, Android JNI, real bpy native fixture and Java tests before release. A successful CI screenshot or a 300-MB APK is not proof that phone GPU rendering works.

**30-minute verified slice:** optional module registry and no-crash integration smoke test with synthetic phase module(s) and a packaged Blender startup import test. Further integration proceeds when other phase PRs land.

**Pass evidence:** supported/unsupported operations accurately listed; one request travels from typed bridge to actual native Blender and returns real data; invalid actions rejected; missing phase module is graceful; packaging repeated twice without duplicate startup scripts; signing check is enforced; no main merge or owner data change.

**Failure traps:** import-time Blender exceptions disabling all MCP tools, permissive eval, underdeclared scopes, circular imports between 13 modules, CI changing app ID, test port without runtime ZIP packaging, synthetic preview released as production.

## PHASE 11 — TRUE AUTONOMOUS ARTIST TOOL CONTROLLER (THE HANDS)

**Assigned agent:** 11. **Branch:** feature/omega-P11-artist-controller-20261022. **Own:** full-app/scripts/omega/phase11_artist.py and app/src/main/java/com/rezox/render/omega/artist/** plus owned tests. Phase 11 does not own the existing BlenderMobileControls, shared registry or P03 journal.

**Mission:** Give ChatGPT authentic, observable, programmable artistic control of real Blender—the ability to choose objects/modes and perform sculpt, mesh, paint, rig pose, modifier, node, animation timeline and scene operations as an artist would. This is central to the user's request: from a single project description to visible work with minimal owner intervention.

**Design: two complementary control modes:**

1. **Semantic native tools (default):** controlled bpy/BMesh/Blender operator operations with explicit target object ID, expected Blender mode, bounded parameters, editor context and verified postconditions. This is faster and more reliable than pressing a virtual finger for every vertex. For a sculpt stroke, target actual native object, selected brush/action and coordinates mapped to the Blender sculpt surface; verify mesh vertex displacement or data changes. For a node edit, verify actual nodes/links. For a pose, verify bone transforms or pose evaluators. Never rename a call “brush painting” when it only adds a sphere.
2. **Visible UI/control channel (when needed):** scoped focus, mode switching, editor area selection, toolbar/menu selection, touchscreen drags, stylus pressure when available, keyboard modifiers, graph handles and camera orbit. Actual executed GUI events may show a small hand/touch marker; semantic bpy actions must show a work badge/target and receipt rather than fabricated finger coordinates.

**Required implementation:**
- Read-only inspection of active scene, object mode/type, selection, active tool, supported operators, current editor areas, workspaces and viewport camera/matrix. UI state must come from actual Blender, not assumed context.
- A **bounded tool taxonomy** (exact action + schema, never raw operator string): object select/transform/duplicate/delete-with-checkpoint; mesh edit loop/face operations; sculpt brush sample/stroke; modifier add/configure; shader node create/link; rig pose and constraints; F-curve point edit/NLA control; lighting/camera/world changes; safe project save and render request. A 30-minute first slice need not implement every category, but categories remain frozen extension slots.
- For each action, validate preconditions, expected scene revision, target object existence, owner-scoped project, finite geometry coordinates, bounded vertex/stroke count and cancellation at safe boundaries. Map tool actions onto actual bpy context; avoid UI dependence where a native semantic operation is more stable.
- Show current operation, named target and actual progress on top of Blender, integrated later by P10 with P03 work journal. The icon never lies about clicking, loading or finishing.
- Tool output must describe old/new native state and verifiable geometry or node/pose diff; use scene checkpoint or undo for rollback. Multi-step plans cannot continue after a failed postcondition.
- Support visual screenshots/captures routed through existing owner-authorized screenshot mechanism. No Gallery enumeration or other-app control. The source video can inspire action choreography but is not automatically a verified machine-readable Blender macro.
- Owner can safely pause/stop/resume; no endless mouse loops, no permanently stuck modifier keys, and no unexpected active-mode changes after failure.

**30-minute verified slice:** execute one real sculpt or edit sequence on a synthetic editable Blender mesh (for example two native sculpt strokes plus modifier adjustments), inspect the topology change, save/reopen and expose a receipt. A second tiny fixture must prove a mode switch and object selection really occurred.

**Pass evidence:** actual native Blender tool execution, before/after mesh hash/vertex displacement, UI context correctness, optional real touch overlay observation, undo or rollback. A script printing “sculpt complete” without mesh changes fails.

**Failure traps:** arbitrary bpy eval as agent access, simulated touches at invented coordinates, Blender context override crash, zero brush influence but fake success, moving mouse for minutes instead of using Blender API, leaving app in unintended editor state, clipboard or other apps accessed with broad privileges.

## PHASE 12 — VISUAL INTELLIGENCE / SELF-CRITIQUE / ITERATIVE CORRECTION (THE EYES)

**Assigned agent:** 12. **Branch:** feature/omega-P12-visual-quality-20261022. **Own:** full-app/scripts/omega/phase12_quality.py and app/src/main/java/com/rezox/render/omega/quality/** plus owned tests. P12 may read but never modify P05 character, P06 rig, P07 animation or P11 artist executor modules.

**Mission:** Prevent the 0.24 distorted human and other visually unconvincing assets from being treated as complete merely because object creation calls succeeded. Assess real geometry, rig performance, composition and rendered images, issue typed repair proposals and verify improvements with repeatable evidence.

**Required implementation:**
- **Geometry inspection:** side/front/three-quarter bounds, human landmarks and ratio outliers, left/right symmetry, shoulders/neck continuity, self-intersections and near-coplanar surfaces, UV/material completeness, missing facial/hair/hands detail. Distinguish objective metrics from aesthetic judgment.
- **Rig/motion inspection:** skinned mesh deformation under known poses, weight issues, foot/paw world-position drift, action-loop discontinuities, wrist/elbow overrotation, collision candidates and intended movement mismatch. Do not call a skinned mesh good merely because a vertex group exists.
- **Scene inspection:** active camera framing, clipped subjects, missing lights/world, scene graph instancing vs huge duplication, render passes, missing textures and viewport-vs-final differences.
- **Pixel inspection:** inspect actual captured Blender viewport or verified PNG/EXR with their frame, camera, size and source revision. Compare to owner-supplied reference images when explicitly accessible. Do not assume on-device neural image scoring or reference input is available; return INSPECTION_UNAVAILABLE rather than fabricating a similarity percentage.
- **Revision engine:** return a finite prioritized list of typed, object-specific proposals to the P03/P11 control loop. Each proposal includes current defect evidence, target object/channel, planned operation, expected measurable improvement, max attempts and rollback checkpoint. The quality evaluator does not execute unapproved arbitrary Python.
- **Bounded feedback:** iterate only while postconditions improve and resource budgets permit. If a target requires manual artistic judgment, say so and leave a saved editable project rather than endlessly deforming it.
- Support omega.quality.inspect and omega.quality.revise_plan with machine-parseable metrics, screenshot provenance, confidence/uncertainty and honest visual_quality_verified state.

**30-minute verified slice:** inspect a known intentionally bad humanoid mesh (oversized shoulders, small head, no joint geometry) and report grounded defect metrics; produce a bounded native repair proposal; confirm a simple corrected mesh achieves the targeted metric without damaging other data.

**Pass evidence:** deterministic good-vs-bad fixture, screenshot/frame hash binding when available, genuine measurements, repair loop limited by max iteration/revision, no aesthetic “100% match” claim without real comparable data, clear distinction between issue diagnosed and issue actually repaired.

**Failure traps:** hallucinated annotations or polygons, false photoreal similarity scores, endless “make it better” cycles, corrections that worsen neighboring anatomy, pixel review on a stale frame, treating a rendered PNG as the underlying editable 3D asset.

## PHASE 13 — PHYSICS / DESTRUCTION / DYNAMIC VEGETATION / FLUID-CACHE INTERCHANGE

**Assigned agent:** 13. **Branch:** feature/omega-P13-physics-simulation-20261022. **Own:** full-app/scripts/omega/phase13_simulation.py and app/src/main/java/com/rezox/render/omega/simulation/** plus owned tests. Read but never modify P08 world generation, P09 VFX code or P02 renderer.

**Mission:** Enable genuine Blender dynamic scenes: cinematic urban debris/destruction, rigid-body contact, cloth/vegetation/wind and water simulation interoperability. Do not claim fake fluid simulation from a reflective water plane.

**Required implementation:**
- Create or configure actual Blender collision shapes/rigid bodies with correct mass, friction, collision groups, keyframe activation and deterministic initial conditions. Simulate modest debris/vehicle impacts, inspect evaluated transforms and verify they differ from static keyframing.
- Explicitly separate **native physical simulation**, **imported baked fluid/particle caches**, and **visual-only shader animation**. Runtime reports which path is used. An imported mesh sequence should have frame range, object names, size and hash receipts and missing-cache handling.
- Bounded rigid-body bake/cache with resumable folder stages, source fingerprint and checksums where Blender exposes stable baking mechanisms. No untrusted absolute paths, decompress bombs or remote arbitrary data execution.
- Support real vegetation dynamics via native scene modifiers or simple wind deformation if supported, and report false/not installed for hair/cloth/fluid features that cannot be evaluated on current Android engine.
- For waterway reference 1000071906, implement an import/export validation boundary for legitimate mesh/particles/foam frames from separate simulation tools. Do not integrate proprietary code or claim LiquiGen is part of Blender. Google Drive may store owner-approved outputs.
- Provide omega.simulation.bake and omega.simulation.inspect_cache with source settings, frame range, cached file receipts, native simulation engine identity, output geometry checks and truthful unsupported status.

**30-minute verified slice:** native Blender rigid-body drop/impact with at least two colliders, 24+ evaluated frames, identifiable changed object transforms and a saved/cached state. A cache-verification fixture is a separate small acceptance.

**Pass evidence:** actual Blender physics properties and evaluated motion, collisions producing non-static state, intact source project, cache revision/hash handling, bounded memory and explicit lack of fluid-solver capability if unavailable.

**Failure traps:** hand-keyframed debris pretending to be physics, video overlay pretending to be a simulation mesh, claiming static water material is collision-aware liquid, unbounded simulation frames, unsafe external cache extraction, huge GPU bake at severe thermal pressure.

### Cross-phase artistic end-to-end target

After P10 integrates tested capabilities, Render must be able to process the following owner request as a real production DAG:

> Create a detailed adult humanoid and a quadruped, refine their anatomy and hair, build an atmospheric ruined courtyard with vegetation and a waterway, rig the characters, choreograph a natural walk and a three-strike combat sequence, move the camera dramatically, create RAW and FINAL lighting/compositing passes, render every frame with the user's requested settings, recover safely from interruption, save the editable .blend and export verified image/video to owner-approved storage.

This is the **final integrated acceptance scene**, NOT a promise that every feature can be engineered and visually validated in a single 30-minute sprint. If an individual feature remains absent, the integrated planner must produce an explicit missing capability report and a recoverable partial project, not a substituted screenshot or fake success.


---

# PART III — BOOTSTRAP, PARALLELISM, EVIDENCE, INTEGRATION AND RELEASE

## 4. Immutable 13-branch assignment registry

Every phase branch is created from the identical **phase seed**: the one commit at the tip of integration/render-omega-ten-phases-20261022 immediately after this master document is finalized. The seed SHA is observable from the actual branch heads (and may be copied into the handoff); putting the mutable Git commit SHA inside its own content would create a circular hash, so the canonical registry names the *ref* and the GitHub branches provide the exact seed SHA.

| Assigned number | Phase name | Exact HEAD branch | Exact target base |
|---|---|---|---|
| 1 | Native engine + mobile viewport | feature/omega-P01-native-engine-20261022 | integration/render-omega-ten-phases-20261022 |
| 2 | Render/recovery/encoding | feature/omega-P02-render-recovery-20261022 | integration/render-omega-ten-phases-20261022 |
| 3 | Autonomous plan/journal/hand | feature/omega-P03-autonomy-planner-20261022 | integration/render-omega-ten-phases-20261022 |
| 4 | True mesh topology | feature/omega-P04-topology-20261022 | integration/render-omega-ten-phases-20261022 |
| 5 | Human sculpt and hair | feature/omega-P05-human-character-20261022 | integration/render-omega-ten-phases-20261022 |
| 6 | Skinned humanoid/quadruped rig | feature/omega-P06-rigging-20261022 | integration/render-omega-ten-phases-20261022 |
| 7 | NLA/motion/choreography | feature/omega-P07-motion-20261022 | integration/render-omega-ten-phases-20261022 |
| 8 | Assets/world assembly | feature/omega-P08-assets-world-20261022 | integration/render-omega-ten-phases-20261022 |
| 9 | Native lookdev/compositor/VFX | feature/omega-P09-lookdev-vfx-20261022 | integration/render-omega-ten-phases-20261022 |
| 10 | Integration/registration/CI | feature/omega-P10-integration-20261022 | integration/render-omega-ten-phases-20261022 |
| 11 | Authentic artist tool executor | feature/omega-P11-artist-controller-20261022 | integration/render-omega-ten-phases-20261022 |
| 12 | Visual quality and revision | feature/omega-P12-visual-quality-20261022 | integration/render-omega-ten-phases-20261022 |
| 13 | Physics/destruction/simulation | feature/omega-P13-physics-simulation-20261022 | integration/render-omega-ten-phases-20261022 |

**Never call old version feature/024 or feature/025 a phase branch.** They are inherited implementation lineage, not new 13-agent workstreams. The current installed app version is not inferred from source: check device package version and signer before release.

## 5. Strict conflict/ownership controls

### 5.1 Git rules

- One branch, one assigned phase, one responsible agent. Work on the existing pre-created branch; never use a second worktree pointed at someone else's branch. Phase agent MUST NOT directly push to main or integration.
- No force-push over another agent's head; no merging another phase branch into yours; no cherry-picking their unmerged code.
- Exact match ownership from §2 (and unique report path) is compulsory. Read-anywhere does **not** grant write permission. If you discover a bug in an unowned shared file, create a minimal note in your PHASE_NN_RESULT.json and include an exact proposed patch in PR description; let P10/integrator own the actual shared edit.
- Do not edit the canonical master doc from a phase branch. The only acceptable update is a separately approved integrator-issued revision, with all branches re-aligned deliberately to its new seed.
- Each phase commits tests, documented operation schemas and actual code together. PR uses distinct title “OMEGA Phase NN — <scope>” and targets exactly the integration branch.
- Integrator verifies Git changed-files before merge. A one-line unrelated correction is still a violation; reviewer should request reversal rather than letting overlap creep in.

### 5.2 Parallel-start rule and Phase 10 first-hour behavior

P10 can start concurrently even though P04–P09/P11–P13 code has not yet landed. Its initial deliverable is a **missing-module-safe registry and packager**, not a claim of full 13-phase integration. Registry entries are activated only for modules that exist, validate, execute and passed contract tests. Integration PR initially remains draft; P10/integrator updates it as separately reviewed modules arrive.

Phase 1–9 and 11–13 need no live dependency on phase 10 for their first slice. Each validates pure payloads and runs independently in real Blender fixtures. Their operation's canonical name and function signature are frozen in §3. P10 may supply minimal sample context objects for test adapters without mutating their code.

### 5.3 Interface mismatches

If two phases disagree on a semantic field, do not have one agent silently change another:
1. Record mismatch: operation name, field, old/new expected type, evidence and failed test.
2. Propose a neutral adapter in P10's owned integration namespace.
3. Prefer additive versioned fields and capability negotiation to breaking changes.
4. Preserve old API until every consumer moved and tests pass.
5. Integrator reviews and merges with explicit migration test.

## 6. Hard timebox and status protocol

The user's target is approximately **30 minutes per agent**, with all 13 working concurrently if separate ChatGPT tasks can be started. This is a strict *planning timebox*, not a promise that a truly film-quality humanoid/renderer/physics stack fits into thirty minutes or that work continues invisibly after a chat has ended.

| Target elapsed time | Required result |
|---|---|
| 0–4 minutes | Read canonical doc/ownership and current source. Baseline test/branch identity verified |
| 4–8 minutes | Define narrow implementation and exact native outcome, write failing regression |
| 8–20 minutes | Implement a working bounded vertical slice in owned paths |
| 20–25 minutes | Native bpy/Android/host tests; check artifact and pre/postcondition |
| 25–28 minutes | Commit, PR against integration, produce machine-readable phase report |
| 28–30 minutes | Report accurate status, achievements and unverified blockers |

**No false deadline completion:** If a phase requires more than one 30-minute increment, report Partial and keep its PR draft, with concrete next steps. Do not fill remaining gaps with untested code or generic documentation and label Complete.

### 6.1 Machine-readable report contract

A phase MUST write a syntactically valid JSON document at reports/omega/PHASE_NN_RESULT.json. Required minimum fields (the example is schema guidance; replace all invented values with actual evidence):

    {
      "contract": "RENDER-OMEGA-13P-20261022",
      "phase": 11,
      "title": "True autonomous artist tool controller",
      "status": "Partial",
      "seed_sha": "40 hexadecimal characters from Git",
      "head_branch": "feature/omega-P11-artist-controller-20261022",
      "head_sha": "actual Git commit SHA",
      "pr_url": null,
      "owned_paths_changed": [],
      "real_bpy_tests": {"state": "NOT_RUN", "commands": [], "results": []},
      "android_tests": {"state": "NOT_RUN", "reason": "no device attached"},
      "native_receipts": [],
      "artifacts": [],
      "quality_reduced": false,
      "residual_blockers": [],
      "unverified_claims": []
    }

**Status semantics:** Complete = assigned 30-minute phase slice truly implemented and its required focused gates pass, with PR and receipts. Partial = some real verified functionality, but mandatory slice or proof missing. Blocked = no verified slice due to a concrete access/tool/hardware/dependency restriction. Use the single exact word Complete as the last word of the phase report only when Complete. Otherwise last word is Partial or Blocked.

### 6.2 Human-visible progress requirements

All agents should present a brief meaningful progress statement at initiation, after initial source inspection, after first working code and after test results. Progress is not a substitute for a commit or proof. A ChatGPT chat is NOT a durable 30-minute background executor unless a task infrastructure is explicitly running; do not promise unseen work after returning a response.

---

## 7. Cross-phase neutral contracts for real artist autonomy

### 7.1 Native artist action payload — P11 producer, P10 dispatcher

Every supported artist step must specify an existing owned native Blender project, target type/object name/scene revision, operator family, normalized typed parameters and expected postcondition. Example *semantic shape*, not a generic remote scripting endpoint:

    {
      "operation": "omega.artist.execute_tool",
      "payload": {
        "tool": "mesh.sculpt_stroke",
        "target": "CharacterBody",
        "expected_mode": "SCULPT",
        "expected_scene_revision": "<sha>",
        "parameters": {
          "brush": "DRAW",
          "radius": 0.07,
          "strength": 0.32,
          "samples": [[0.1,0.2,0.3],[0.2,0.2,0.3]]
        },
        "postcondition": "evaluated_mesh_changed"
      }
    }

**Example does not guarantee the specific Blender build supports this brush.** P11 must inspect actual native enum and context. Reject unsupported brush/mode/operators. Never interpret generic strings as arbitrary bpy.ops identifiers. Real event injection must remain within Render's own foregrounded Blender view and authorized Android UI.

### 7.2 Self-critique / revision payload — P12 to P03/P11

A grounded quality finding uses observations, provenance and a bounded action proposal, not subjective magic ratings:

    {
      "source_revision": "<sha>",
      "target_object": "CharacterBody",
      "measurement": "shoulder_width_over_head_width",
      "observed": 3.6,
      "reference_target": {"min": 1.8, "max": 2.5},
      "evidence": {"kind": "measured_mesh", "view": "front"},
      "repair": {"tool": "mesh.adjust_region", "parameters": {"region": "shoulders"}},
      "max_iterations": 2,
      "visual_quality_verified": false
    }

Values here are **illustrative**, not universally correct human anatomy thresholds. Phase P12 must declare fixture-specific tolerances, scene scale, reference context and uncertainty; do not hard-code those illustrative values as universal aesthetics or apply corrections without valid tool parameters.

### 7.3 Revision + recovery transaction

Before any potentially destructive multi-operation execution: verify project revision → save app-owned checkpoint → validate all arguments/preconditions → run action on actual Blender main context → read back Blender state → audit agreed postcondition → commit updated revision/receipt → continue. On interruption: inspect journal and native scene to determine whether effect was committed; never unconditionally repeat a sculpt stroke or duplicate an asset.

If an operation requires a GUI but the editor is backgrounded, return AWAITING_DEVICE_FOREGROUND and queue safely. A cloud command being accepted is not native completion. User permissions and an accessible Render app remain meaningful even when the owner asks for autonomy.

### 7.4 Storage, security and app independence

- Native project data, snapshots, render masters and trace receipts stay app-owned unless the user explicitly grants a folder or export location. Support SAF and Google Drive as owner-selected storage, not computation.
- No Gallery scans. Accept only explicit media share/picker grants. Preserve original user reference images and their content hashes without repackaging private files in GitHub PRs.
- Do not expose owner token/credentials, keystore, arbitrary paths or read/write entire phone just because the user delegates project work. Design broad **Blender capability coverage** within authenticated, typed, auditable app operations.
- All code respects Blender/copyleft source availability and independent licensed-asset provenance. If upstream Blender project disappears, an already installed offline engine may continue; *future rebuilding* still requires preserved source/toolchain/dependencies and licenses.

---

## 8. Integration acceptance matrix

Each test must identify **real engine, real native data, real output, Android/device evidence or synthetic-only evidence**. No test is permitted to collapse those categories.

| ID | Target feature | Mandatory fixture / validation | Expected proof |
|---|---|---|---|
| INT-01 | Real Blender boot and input | Android portrait ↔ landscape ↔ background ↔ resume | Same project ID/scene, usable controls, no reset |
| INT-02 | True edge-loop geometry | Two pillars → bridge edge loops → save/reopen/undo | Connected manifold native mesh and normals |
| INT-03 | Character anatomical quality | 0.24 distorted silhouette vs repaired character | 3-view geometry, proportions, actual editable mesh; no “finished” primitive |
| INT-04 | Native skinned rig | Humanoid and 4-legged dog fixture | Vertex weights, deformer changes and IK/FK evidence |
| INT-05 | Action choreography | Walk loop, punch combinations and NLA retime | Bone curves and evaluated contact metrics |
| INT-06 | World staging | Train field + ruined temple + lights/sky/scatter | Native instanced assets and camera render |
| INT-07 | Materials/VFX | Same scene WIP/RAW/FINAL | Native node graph/passes and verified pixel difference |
| INT-08 | Simulation | Rigid debris collision + imported fluid-cache series | Native evaluated physics or explicitly declared imported simulation |
| INT-09 | Full-quality still render | Requested engine + dimensions + samples | Exact valid image file, content checksum, no alias engine |
| INT-10 | Interrupted animation | Frames 101–105, kill at 103, resume | No duplicate valid frames; final encoded output |
| INT-11 | Lossless project recovery | Dirty scene, corrupt latest, valid previous snapshot | Verified rollback copy and saved scene restored |
| INT-12 | Artist control | Real Blender sculpt stroke, modifier, selection | Measured change, native target and truthful command hand |
| INT-13 | Self-correction | Deliberately bad character/object | Evidence-based defect, bounded repair and re-audit |
| INT-14 | Agent security | Invalid tools, paths, UUID, oversized request | Rejected without project mutation |
| INT-15 | Native APK integrity | Original signed Android package and bundled Omega modules | apksigner/aapt, runtime ZIP, required native libraries |
| INT-16 | On-phone endurance | Five-minute complex scene test plus thermal | Measured pause/recovery, exact output request, actual Android logs |

For INT-03 and INT-13, visual resemblance is not guaranteed by a numeric geometry score. Record both mechanical/geometry tests and human-readable visual evidence; keep the final artistic quality gate open until the owner evaluates actual output if necessary.

## 9. Staged merge and verified release procedure

**Wave A — isolated checks:** Each phase PR contains only its owned implementation, fixtures and reports. Verify source paths. Merge in the order dictated by test readiness, **not** merely ascending phase number. Independent native math modules can merge without P10 registry activation.

**Wave B — registry integration:** P10's adapter/registry PR merges after core contracts stabilize, then integrates successfully tested phase modules by operation ID. Fail disabled/missing capabilities gracefully, never crash engine startup because one phase module is absent.

**Wave C — combined Blender/Android verification:** Run real Blender bpy fixtures for true mesh/sculpt/rig/action/world/physics; run Android unit/JNI tests; build actual pinned Blender APK and verify embedded modules. Exercise the existing VideoStudio MCP → Render authenticated Binder path with an actual native command and inspect returned scene data.

**Wave D — original-package on-phone tests:** Confirm existing installed package/version/signature, snapshot its app-owned project files with owner consent, install only an APK bearing the exact same accepted signer and higher versionCode. Test phone Vulkan, slow renderer, thermal stress, background/return continuity, rendering and saved asset/PNG/MP4 bytes. Do NOT uninstall or clear data. Don't claim a permanent signing certificate has been installed unless its protected storage and exact cert match are verified.

**Wave E — owner acceptance/release:** Only after tests and owner instruction, approve a release candidate. Failing tests yield a draft PR and an explicit blocked matrix; a successful GitHub desktop build alone does not authorize installation.

## 10. Direct launch instruction for every ChatGPT agent

The owner can paste the following template into thirteen ChatGPT conversations and change only the integer N. All agents read the same one master document. The phase number in the user's instruction is authoritative even if the chat has no previous history.

> Implement RENDER OMEGA Phase N autonomously. Repository: RezoxNemesis/Render. Read the single canonical master blueprint at https://github.com/RezoxNemesis/Render/blob/integration/render-omega-ten-phases-20261022/docs/omega/RENDER_OMEGA_TEN_PHASE_MASTER_BLUEPRINT.md completely. Your assigned number is N; execute ONLY Phase N. Use its pre-created branch from the frozen phase seed and follow its exact path ownership, typed operation contracts and acceptance tests. Work toward the 30-minute engineering timebox without sacrificing correctness. Implement real code and native Blender tests, commit, open/update your draft PR targeting integration/render-omega-ten-phases-20261022, and write reports/omega/PHASE_NN_RESULT.json. Do not modify other phases, shared registry, signing, master blueprint or main. Never fake tool actions or visual/render quality. End with Complete ONLY if the specified phase-slice deliverable is actually implemented and verified, otherwise Partial or Blocked with precise evidence and remaining work.

The 30-minute clock starts when the individual agent receives this instruction; there is no global background orchestrator implied. If the owner has only ten chats available, phases 11–13 can be assigned to additional chats later with the same seed, but concurrency does not change the 13 independent code ownership boundaries.

## 11. Final definition of success — no shortcuts

Render OMEGA is an autonomous **artist-operated 3D studio**, not merely an Android port that opens the Blender toolbar. It succeeds when a user can describe a scene and ChatGPT can perform real native steps—create, sculpt, mesh-edit, rig, animate, light, composite, simulate where supported, render, correct, save and export—with verifiable receipts and minimal repeated owner input.

Feature support is measured **against the actual installed engine**, not desktop branding. If the owner requests an unavailable native simulation, plugin, memory quantity or Vulkan feature, the app must preserve the project, explain the exact unsupported requirement and offer an explicit consented alternative. It may not substitute a fake video, silently lower requested quality or claim an unseen feature was implemented.

**The blueprint is complete when this authoritative document and all thirteen identical-base branches exist.** Phase implementation completion is a separate, test-gated milestone; thirteen branches created is not proof that Blender film-quality goals are already met.

**END OF THE ONE RENDER OMEGA 13-PHASE MASTER ENGINEERING BLUEPRINT.**
