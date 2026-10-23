# Vulkan timeline counter startup fix

The pinned Android engine calls `vkGetSemaphoreCounterValueKHR` directly in
`VKDevice::submission_finished_timeline_get()`. Its initialization aliases a
missing **core** function to the KHR function, but does not provide the reverse
alias. A logical device exposing the promoted core function can therefore
crash at address zero even though its Vulkan feature checks pass.

An actual Render process on the Android 15 workspace device demonstrated this:
the instance-level JNI query exposed both names, while the native debugger
found a valid core device-table pointer and a null KHR pointer. The ARM guest
backtrace identified the call at `libblender.so+0x5fc19d0`. The older Android 12
translation runtime had neither device pointer, a separate compatibility limit.
These observations do not establish the owner's physical phone's fault cause.

The source fix calls the existing aliased core entry. Extension-only drivers
retain the fallback already established by `VKDevice::init()`. No GPU feature,
modeling tool, scene quality setting, sample count or render capability is removed.

Production staging applies an exact source-equivalent correction to the pinned
ARM64 release library, rather than claiming to have rebuilt all Blender sources:

- The original APK and source revision retain their existing checks.
- The library must match SHA256
  `35bec73f5bfc21179221686f383bfcf92c5b08d3f0f471f74b167a142b6691b9`.
- Eight inlined counter-call field loads change from the KHR table offset to
  the core table offset. Only 16 bytes change. The fallback initialization,
  unrelated fields and every other engine byte are preserved.
- ELF architecture, executable segments, expected instructions and following
  indirect calls are checked. The result must match SHA256
  `a87b805df88ab64b4af21baac98bf380de9b0a1d90ac5525c082c5aceac29d59`.
- Unknown libraries are rejected. The verified input APK is never modified.
  The corresponding source diff and exact patch provenance ship in APK assets.
  The upstream compiler Build ID remains unchanged; use the library SHA256 and
  patch manifest to distinguish this corrected artifact.

This is version `0.28.3-vulkan-timeline-fix`, Android code 33. The original
package/signing configuration is preserved. Workspace APKs use a separate test
key and are not install-compatible phone updates.

Validation: twelve packaging/guard tests passed, including unchanged-payload
checks and rejection of unknown hashes, wrong ABI, non-executable locations and
unexpected call instructions. The source diff applies to the exact pinned Git
index. Actual full-engine staging and the complete Android APK build passed;
the staged/packaged corrected engine and unchanged runtime ZIP hashes matched.

A debugger-only alias repair first routed the pending call through the real
core function without skipping it. A subsequent cold process start used the
exact packaged corrected library, with no debugger repair, and completed
startup-file loading, GPU UI resource initialization, Python and `WM_init`.
For this isolated userdebug test, only the extracted engine library was
atomically replaced after stopping the app and checking both hashes. Installed
APK metadata remained 0.28.2; a whole 0.28.3 APK install is not claimed. No app
data or owner-phone files were cleared or changed.

This verifies cold-start progress beyond the captured crash. A usable native
viewport, the agent heartbeat, physical phone behavior, character likeness and
completion of an animation still require their own actual results.
