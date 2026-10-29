# Render 0.22 reference-driven production engineering

## User goal and existing failure

Preserve the complete bundled Android Blender engine and the current VideoStudio 3.5.5 -> native Binder connection, while improving reference fidelity, direct media import, visible truthful interaction, screenshots, viewport precision and long animation recovery. The prior portrait was assembled from generic geometry without importing the original reference, aligning a camera or verifying likeness. Successful object/keyframe receipts were wrongly treated as visual progress. More objects or subdivisions alone do not establish correct anatomy, fabric folds or identity.

## Implementation scope

1. Add a versioned native studio operation catalogue with argument schemas and runtime capability checks. Preserve current public ID, app package, data and installed signing certificate. Separate control-plane reachability, native editor readiness, UI visibility and actual native execution.
2. Add an Android reference inbox: ACTION_SEND/ACTION_SEND_MULTIPLE and explicit file selection for images/video. Copy only individually user-granted content URIs into hashed app-private files. Validate decode/type/size and preserve originals. Allow explicit video frame sampling and list only imported references, never enumerate Gallery.
3. Bind reference assets to a Blender scene, packed images and camera-aware landmark guides. Measure projected landmark error against an explicit image crop; label the metric, never invent a 90%-100% likeness score. Preserve and expose the provenance of assets, camera and annotations.
4. Expose native UI state, selection, actual menu opening and bounded event simulation where supported. A hand overlay follows observed Blender input events; data-API commands are labelled as native operations, not fabricated mouse clicks. Owner Stop and app scoping remain intact.
5. Improve detailed controls using runtime RNA discovery: inspect objects/topology/materials and describe validated modeling operators before execution. Never guess parameters or silently substitute cubes for unsupported operations. Keep file/network/shell operations scoped to existing project/import/export APIs.
6. Add viewport diagnostics and scale-aware clip/orbit controls. Change only viewport settings when requested; do not lower mesh resolution, texture limits or final render quality.
7. Fix render resume accounting for non-1 start frames, journal actual pauses and recover missing/corrupt frames explicitly. Plan five-minute frame counts, disk estimates and measured throughput separately from promises of completion. Keep snapshots/PNG masters and the current native codec path.
8. Capture Render's own visible window even when focus belongs to an overlay, without capturing other apps. Validate actual window visibility/lifecycle and retain size/memory bounds.

## Testing and release gates

Pure contract tests, Android unit tests, real Blender synthetic fixtures, runtime packaging/version checks and same-certificate APK verification must pass. Synthetic desktop Blender tests are not user rendering and are not proof of Android UI/GPU/codec behavior. Physical-device checks remain required for import/share intents, actual hand/event alignment, screenshot capture, viewport artifacts, process recovery and sustained five-minute rendering.

Work stays on a draft feature branch; no main merge, automatic installation, new relay, cloud Blender, Gallery browsing, signing-key rotation or clearing of app data. Baseline package com.rezox.render, versionCode 24, installed signer SHA256 f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30. Candidate versionCode 25. Private owner credentials are never copied into source.

## Evidence limits

Reference import, guides, camera fitting and detailed controls enable a better authoring process; they do not constitute an automatic learned single-photo-to-photoreal-rigged-human model. Unseen back/feet geometry remains inferred unless more reference views are provided. The goal is correct source-guided modeling, not a photo billboard disguised as a 3D reconstruction. No completion claim is accepted without native results and actual visual comparisons.
