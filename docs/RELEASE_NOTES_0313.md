# Render Studio 0.31.3 — staged character review

`com.rezox.render`; versionCode **39**; versionName
`0.31.3-character-review`. Retains the 0.31.2 engineering changes and the same
native engine. Existing private VideoStudio credentials/Binder transport remain.

- Fixes a concrete engine-settings bug: Workbench antialiasing no longer reads
  or changes EEVEE samples. Preview engine overrides inherit the selected engine's
  samples. Unsupported counts fail; final artist settings are not reduced.
  Older Workbench jobs retain the actual antialiasing saved in their immutable
  snapshot; their previously unused foreign sample counts are not reinterpreted.
- Adds checkpointed `camera.frame` for front/back/side/three-quarter orthographic
  review, evaluated world bounds, explicit aspect and margins. Existing cameras
  and geometry remain available.
- Adds `viewport.orient` for real native orthographic review without simulated
  pointer input or an external renderer.
- Adds checkpointed `sculpt.prepare`: copies the evaluated body, bakes transforms
  into the copy and invokes native voxel remesh at an explicit physical resolution.
  It checks actual connected components and preserves the original editable mesh.
  Voxel/memory budgets fail explicitly instead of coarsening the surface. It is
  sculpt preparation, not a completed anatomical sculpt or facial reconstruction.
- Diagnostics identify the observed Android ARM-translator F16C assertion as a
  current runtime-compatibility failure, with actionable checkpoint/recovery
  guidance. Historical failures are not treated as current evidence. The native
  diagnostic is also exposed through existing `connection.diagnose`; no renderer,
  quality setting or thermal protection changes automatically.

Host verification recorded **68 passing focused checks**, including legacy
Workbench snapshot compatibility. The initial run recorded 66 checks. Workbench
regressions were observed failing before the settings fix. Host admission checks
do not execute Blender or verify an image. Build/native evidence is tracked
separately; no native render or sculpt result is established by these changes.
Sixteen targeted Android/JVM checks also passed for current/historical log
selection, failure classification and diagnostic dispatch.

The workspace previously suffered repeated host Mesa mapping aborts and an ARM
translator F16C failure during EEVEE rendering. The new native Workbench body
attempt created its orthographic camera and saved its review setup, but the
actual frame also aborted on F16C: **0/1 completed frames**. No sculpt stage ran.
See [build-specific evidence](WORKSPACE_TESTING_0313.md). No exact likeness, superiority to desktop
Blender, measured performance gain, phone/thermal result, uninterrupted 24-hour
execution, native final-quality image or completed character is claimed.
Android background restrictions and force-stop behavior still apply.

Use the historical signing identity only; installed-phone compatibility still
requires matching its certificate. Never uninstall/clear data to bypass a mismatch.
The existing signing workflow fails rather than inventing another key.
See [native character controls](NATIVE_CHARACTER_REVIEW.md) and
[the prior runtime evidence](WORKSPACE_TESTING_0312.md).
