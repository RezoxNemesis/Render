# Native character review and sculpt preparation

Use the existing `production.execute`/VideoStudio Binder connection and discover
schemas with `artist.capabilities`. All work executes inside Android Blender.
No image-to-3D generator, new MCP server or arbitrary Python entrypoint is added.
The supplied reference is guidance, not proof of measured proportions or likeness.

1. Save the editable proportion blockout with `project.checkpoint`.
2. `camera.frame` accepts a target mesh `object`, new camera `name`, `view`
   (`FRONT`, `BACK`, `LEFT`, `RIGHT`, `THREE_QUARTER`), optional `aspect` and
   `margin`. It creates an orthographic review camera using evaluated world
   bounds. Set aspect to the intended output width/height. It preserves geometry,
   existing cameras and render quality; the new camera becomes active explicitly.
3. `viewport.orient` accepts `object`, `view`, optional `margin`; it sets actual
   native viewports to the chosen orthographic orientation without fake input.
4. Explicitly choose a preview profile/engine and render the body first. Workbench
   samples now refer to its actual `display.render_aa`, rather than EEVEE settings.
   Unavailable antialias counts fail; OFF/FXAA require explicit supported numeric
   samples for this durable-job pipeline. Native Blender retains those modes.
   Engine changes inherit the selected engine's sample count, preserving others.
5. After proportion review, `sculpt.prepare` accepts `object`, a new `name`,
   explicit `voxel_size_m`, optional `max_voxels` (default 8 million), `hide_source`
   (default false), and `require_connected` (default true). It copies evaluated
   geometry, bakes world transforms in the copy, and invokes native voxel remesh
   at the requested physical resolution. It checks connected components before
   accepting a continuous surface. The original mesh remains editable. Source
   visibility changes only when explicitly requested; failures remove the copy
   and retain the pre-edit checkpoint. This prepares a surface, not a sculpted
   body, face or likeness.

Voxel admission uses padded evaluated bounds and an explicitly heuristic memory
estimate against Android's actual `MemAvailable`. Missing signals, excessive
budgets or insufficient memory fail clearly; resolution is never coarsened
automatically. Native allocations can exceed the estimate. Voxel remesh changes
topology, so this entrypoint rejects rigged, animated, shape-keyed or UV-mapped
sources. The source and checkpoint remain available; unrestricted native Blender
workflows are retained. Sculpt brush strokes still require an active native brush
and valid viewport. No desktop parity or superiority claim follows from more
automation controls.

Checkpoint again before anatomical refinement, then work on the face, hair,
clothes, materials and rig separately. Successful operations alone do not verify
visual quality. Inspect actual native images and retain exact command results
before retrying any uncertain mutation.
