# Feature parity matrix — targets, not claims

Status vocabulary: NOT_STARTED, IN_PROGRESS, VERIFIED, BLOCKED. Every row must be demonstrated on a real Android phone against an upstream Blender project and exported artifacts.

| Feature | Status | Evidence needed |
| --- | --- | --- |
| Read-only SDNA schema index and datablock-category count | IN_PROGRESS | host synthetic tests; need actual .blend fixtures and real phone runtime |
| Upstream Blender BLO header and BHead decoder | IN_PROGRESS | host tests and Android crosscompile; full scene decoder not integrated |
| Genuine upstream Blender FP16 math module | IN_PROGRESS | host tests and Android cross-compile; no real-device run yet |
| Native binary .blend structure preflight | IN_PROGRESS | real Blender-created files, device execution, malformed-file tests |
| Android Vulkan GPU capability detection | IN_PROGRESS | on-device API/driver data and graceful no-Vulkan fallback |
| .blend open/save with linked data and library overrides | NOT_STARTED | byte-preserving functional round-trip |
| Modeling, edit mesh, modifiers, retopology | NOT_STARTED | evaluated mesh reference tests |
| Sculpt, UV editor, texture painting | NOT_STARTED | topology/paint output comparison |
| Materials, shader nodes, Geometry Nodes | NOT_STARTED | matched evaluated node graphs and renders |
| Rigging, constraints, IK, NLA, animation curves | NOT_STARTED | evaluated pose/frame comparison |
| Simulations (cloth, rigid bodies, fluids, particles) | NOT_STARTED | reproducible cached result tests |
| Grease Pencil, 2D animation | NOT_STARTED | identical stroke/frame structure |
| EEVEE realtime raster renderer | NOT_STARTED | Android backend qualification |
| Cycles physically based rendering | NOT_STARTED | CPU on-device golden-image comparisons |
| Compositing, editing, audio, codecs | NOT_STARTED | matching rendered image/audio/video |
| Python API, add-ons, Geometry Nodes scripting | NOT_STARTED | bpy regression suite and compatible extensions |
| Asset browser, linked libraries, remote sync/offline | NOT_STARTED | disconnected reopen/link/pack cycle |
| Touch/stylus UI, workflow parity | NOT_STARTED | recorded workflow/device testing |
| Recovery, thermal handling, long renders | NOT_STARTED | stress testing and checkpoint replay |

**Foundation-only work:** native shell boots, JNI loads, SAF can import a .blend into the phone's app-specific storage. Import is not a successful Blender open.
