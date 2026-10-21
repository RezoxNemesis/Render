# Native SDNA catalog preflight

This is a bounded, read-only diagnostic on local .blend files, not Blender's
full \`DNA_sdna_from_data\` or \`BKE_main\` scene loader.

The parser uses the *actual vendored upstream Blender* blenloader_core
\`BLO_readfile_blender_header_decode\` and \`BLO_readfile_read_bhead\`
functions to locate a DNA1 block and ENDB termination. The DNA1 payload
is decoded as the genuine SDNA NAME/TYPE/TLEN/STRC layout described in
\`source/blender/makesdna/intern/dna_genfile.cc\` at pinned upstream commit
fbe82a46101643c5cf8d7ab331d6a47566008fa7.

It reports:
- Blender file header version;
- names, types, and struct entry counts;
- up to eight structure type names for debugging;
- top-level Object (OB), Scene (SC), Mesh (ME) block counts by BHead ID codes.

All indices, marker tags, field counts and file seeks are range-checked. It
rejects malformed data and leaves the original file untouched.

**Limits apply ONLY to diagnostics:** DNA1 payload 128 MiB, up to one million
block and table entries. They DO NOT reduce engine scene capability; the
full upstream data loader must handle larger Blender files independently.

**Unimplemented:** Zstd FileReader decompression, cross-endian BHead
parsing, structural renames/legacy workarounds, nested DNA field offsets,
pointer remapping, scene graph and asset linking, BKE/depsgraph, all
modeling/animation/rendering functions. Real Blender-generated .blend file
acceptance tests and on-device runtime validation are still required.

The host tests synthesize SDNA payloads and do not demonstrate scene loading.
The catalog emits \`sceneLoaded:false\` and \`engineIntegrated:false\` even
after successful schema indexing.

## gzip preflight support
Gzip input is now passed through Blender's original GPL-licensed `filereader_gzip.cc`, with a narrowly adapted guardedalloc shim and ARM/host libz. The scoped patch uses `delete[]` for the buffer allocated by the shim; this is NOT the full Blender memory allocator. The upstream gzip reader is forward-only, so the diagnostic parser streams over file blocks with a 512-MiB diagnostic decompression-work budget. This is not a feature limitation in the planned Blender engine. Zstd still requires the genuine upstream reader and an Android zstd build.

## Top-level ID pointer-token inventory
A bounded diagnostic set now tracks distinct **saved** ID block pointer tokens (as hexadecimal-like address identifiers, never dereferenced as Android pointers). Four-byte control/data blocks are excluded. The report includes top-level ID block counts and repeated nonzero tokens, helping establish an initial mapping before full Blender Main/BKE pointer reconstruction. These tokens are not usable native memory addresses, and this index is **not** Blender's original OldNewMap or linked-library logic.

## Real Blender-produced file acceptance suite

The separate `blender-real-file-compatibility` CI job installs Blender on a
**Linux test runner only**, uses genuine `bpy` to generate meshes, an
animation and additional scene, saves uncompressed `.blend` files, and
compresses one via gzip for readback checks. It then runs Render's C++ loader
against the real files, comparing schema / ID block counts and checking that
`sceneLoaded` is still `false`.

The CI Blender binary **never becomes a remote rendering dependency** of
Render for Android. A successful test only validates file diagnostics and
saved-block indexing. Neither BKE reconstruction nor native viewport/modeling
or animation playback are thereby completed.

## Saved ID-name previews
The diagnostic now reads Object, Scene, and Mesh names using the original on-disk SDNA field layout. This handles older 66-byte and newer 258-byte `ID.name` fields, with bounded sampled payloads rather than unbounded project copies. The data remains read-only; Blender `Main`, BKE Object instances, scene evaluation, and rendering are NOT yet implemented. Real Blender fixture CI checks compressed and raw files produce matching saved names.

## Native Zstandard support
Blender's upstream Zstd FileReader and exact-revision pinned Zstandard 1.5.7 library now decode ordinary Zstd-compressed Blender streams and Blender-native compressed projects in the Android C++ layer. The CI suite tests both artificial framing fixtures and actual Blender-generated files. The source is obtained during application *build*, not on the Android phone at runtime; a developer can supply a cached source checkout for offline builds. This is still a read-only catalog, not a BKE scene loader.
