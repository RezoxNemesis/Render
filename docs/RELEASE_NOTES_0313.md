# Render Studio 0.31.3 — staged character review

`com.rezox.render`; versionCode **39**; versionName
`0.31.3-character-review`. Retains the 0.31.2 engineering changes and the same
native engine. Existing private VideoStudio credentials/Binder transport remain.

- Fixes a concrete engine-settings bug: Workbench antialiasing no longer reads
  or changes EEVEE samples. Preview engine overrides inherit the selected engine's
  samples. Unsupported counts fail; final artist settings are not reduced.
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

The first host verification recorded **66 passing focused checks**. Workbench
regressions were observed failing before the settings fix. Host admission checks
do not execute Blender or verify an image. Build/native evidence is tracked
separately; no native render or sculpt result is established by these changes.

The workspace previously suffered repeated host Mesa mapping aborts and an ARM
translator F16C failure during EEVEE rendering. Native Workbench proportion
rendering is being checked separately. No exact likeness, superiority to desktop
Blender, measured performance gain, phone/thermal result, uninterrupted 24-hour
execution, native final-quality image or completed character is claimed.
Android background restrictions and force-stop behavior still apply.

Use the historical signing identity only; installed-phone compatibility still
requires matching its certificate. Never uninstall/clear data to bypass a mismatch.
The existing signing workflow fails rather than inventing another key.
See [native character controls](NATIVE_CHARACTER_REVIEW.md) and
[the prior runtime evidence](WORKSPACE_TESTING_0312.md).
