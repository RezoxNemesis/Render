# Upstream Blender source port — verified scope

Official project: https://projects.blender.org/blender/blender
Mirror and pinned commit: https://github.com/blender/blender/commit/fbe82a46101643c5cf8d7ab331d6a47566008fa7 (2026-10-21)

The original GPL-2.0-or-later sources:
- source/blender/blenlib/intern/math_half.cc
- source/blender/blenlib/BLI_math_half.hh

are vendored into third_party/blender_half. The only source change gates the ARM
NEON FP16 intrinsic path on __ARM_FEATURE_FP16_VECTOR_ARITHMETIC in addition to
__ARM_NEON. ARMv8 phones without optional FP16 can use upstream scalar conversion
without an illegal-instruction compile/runtime dependency.

The compat/BLI_math_base.hh header is a restricted std::clamp shim necessary for
this isolated module. It IS NOT full Blender blenlib. In a full port it must be
replaced with official Blender headers. JNI references the real Blender FP16
library to ensure Android linking of actual upstream object code. Host test
validates exact FP16 conversions. No BKE, BLO, full scene evaluation or rendering
is integrated.

Next engine targets: complete blenlib/guardedalloc, DNA and blenloader_core,
Main/BKE and depsgraph, Android Vulkan/GPU backend, EEVEE/Cycles,
Python and all other Blender functionality. No remote workstation requirement.
Factory assets are not bundled; some upstream binaries are stored in Git LFS.

## Genuine upstream Blender low-level .blend decoder

Vendored unchanged from the same pinned upstream commit:
`BLO_core_blend_header.hh`, `BLO_core_bhead.hh`,
`intern/blo_core_blend_header.cc`, `intern/blo_core_bhead.cc`,
and the real upstream BLI FileReader/endian/compiler/utility header dependencies.

Android/host adapter `third_party/blender_blo_core/native/blender_reader_adapter.cc`
implements Blender's FileReader callback ABI using bounded local file streams.
The BLI assertion callbacks are implemented in a small platform port; assertions
are enabled, but native backtraces are not yet available. The JNI import
diagnostics call the real Blender header parser and first-block reader.

Host native C++ tests exercise actual upstream header/BHead decoders on
legacy 32-bit, legacy 64-bit and modern 64-bit synthetic files.

**Not implemented:** full blenlib, GZip/Zstd streaming through Blender's
FileReader, DNA/BKE scene reconstruction, versioning, depsgraph, viewport,
EEVEE, Cycles, or any Blender animation or editing operation.

## SDNA catalog preflight (diagnostic layer)
The Android JNI shell now calls a bounded read-only parser for the genuine SDNA NAME/TYPE/TLEN/STRC table from a DNA1 block. It uses upstream Blender's BLO BHead reader and does not decode original scene data or replace DNA_sdna_from_data. This is not a scene loader or depsgraph. Details: docs/DNA_CATALOG.md.

## Authentic Zstd FileReader dependency

Blender's genuine GPL-2.0-or-later filereader_zstd.cc is vendored from pinned
Blender source. It links against upstream Zstd 1.5.7 pinned to Git commit
f8745da6ff1ad1e7bab384bd1f9d742439278e99 (dual BSD/GPL2).
This dependency is built as a static arm64 Android library; nothing is fetched
by the installed mobile application. An optional local RENDER_ZSTD_SOURCE_DIR
provides an exact-revision offline development build.

The ported reader has explicit array delete[] substitutions to match the
current narrow new[] allocator shim; the entire guardedalloc, BLI, and real
DNA scene loader still require integration. Zstd compression support must
pass Android CI and Blender-produced fixture tests before being claimed.
