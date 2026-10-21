# Native .blend format preflight — NOT full Blender file loading

This milestone implements a bounded, read-only structural index of uncompressed .blend
files in C++17. Its file-format rules are based on the actual Blender upstream
blenloader_core specification:

- https://github.com/blender/blender/blob/main/source/blender/blenloader_core/BLO_core_blend_header.hh
- https://github.com/blender/blender/blob/main/source/blender/blenloader_core/BLO_core_bhead.hh
- https://github.com/blender/blender/blob/main/source/blender/blenloader_core/intern/blo_core_blend_header.cc
- https://github.com/blender/blender/blob/main/source/blender/blenloader_core/intern/blo_core_file_reader.cc

Supports:

- Legacy 12-byte header: 32- or 64-bit pointer, little or big endian, version xxx.
- Modern 17-byte header: file format 01, little endian, 64-bit pointer, version xxxx.
- Legacy BHead4 (20-byte), SmallBHead8 (24-byte) and modern LargeBHead8 (32-byte).
- Bounds checks on signed block lengths/counts, seeks, DNA1 SDNA signature and ENDB.
- gzip and zstd candidate recognition without attempting to decompress user data.
- Explicit refusal to guess unknown future file formats; leave the original files intact.
- Constant-memory block scanning, capped by index count; exceeding the cap does not
  mean the project is corrupt and must not prevent real Blender engine opening later.

Limitations:

- No SDNA schema deserialization, Main/BKE reconstruction, Blender versioning, depsgraph,
  linked libraries, scene evaluation, viewport or rendering. A structural index being
  successful does NOT mean a .blend is a fully valid Blender scene.
- gzip/zstd need the upstream Blender FileReader implementation and its dependencies.
- Native tests use intentionally synthetic block-framing fixtures, NOT Blender-created
  production .blend files. Add a real Blender-generated version matrix before accepting
  compatibility claims.
- This is a preflight/diagnostic utility supporting an eventual port of the genuine
  Blender BLO/BKE engine; it must never be marketed as a replacement scene loader.
