# 0.28.2 loader diagnostics and repeatable runtime packaging

Render now distinguishes the Vulkan loader API exposed to its ARM64 process
from the physical driver's advertised API. The read-only JNI report requests
at most Vulkan 1.3, checks both timeline-counter instance dispatch names and
labels logical-device dispatch and Blender readiness as unverified. These
queries are diagnostics, not a substitute for a Blender heartbeat or a render.

The workspace debugger intercepted the existing Android 12 ARM-on-x86 crash
before signal delivery. The guest PC was zero; the return address resolved to
`VKDevice::submission_finished_timeline_get()` at the pinned engine's
`vkGetSemaphoreCounterValueKHR` call. Both its core and KHR device-table
pointers were null. This establishes the failing call in that translated test
runtime, not the cause of a fault on the owner's ARM64 phone. The Blender
library was unchanged during diagnosis.

Injected Python scripts now receive fixed ZIP timestamps and file permissions.
A source checkout's metadata no longer changes the runtime asset hash and
unnecessarily invalidates Android's verified runtime cache. Script content
changes still change the archive. Existing upstream ZIP entries are retained.
The staging subclass also covers scripts added by the existing build adapters.

The production build adapter advances to Android code 32 and
`0.28.2-loader-diagnostics`; it accepts the known 0.28.0/0.28.1 predecessor
states and retains package/signing configuration. CI artifact names follow
the new version. The workspace signing key remains a separate test key and
cannot be represented as a phone-compatible update.

Validation: eight packaging tests passed, including byte-for-byte archive
stability across timestamp/permission changes, payload-change invalidation,
original upstream payload preservation, duplicate/collision checks and Omega
module validation. The updated ARM64 JNI code passed the Android native build.
Native editor readiness, character likeness, animation quality and physical
phone thermal behavior remain separate acceptance gates.
