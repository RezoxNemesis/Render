# OMEGA Phase 07 — native motion fixture and typed API

This phase owns only the motion module and test fixtures. P10 is solely
responsible for native Android startup ZIP inclusion and dispatch registration.
The Blender module can be imported without `bpy` for pure validation tests.

## Operation: `omega.motion.create_actions`

The default `kind: "walk"` creates **one actual Blender Action and NLA strip**
on an existing armature using five pose F-curves: armature-local Root Y
translation plus both thigh/shin X rotations. Input is an exact JSON object:

```json
{
  "rig": "OMEGA07_TestRig",
  "clip": "WalkCycle",
  "kind": "walk",
  "start": 1,
  "frames": 25,
  "stride": 0.36,
  "clearance": 0.075,
  "contact_z": 0.12,
  "retime_scale": 1.0
}
```

Only `rig` and `clip` are mandatory. `frames` must be between 13 and 121,
with `(frames-1) % 4 == 0`. The biped's root, left/right thigh and shin bones
default to `Root`, `LeftThigh`, `LeftShin`, `RightThigh`, `RightShin`.
For another naming convention provide all five keys in a `bones` object or
put equivalent JSON in the armature's `omega_motion_channels` custom property.
No other operation names, arbitrary Python, operator strings or filesystem
paths are accepted.

The current walk solver **requires** straight-down FK legs, an XYZ rotation
mode, root-parented thighs and shin-parented knees, with local +Y travel.
Unreachable contact goals or incompatible rigs fail, without fake animation.
Both feet are sampled from native evaluated shin-tip transforms at each gait
keyframe; **skinned sole and exact visible toe contact are not yet verified**.
Translation is stored on the root *pose bone*, not the whole armature object.

To retime an existing strip without changing underlying F-curves:

```json
{"rig": "OMEGA07_TestRig", "clip": "WalkCycle", "kind": "retime", "retime_scale": 1.5}
```

Requests reject a new action on a rig with conflicting active animation,
reject clip-name/revision conflicts and honor context cancellation before and
during keyframe writing with rollback. `context.job_id` may be a validated
32-character lower-case hex key and prevents cross-clip duplication. A dry run
rejects mutation explicitly rather than creating a false success receipt.

## Operation: `omega.motion.audit`

```json
{"rig": "OMEGA07_TestRig", "clip": "WalkCycle"}
```

Read-only results include native Action/NLA names, curve count, total keys and
SHA-derived action-key fingerprint; root samples and per-cycle stride; NLA
start/end and scale; loop-seam rotation error; evaluated planted-foot XY drift
and vertical shin-tip penetration. Scene frame/subframe is restored after
sampling. No render-quality settings are modified. JSON receipts mark visual
quality as **not** verified until independent inspection.

## Verification commands

```bash
python -m unittest discover -s tools/omega -p 'test_phase07_*.py' -v
python -m compileall -q full-app/scripts/omega tools/omega native-tests/omega/phase07
blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase07/test_native_motion.py
```

The first two checks can run without bpy. The third requires an actual
Blender executable. It builds an independent native armature, creates NLA
animation and two Blender cameras, checks keyframes/loop/foot contact,
saves a real `.blend` in a temporary folder, reopens, retimes, saves and
reopens again. The code exists, but a fixture not executed on Blender is
**not** evidence of native passing. On-device Android renderer certification,
jab/cross/hook actions, paw contacts and production skinned foot quality remain
separate acceptance tasks.
