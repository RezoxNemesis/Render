# Render 0.32.1 workspace verification

This upgrade retains [the earlier native character evidence](WORKSPACE_TESTING_0313.md).
Private photographs, native projects, command receipts and screenshots remain
outside this public repository. No desktop/cloud Blender, external generator or
Gallery enumeration was used.

## Delivered build

- Code: `f1117d9547b83fb3b347e23828e9e8ad4cb84294`.
- Successful signed CI run: `40100798443`.
- Package `com.rezox.render`, version code **41**, version name
  `0.32.1-native-storage-assets`; **302,259,272 bytes**.
- APK SHA-256:
  `7fcfd6e0fc206a0c14b3f1897c21925362d9dc13b9f516af582b807ae8dbf84d`.
- Pinned historical development certificate SHA-256:
  `f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30`.
- Independent ZIP/certificate/package checks passed. All **146 native libraries**
  match the prior 0.31.3 APK byte for byte, and **21 packaged Python modules**
  match the declared source. This is build identity evidence, not native success.

The final signed APK was installed as an update in the owned emulator without
data clearing. The body-with-reference checkpoint still matched its hash. A
read-only Android production-status check passed and reported the actual
**172,800,000 ms** frame deadline, editor-not-ready, and the inactive worker as
**interrupted** with recovery required. This caught and fixed the observed
`ready` cache with stale `Rendering` detail as well as explicitly in-flight
cached states. It did not start Blender or render another frame.

**77 focused Python checks** and **37 targeted JVM checks** passed. They cover
file scopes, source changes, checksums, duplicate requests, edited destinations,
archives, image admission, setting restoration, unavailable native operators,
interrupted-worker status, long-frame deadlines and exact retained receipts.
Fixtures do not count as native assets or rendered output. No benchmark or
24-hour endurance test was run.

## Actual Android storage and native image results

These native/storage results belong to the tested **0.32.0** APK, code source
`943d7c0fe53528004d3647df76b1eec7dd6940ed`, APK SHA-256
`636c474bcc454cde60f1f4dc0eb6b539c2ae2d25ba91bf35807d25db2b64c0da`.
Later error/UI/deadline and absent-operator handling fixes have separate host
coverage; full native acceptance is not inferred for the final APK.

- Installed the historical-signer candidate in the owned Android 15/API 35
  emulator without uninstalling or clearing app data. Existing native body
  checkpoints retained their hashes.
- Through the production dispatcher and file foreground service, created nested
  app-workspace folders, exported the genuine native body project, independently
  read/hash-verified it, retained the duplicate request result and imported the
  same original bytes into immutable staging. **Passed**.
- Used Android's system folder picker to grant the local **Documents** folder.
  The same production operations created `RenderWorkspace032/Projects`, exported
  and readback-verified the native project, then imported identical bytes.
  **Passed**. This was an Android DocumentsProvider test, not a Drive-provider test.
- Both round trips used **173,685 bytes**, SHA-256
  `20afdbda9fd8eaebf58d95b2595f9ba77665bd71df2e0d21b107d36e961af113`.
  Transfer results correctly reported `native_import_completed: false`.
- The editor subsequently reached a fresh, current-PID/current-launch native
  heartbeat. Native `file.inspect` read the staged Blender project's scene,
  object, collection and material metadata without replacing the active scene.
- Native importer discovery exposed a genuine missing-operator response:
  `KeyError: WM_OT_collada_import not found`. Its exact failed receipt was
  retained. The final fix catches the native RNA `KeyError` and reports absent
  operators unavailable; a host regression covers that observed response.
  The fixed catalog was not rerun on the final native surface.
- Restored the existing body scene. Staged the explicitly supplied original
  portrait through owned-emulator ADB setup, then performed the **actual image
  import through Android Blender's typed `file.import`**, with a checkpoint
  before the change. The original **853×1280** image was packed and kept separate
  from previews; the reference object is excluded from final rendering.
- Native quality inspections before/after the image import were identical:
  EEVEE, **1920×1080**, **100%**, **64 samples**, **24 fps**, original thread and
  transparency/persistence settings. No resizing or sample reduction occurred.
- Saved and independently pulled the editable body-with-reference draft:
  **275,927 bytes**, SHA-256
  `9ef60c34ad0b9357ecde13b01d45cf3854760cd634f085c93f2a858a45799ba6`.
  Geometry remains the original coarse body blockout; no sculpt, facial detail,
  garments, rig or character animation is claimed.

The private spool/instrumentation checks do **not** establish end-to-end
VideoStudio Binder authentication, reconnection or normal ChatGPT routing.

## Drive, HTTPS and interruption boundaries

The connected Drive tool stored the genuine native checkpoints in the artist's
existing private Projects folder. Downloading the body-with-reference project
back from Drive returned **275,927 identical bytes**, matching the native SHA-256.
This verifies a connector storage copy, not cloud rendering or Android Drive sync.
No private folder IDs or account credentials are embedded in the source.

The Android HTTPS original-file route initially returned a retained
`ConnectException` with **zero bytes transferred**. The owned emulator lacked the
managed workspace egress proxy. After configuring that existing workspace proxy,
a fresh, explicit transfer returned `SSLHandshakeException`, also at zero bytes.
The known failed receipt was inspected and retained before retrying; an uncertain
mutation was not replayed. TLS checks were never disabled. The final app maps
these errors to actionable, URL-free recovery hints. Successful native Android
HTTPS ingestion on a trusted network and Android's Drive provider remain
unverified. Connected Drive OAuth is independent of an Android folder grant.

After the native image import and checkpoint pull, the emulator's **host QEMU
process aborted** in Mesa `llvmpipe_map_memory` on `MAP_FAILED`. The last observer
sample showed **64,430 mappings / 65,530 host limit** and memory near the
**16 GiB cgroup limit**; no cgroup OOM kill was recorded. These observations do
not prove which limit caused the failure or a phone/Blender memory leak.
The owned AVD was cold-started without wiping data. Both the original project
and new body-with-reference checkpoint retained their exact hashes afterward.
No render was replayed and Blender was not relaunched after this host abort.

The earlier actual EEVEE and Workbench renders failed in the workspace's ARM
translator on missing F16C, as recorded in the prior report. No completed native
character PNG or movie is delivered. Final native rendering, the fixed catalog
on the final APK, other model/media codecs, physical realme/Dimensity behavior,
remote authentication, performance gains and 24-hour execution remain unverified.
Pause/cancel may wait for an in-flight native frame; durable recovery retains
completed frames and projects, not mid-frame sample buffers. Force-stop prevents
execution until the app is reopened.

The historical certificate does not establish the installed phone's certificate.
No physical phone installation or compatible update claim is made.
