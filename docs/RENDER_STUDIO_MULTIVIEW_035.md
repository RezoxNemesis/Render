# Render Studio 0.35.0 — Coupled multi-camera mesh fitting

Package `com.rezox.render`, candidate version code **44**, built on the
original full ARM64 Blender engine and historical signing identity.

## Why this upgrade exists

Fitting a body or face against a front reference alone can deform the side
profile. The new `reference.fit.multiview` operation solves shared 3D vertex
displacements against **2–6 real Blender cameras at once**. Every vertex to be
modified must have at least two reference observations. The operation does not
claim one photo reveals unseen geometry or produce a fabricated visual likeness
percentage.

### Authenticated operation

Use the existing private VideoStudio/Render connection and target ID. After
confirming `production.execute` and `artist.capabilities`, supply:

```json
{
  "operation": "reference.fit.multiview",
  "target_id": "<exact connected Render public UUID>",
  "payload": {
    "object": "Character",
    "expected_vertices": 1000,
    "views": [
      {
        "camera": "FrontCamera",
        "reference": {"left_eye": [0.34, 0.42], "right_eye": [0.63, 0.42]},
        "model": {"left_eye": 140, "right_eye": 170}
      },
      {
        "camera": "SideCamera",
        "reference": {"left_eye": [0.49, 0.41], "right_eye": [0.55, 0.42]},
        "model": {"left_eye": 140, "right_eye": 170}
      }
    ],
    "strength": 0.65,
    "max_displacement": 0.10,
    "regularization": 0.005,
    "dry_run": true
  }
}
```

This example illustrates the typed command shape only. The cameras, object,
vertex count and landmark indices **must come from the actual loaded project**
and inspected reference image; never copy these example values blindly.
Inspect and validate the dry-run `rms_before` and
`rms_predicted_after` first. After artist review, repeat the same request
with `dry_run:false`. The existing Render agent checkpoints the native
.blend before consequential geometry modifications.

### Important invariants

- No Gallery enumeration, arbitrary paths, eval/exec or remote Blender Python.
- Reject views whose camera directions are too similar; not a disguised
  single-camera edit.
- Require each edited mesh vertex to be observed from two distinct camera
  views; reject duplicate vertex IDs in one view and out-of-range indices.
- Support only actual Blender perspective/orthographic cameras and active,
  typed mesh objects. Shape-key meshes are deliberately refused to avoid
  corrupting facial animation targets.
- Use bounded numerical camera Jacobians, regularized 3-by-3 least squares,
  maximum world-space displacement, and a proportional strength factor.
- Calculate the **combined** predicted projection error across all views and
  refuse edits predicted to worsen it.
- Never change camera parameters, scene frame rate, render engine, resolution,
  lighting, external assets or existing rig animations.
- The return metric is geometric projected landmark error, **not** exact
  likeness, identity confidence, skin or clothing texture quality.
- An `applied:false` result may be a valid no-op; no improvement is not success.

## Verification

The Python contracts test invalid camera/vertex maps and bounds. A genuine
Blender fixture runs the two-camera fit on native bpy mesh vertices, both
`dry_run:true` and a committed, measured edit, before creating subsequent
armature/facial animation keys. Android tests cover the typed allowlist.
Physical Android rendering, detailed character topology and automatic
reference landmark extraction remain separate acceptance tasks. Because the
two-reference solver moves only selected mesh vertices, it is an artist aid,
not an automatic character generator.

**Release boundary:** PR #32 is the canonical draft source change; build-only
PR #33 is not a merge target. Preserve saved projects. Install only if the
device-installed certificate matches the pinned historical signing identity.
