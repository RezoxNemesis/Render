# Original Blender guardedalloc port

The build now compiles all five translation units of upstream Blender's guardedalloc library at revision `fbe82a46101643c5cf8d7ab331d6a47566008fa7`:

- leak_detector.cc
- mallocn.cc
- mallocn_guarded_impl.cc
- mallocn_lockfree_impl.cc
- memory_usage.cc

Source is fetched by a sparse, shallow, exact-commit Git checkout during the developer/CI build, not by the Android runtime. The original checkout is verified and left unmodified. A staged `mallocn_intern.hh` adds Android's malloc.h branch without falsely enabling glibc malloc_stats. Existing upstream algorithms, allocation accounting, padding, destructors, lock-free/counting mode and fully guarded mode are retained.

The previous toy MEM_guardedalloc.h compatibility shim and manually changed array frees are removed. Blender's original gzip reader and a signedness-adjusted original Zstd reader now allocate and free through the real library. Zstd port changes are explicit in tools/prepare_blender_zstd.py and fail closed if the pinned source changes.

The new native test checks both allocator modes: zero initialization, memory/block accounting, data-preserving reallocation with zero extension, 64-byte alignment, C++ destructor calls, multi-threaded allocation/free and zero leaked blocks. Existing real .blend/gzip/Zstd tests must pass with the real allocator, and the full module must cross-compile into the Android ARM64 APK.

This is an engine prerequisite, NOT Main/BKE reconstruction, dependency-graph evaluation, modeling or rendering. Those systems still need their actual upstream implementations.

Licensing: original source file notices are retained; GPL-2.0-or-later applies. The complete corresponding original module is available at the pinned Blender source revision, alongside this repository's build adapters. The copied upstream GPL license is included in the APK notices.
