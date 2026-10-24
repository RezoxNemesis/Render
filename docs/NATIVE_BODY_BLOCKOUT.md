# Native body proportion stage

`production.execute` operation `body.blockout` creates a new editable body
blockout inside Render's Android Blender main thread. Discover its closed input
schema with `artist.capabilities`. Supply a new `name`, `proportions` in metres,
and optional `subdivision_levels` (0–3, default 2). Unspecified dimensions scale
with the requested height; explicit measurements are retained.

Controls cover height, head height/width, shoulder/bust/waist/hip width, bust/
waist/hip depth and upper-arm/thigh/calf diameter. Nonfinite, unsupported and
inconsistent dimensions fail explicitly. The current scene is checkpointed before
creation. A frozen render snapshot cannot be edited. No existing objects, scene
quality settings or original references are replaced.

The first stage contains closed editable volumes for torso/pelvis/neck, head,
arms, hands, thumbs, legs and feet. It uses a neutral relaxed arm pose. Its
response and saved object mark `sculpt_union_pending=true`: it is a proportion
blockout, not a joined sculpt surface or finished character. Fingers, facial
likeness, garments, rigging and final rendered realism are not completed by this
operation. Subsequent sculpting/retopology must be separate consequential stages
with new checkpoints. Presence in capabilities is not a runtime acceptance pass.

Use front/side/back references to choose explicit dimensions. A reference sheet
is design guidance, not proof of physical measurements or a 3D scan. Keep private
reference images and character projects outside the application source repository.
