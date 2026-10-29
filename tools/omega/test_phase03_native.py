"""Native Blender verification: blender -b --python tools/omega/test_phase03_native.py.

Uses actual bpy mesh creation/save/reload, no mock. An unavailable bpy is a test
blocker, not an excuse to claim native integration succeeded.
"""
import importlib.util
from pathlib import Path
import tempfile
import bpy

FILE = Path(__file__).resolve().parents[2] / "full-app" / "scripts" / "omega" / "phase03_agent.py"
spec = importlib.util.spec_from_file_location("omega_phase03_agent", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

PROJECT = "a" * 64
REVISION = "b" * 64
KEY = "d" * 64
scene = bpy.context.scene
before = len(scene.objects)
bpy.ops.mesh.primitive_cube_add(size=1.0)
obj = bpy.context.object
obj.name = "NativeCube"
assert len(scene.objects) == before + 1
record = module.confirm_native_stage(scene, idempotency_key=KEY, project_id=PROJECT,
                                      source_revision=REVISION, object_name=obj.name,
                                      native_receipt={"native_execution_verified": True, "created": [obj.name]})
assert record["object"] == "NativeCube"
with tempfile.TemporaryDirectory() as root:
    blend_file = str(Path(root) / "phase03-native-fixture.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_file)
    bpy.ops.wm.open_mainfile(filepath=blend_file)
    reopened = bpy.context.scene
    assert reopened.objects.get("NativeCube") is not None
    receipts = module._read_receipts(reopened)
    assert receipts[KEY]["object"] == "NativeCube"
    count = len(reopened.objects)
    # Reclaimed key is evidence of an already-realized effect, NOT permission
    # to issue a second object creation command.
    module.confirm_native_stage(reopened, idempotency_key=KEY, project_id=PROJECT,
                                source_revision=REVISION, object_name="NativeCube",
                                native_receipt={"native_execution_verified": True, "created": ["NativeCube"]})
    assert len(reopened.objects) == count
    try:
        module.confirm_native_stage(reopened, idempotency_key=KEY, project_id=PROJECT,
                                    source_revision="f"*64, object_name="NativeCube",
                                    native_receipt={"native_execution_verified": True, "created": ["NativeCube"]})
    except ValueError as err:
        assert str(err) == "CHECKPOINT_CONFLICT"
    else:
        raise AssertionError("cross-project/revision replay was allowed")
print("PHASE03_NATIVE_BPY_OK saved/reopened mesh and no duplicate native object")
