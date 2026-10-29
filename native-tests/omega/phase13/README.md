# OMEGA P13 native Blender fixture

Run against the actual available Blender interpreter:

```bash
python3 -m unittest tools/omega/test_phase13_contract.py -v
blender -b -noaudio --python-exit-code 1 --python native-tests/omega/phase13/real_blender_fixture.py
```

The fixture creates **three genuine native mesh colliders** (two active rigid
bodies and a passive ground), executes 36 sequential frame evaluations, checks
actual evaluated physics motion, checksums each app-scoped cached frame,
checks the idempotency receipt, saves a true `.blend` copy, reloads it, and
re-evaluates physics after reload. It does not fake physics with keyframes.
`SAMPLED_NATIVE_PHYSICS` is explicitly requested and does **not** claim Blender
point-cache baking. A native point-cache bake request fails explicitly unless
the Blender `ptcache.bake` operator confirms `is_baked`.

This host fixture is not an Android-native/ARM64 verification. P10 must package
the module and test it on the owner's installed native Blender engine before
exposing either operation as an installed capability.
