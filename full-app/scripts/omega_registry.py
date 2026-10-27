# SPDX-License-Identifier: GPL-2.0-or-later
"""RENDER OMEGA's frozen, fail-closed Blender-main-thread operation registry.

No phase is enabled merely because its file can be imported. Independently
reviewed phase suites must be explicitly promoted to VERIFIED_PHASES in an
integration review. Missing/broken plugins never prevent core Blender startup.
This registry deliberately does not import bpy or any phase at import time.
"""

import hashlib
import importlib
import json
import re

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.integration.capabilities", "omega.integration.audit")

# Frozen blueprint §3.1. No executable module name is accepted from a request.
PHASES = (
    (1, "phase01_engine", ("omega.engine.diagnose", "omega.engine.viewport_profile")),
    (2, "phase02_render", ("omega.render.preflight", "omega.render.job_status")),
    (3, "phase03_agent", ("omega.agent.plan_validate", "omega.agent.journal_status")),
    (4, "phase04_geometry", ("omega.geometry.bridge_loops", "omega.geometry.inspect")),
    (5, "phase05_character", ("omega.character.create", "omega.character.audit")),
    (6, "phase06_rig", ("omega.rig.bind", "omega.rig.audit")),
    (7, "phase07_motion", ("omega.motion.create_actions", "omega.motion.audit")),
    (8, "phase08_world", ("omega.world.build_scene", "omega.world.audit")),
    (9, "phase09_vfx", ("omega.vfx.create_grade", "omega.vfx.cache_inspect")),
    (11, "phase11_artist", ("omega.artist.inspect_ui", "omega.artist.execute_tool")),
    (12, "phase12_quality", ("omega.quality.inspect", "omega.quality.revise_plan")),
    (13, "phase13_simulation", ("omega.simulation.bake", "omega.simulation.inspect_cache")),
)

# Initial Wave A: no external phase module has passed combined G2/G3 review.
# Populate ONLY after the corresponding module's real-bpy/contract tests and
# changed-file review pass. Installation by itself is never verification.
VERIFIED_PHASES = frozenset()
_ALLOWED = {op: (number, "omega." + module)
            for number, module, operations in PHASES for op in operations}
_CAP_BYTES = json.dumps(PHASES, separators=(",", ":")).encode("ascii")
CAPABILITY_REVISION = hashlib.sha256(_CAP_BYTES).hexdigest()
_SHA = re.compile(r"^[a-f0-9]{64}$")
_JOB = re.compile(r"^[a-f0-9]{32}$")


def _payload(payload):
    if type(payload) is not dict:
        raise ValueError("INVALID_ARGUMENTS")
    try:
        raw = json.dumps(payload, allow_nan=False, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise ValueError("INVALID_ARGUMENTS") from None
    if len(raw) > 131072:
        raise ValueError("COMMAND_TOO_LARGE")
    return payload


def _load(number, module_name, reserved):
    """Return module + status; dependency/import errors are not NOT_INSTALLED."""
    qualified = "omega." + module_name
    try:
        module = importlib.import_module(qualified)
    except ModuleNotFoundError as error:
        return None, "NOT_INSTALLED" if error.name in (qualified, "omega") else "IMPORT_ERROR"
    except Exception:
        return None, "IMPORT_ERROR"
    names = getattr(module, "OPERATION_NAMES", None)
    if (getattr(module, "CONTRACT_VERSION", None) != CONTRACT_VERSION
            or type(names) not in (tuple, list)
            or not names
            or any(type(op) is not str or op not in reserved for op in names)
            or len(set(names)) != len(names)
            or not all(callable(getattr(module, method, None))
                       for method in ("validate", "execute", "audit"))):
        return None, "INVALID_CONTRACT"
    if number not in VERIFIED_PHASES:
        return module, "INSTALLED_UNVERIFIED"
    return module, "AVAILABLE"


def capabilities():
    """Return honest status, including absent modules, without raising."""
    phases = []
    enabled = list(OPERATION_NAMES)
    for number, module_name, reserved in PHASES:
        module, status = _load(number, module_name, reserved)
        operations = list(module.OPERATION_NAMES) if module else []
        if status == "AVAILABLE":
            enabled.extend(operations)
        phases.append({"phase": number, "module": "omega." + module_name,
                       "status": status, "implemented": operations,
                       "enabled": operations if status == "AVAILABLE" else []})
    return {"contract_version": CONTRACT_VERSION,
            "capability_revision": CAPABILITY_REVISION,
            "enabled_operations": sorted(enabled), "phases": phases,
            "quality_reduced": False}


def _real_scene(scene):
    try:
        import bpy
        return scene is not None and isinstance(scene, bpy.types.Scene)
    except (ImportError, AttributeError, TypeError):
        return False


def _checked_context(context):
    if type(context) is not dict or not _JOB.fullmatch(context.get("job_id") or ""):
        raise ValueError("INVALID_COMMAND_ID")
    if context.get("capability_revision") != CAPABILITY_REVISION:
        raise ValueError("CHECKPOINT_CONFLICT")
    if not isinstance(context.get("production_root"), str):
        raise ValueError("INVALID_NATIVE_CONTEXT")
    available = context.get("available_memory_bytes")
    if available is not None and (type(available) is not int or available < 0):
        raise ValueError("INVALID_NATIVE_CONTEXT")
    if type(context.get("dry_run")) is not bool or context.get("dry_run"):
        raise ValueError("INVALID_NATIVE_CONTEXT")
    return context


def dispatch(operation, payload, context):
    """Only called by the app-private bpy spool on Blender's main timer thread."""
    if type(operation) is not str or len(operation) > 96:
        raise ValueError("INVALID_ARGUMENTS")
    _payload(payload)
    _checked_context(context)
    scene = context.get("scene")
    native = _real_scene(scene)
    if operation == "omega.integration.capabilities":
        if payload:
            raise ValueError("INVALID_ARGUMENTS")
        result = capabilities()
        result.update({"operation": operation, "state": "succeeded",
                       "native_execution_verified": native,
                       "visual_quality_verified": False})
        return result
    if operation == "omega.integration.audit":
        if payload:
            raise ValueError("INVALID_ARGUMENTS")
        if not native:
            raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE")
        revision = scene.get("omega_source_revision")
        if type(revision) is not str or not _SHA.fullmatch(revision):
            revision = None
        return {"operation": operation, "state": "succeeded", "scene": scene.name,
                "source_revision": revision, "objects": len(scene.objects),
                "native_engine": scene.render.engine,
                "resolution_x": scene.render.resolution_x,
                "resolution_y": scene.render.resolution_y,
                "resolution_percentage": scene.render.resolution_percentage,
                "fps": scene.render.fps, "fps_base": scene.render.fps_base,
                "native_execution_verified": True, "visual_quality_verified": False,
                "quality_reduced": False, "warnings": []}
    entry = _ALLOWED.get(operation)
    if entry is None:
        raise ValueError("NATIVE_BLENDER_ACTION_UNAVAILABLE")
    number, module_name = entry
    reserved = next(ops for num, _, ops in PHASES if num == number)
    module, status = _load(number, module_name.split(".")[-1], reserved)
    if status == "NOT_INSTALLED":
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE")
    if status != "AVAILABLE":
        raise RuntimeError("CAPABILITY_NOT_VERIFIED")
    if operation not in module.OPERATION_NAMES:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE")
    if not native:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE")
    validated = module.validate(operation, payload)
    if type(validated) is not dict:
        raise ValueError("INVALID_ARGUMENTS")
    _payload(validated)
    receipt = module.execute(operation, validated, context)
    if type(receipt) is not dict:
        raise RuntimeError("NATIVE_RECEIPT_INVALID")
    try:
        json.dumps(receipt, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError("NATIVE_RECEIPT_INVALID") from None
    if receipt.get("operation") != operation or receipt.get("state") != "succeeded":
        raise RuntimeError("NATIVE_RECEIPT_INVALID")
    if receipt.get("native_execution_verified") is not True:
        raise RuntimeError("NATIVE_RECEIPT_UNVERIFIED")
    return receipt
