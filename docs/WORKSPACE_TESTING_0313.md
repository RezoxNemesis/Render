# Render 0.31.3 native character review evidence

The owner requested a render of the existing body before sculpting/detailing,
and app improvements if that could not be produced. All actual scene work used
Render's Android Blender. No desktop/cloud Blender, external generator or Gallery
enumeration was used. Private references, body files and screenshots stay outside
this application repository.

## Native execution on source 9ee39ae

The owned Android 15/API 35 x86_64 emulator translates the packaged ARM64 Blender
through Berberis. It has no KVM; this run used Lavapipe, one software-GPU worker,
3 GiB guest RAM and two virtual cores. A Java debugger and host mapping observer
were attached for diagnosis. These are not normal startup/performance conditions.

- Android accepted the historical-signer versionCode 39 update without clearing
  app data. The independent APK SHA-256 was
  `f624a0aeea8a3f41b50a86501bbb6b936a4e79dd28c743ee7842fa0db5f1f6e2`.
- The first readiness wait expired before any command ID was published. The same
  native process remained open; a read-only wait resumed without relaunch. A stale
  PID 5111 readiness record was rejected. The live timer then identified PID 3750
  and the actual current NativeActivity launch UUID.
- Native capability discovery reported `camera.frame`, `viewport.orient` and
  `sculpt.prepare`. Discovery alone does not establish execution success.
- `project.restore` loaded the previously hash-verified Stage 1 body. Scene
  inspection confirmed its **2,720 base vertices / 2,360 polygons**. The new
  `camera.frame` created a **FRONT orthographic** camera, vertical sensor fit,
  aspect **0.75**, margin **1.15**, ortho scale approximately **1.8975**.
  `viewport.orient` completed against the actual native viewport.
- The explicit preview profile selected Workbench, **960×1280**, **32 samples**,
  100% output scale. Before/after native quality inspections were identical:
  configuring the preview did not change the active/final artist settings.
- A review-setup BLEND checkpoint was saved with file/directory fsync and atomic
  publication receipts: **173,685 bytes**, SHA-256
  `20afdbda9fd8eaebf58d95b2595f9ba77665bd71df2e0d21b107d36e961af113`.
  It was independently pulled and matched again after the native abort.
- A native PixelCopy viewport capture was independently verified. It was taken
  before the view-alignment operation completed and is not a camera-render image
  or evidence of accepted body proportions.

The actual one-frame Workbench job was
`789616bc73fe4d7d8a2b8c8dd861609b`; exact native command
`a4da546ea81243afa502367a5ec38b06`. At 10:52:53 UTC, Blender reported rendering
frame 1 with the Workbench engine. At 10:53:53 it aborted:

```
ndk_translation/intrinsics/arm_to_x86_32_or_x86_64/intrinsics.cc:28:
CHECK failed: host_platform::kHasF16C
Fatal signal 6 (SIGABRT)
```

This is the same unavailable ARM-translator CPU path seen in the earlier EEVEE
attempt, now reproduced with Workbench. The job manifest retained **0/1 frames**;
the original exact command remained claimed without a result when polled. No
mutation was replayed, no other renderer was blindly retried and no completed PNG
or movie is delivered. No failed host mmap syscall or host Mesa abort was observed
in this particular attempt; that does not explain the earlier separate GPU aborts.

Sculpt preparation, anatomical sculpting, facial detail, hair, garments and rigging
were not started after the failed first-render gate. The body remains an early
estimated proportion draft. Exact likeness, all-angle proportion acceptance and
final-quality rendering remain unverified.

## Engineering follow-ups and coverage

The final legacy-Workbench compatibility follow-up preserves the actual saved
snapshot antialiasing rather than applying its old foreign EEVEE count. New jobs
record the correct sample-control identity. Current-log F16C classification and
out-of-band `connection.diagnose` add actionable runtime-compatibility reporting;
they do not modify Blender's engine, quality or thermal protections.

**68 focused Python host checks** passed for settings, old snapshot behavior,
body inputs, camera/sculpt admission math, packaging, checkpoint failures and HUD
contracts. **16 targeted Android/JVM checks** passed for startup-log selection,
current-versus-historical CPU failure classification, typed bridge boundaries and
diagnostic dispatch. Failures were observed before the corresponding fixes.
These use host fixtures, not native image or sculpt acceptance.

The delivered APK's exact source, signed CI run, SHA-256, certificate and runtime
payload verification are recorded with its artifact evidence. Native results
above belong to source **9ee39aee1b10c24de33919a73c9c68b012248d92**. The final
0.31.3 diagnostic build, source **1fa53bf81a4196965f4983dc117f739e380f4dd9**,
was separately installed with the historical signer in the owned emulator. A
local Android `connection.diagnose` call returned editor-not-ready and the
observed F16C runtime-compatibility failure with automatic retry unsafe. That
check did not verify remote Binder authentication or rerun the native render.
Full native sculpt and final-image success are not inferred from host checks or builds.

No physical phone was operated. Remote VideoStudio authentication/reconnection,
realme/Dimensity performance and thermals, final-output comparisons and 24-hour
execution were not validated. Android restrictions/force-stop behavior apply.
The fixed private executor/inner ProductionBridge checks do not establish a
remote Binder authentication pass. Further character work requires a compatible
native Android runtime with working render support.
