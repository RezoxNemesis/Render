# Render Studio 0.32.2 — verified MP4 recovery (versionCode 42)

This is an **in-place candidate**, package `com.rezox.render`, built on top of
the 0.32.1 storage, import, thermal and checkpoint changes. The bundled full
ARM64 Blender engine, historical signing identity and VideoStudio integration
are intentionally preserved. Nothing needs to be uninstalled.

## Improvements

- Validate the H.264 MP4 container before committing an encoded video receipt,
  before trusting an old encoded video during recovery, and before exporting an
  app-produced MP4 to Android Downloads.
- Detect incomplete/truncated MP4 top-level boxes; require a file-type header,
  nonempty media data and a movie track. This is a structural test, not a claim
  that every frame plays or decodes correctly.
- Check that separately encoded segments match their **exact** immutable start,
  end, frame count and part index in both recovery and manual export.
- Preserve an invalid monolithic MP4 with an `.unverified.mp4` suffix before
  regenerating it from source PNG frames. Never overwrite existing quarantined
  evidence; reject quarantined files from Downloads export.
- Preserve the source PNG masters, frame timing, requested quality, native
  Blender project and prior-session checkpoints. No automatic resolution
  downgrade.
- Correct version-42 Android/full-native build and add structural, checksum,
  quarantine, export and frame-plan Android regression tests.

## Tested

- Android MP4 recovery regression suite and Android foundation CI passed on
  the pre-release branch.
- Historical signing certificate SHA-256:
  `f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`
  (repository-pinned certificate, not a scan of the owner's phone).
- Native Android build completed with original `com.rezox.render` identity,
  versionCode 42 and packaged `libblender.so` and `librender_bridge.so`.
- Verified delivered APK SHA-256:
  `f0a21e854fcc3f27e09b4a9bdf68e6d0083f7578a9e1f68846209185002f4af1`.

## Not yet proven

Physical-phone install/update compatibility, actual Blender-to-H.264
animation completion, frame-by-frame playback, audio, Android sleep/force-stop
survival, 24-hour thermal endurance and 10 GiB output handling are **unverified**.
Android may stop execution for OS policy reasons. This upgrade does not
checkpoint in-progress per-sample renderer state within a frame. The separately
chunked format is not a single giant MP4. Device testing must validate MP4
decoding and duration, not only file structure.

The full source review remains draft PR #28, based on draft PR #27. Build-only
candidate PR #29 must not be merged into `main`. Do not uninstall, clear
Android app data, change the signing certificate or force a downgrade.
