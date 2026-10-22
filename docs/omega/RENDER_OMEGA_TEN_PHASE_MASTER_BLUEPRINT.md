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

