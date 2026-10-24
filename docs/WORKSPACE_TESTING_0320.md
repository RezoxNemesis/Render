# Render 0.32.0 verification boundaries

This upgrade extends the existing 0.31.3 implementation; its genuine native
body checkpoint and failed render evidence are retained in
[the earlier report](WORKSPACE_TESTING_0313.md). Private references, native
projects, command receipts and screenshots remain outside the public repository.

Focused host checks run in the workspace. They exercise real local file I/O and
contract fixtures; they do not establish Blender import, rendering, device
performance or remote authentication. The signed full APK is built separately
with the pinned upstream native libraries and historical certificate.

Android storage verification uses the existing native `.blend` checkpoint bytes,
the production operation dispatcher, file foreground service and exact transfer
receipts. Workspace-folder copying and an Android DocumentsProvider grant are
separate checks. A successful file transfer is explicitly **not** a successful
native Blender import. No cloud or desktop Blender is used for either check.

Build hashes, source identity and actual Android outcomes will accompany the
delivered APK. Unavailable checks remain unverified rather than being inferred
from compilation or capabilities. No phone, endurance or final-output-quality
claim follows from the workspace checks.
