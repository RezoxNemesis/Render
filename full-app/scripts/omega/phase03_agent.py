"""RENDER OMEGA Phase 3: bounded declarative plans and native stage receipt audit.

No remote eval, arbitrary bpy operator, filesystem access or implicit execution.
Android owns the durable SQLite journal. Blender scene ID properties hold a
second, native-scene proof that an already-run operation must not be replayed.
The dispatcher must call confirm_native_stage only after auditing a real effect.
"""
import hashlib
import json
import re

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.agent.plan_validate", "omega.agent.journal_status")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPTS = "render_omega_agent_verified_stages_v1"
_ACTIONS = {
    "PLAN": {"omega.agent.plan_validate"},
    "CREATE": {"blender.object.add_cube", "omega.character.create", "omega.world.build_scene"},
    "IMPORT": {"omega.world.build_scene"},
    "MODEL": {"omega.geometry.bridge_loops", "omega.artist.execute_tool"},
    "VALIDATE": {"blender.scene.summary", "omega.quality.inspect", "omega.geometry.inspect"},
    "RIG": {"omega.rig.bind"},
    "MOTION": {"omega.motion.create_actions"},
    "WORLD": {"omega.world.build_scene"},
    "VFX": {"omega.vfx.create_grade"},
    "SNAPSHOT": {"blender.project.save_copy"},
    "RENDER": {"blender.scene.render_still", "blender.scene.render_video"},
    "EXPORT": {"blender.project.save_copy"},
}
_BAD_KEYS = {"python", "eval", "exec", "script", "shell", "command", "path", "filepath", "file_path", "uri", "url"}


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("INVALID_ARGUMENTS") from error


def _fields(value, permitted):
    if not isinstance(value, dict) or not set(value).issubset(permitted):
        raise ValueError("INVALID_ARGUMENTS")


def _hex(value, pattern, code):
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(code)
    return value


def _safe_json(value, depth=0):
    if depth > 5:
        raise ValueError("INVALID_ARGUMENTS")
    if isinstance(value, dict):
        if len(value) > 24:
            raise ValueError("INVALID_ARGUMENTS")
        for key, v in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", key) or key in _BAD_KEYS:
                raise ValueError("UNSAFE_STAGE_ARGUMENT")
            _safe_json(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 128:
            raise ValueError("INVALID_ARGUMENTS")
        for v in value:
            _safe_json(v, depth + 1)
    elif isinstance(value, str):
        if len(value) > 512 or "\x00" in value:
            raise ValueError("INVALID_ARGUMENTS")
    elif not (value is None or isinstance(value, (bool, int, float))):
        raise ValueError("INVALID_ARGUMENTS")
    if isinstance(value, float) and not (-1.0e12 <= value <= 1.0e12):
        raise ValueError("INVALID_ARGUMENTS")


def validate(operation: str, payload: dict) -> dict:
    if operation not in OPERATION_NAMES:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    _fields(payload, {"plan_id", "project_id", "source_revision", "stages"} if operation.endswith("plan_validate")
            else {"plan_id", "project_id", "source_revision"})
    if len(_canonical(payload).encode("utf-8")) > 131072:
        raise ValueError("INVALID_ARGUMENTS")
    project = _hex(payload.get("project_id"), _HEX64, "INVALID_PROJECT_ID")
    revision = _hex(payload.get("source_revision"), _HEX64, "CHECKPOINT_CONFLICT")
    plan_id = _hex(payload.get("plan_id"), _HEX32, "INVALID_PLAN_ID")
    if operation.endswith("journal_status"):
        return {"plan_id": plan_id, "project_id": project, "source_revision": revision}
    stages = payload.get("stages")
    if not isinstance(stages, list) or not 3 <= len(stages) <= 24:
        raise ValueError("INVALID_STAGE_COUNT")
    seen = set()
    output = []
    for index, stage in enumerate(stages):
        _fields(stage, {"id", "kind", "operation", "args", "depends_on", "max_retries", "expected_scene_revision"})
        sid = stage.get("id")
        if not isinstance(sid, str) or not _ID.fullmatch(sid) or sid in seen:
            raise ValueError("INVALID_STAGE_ID")
        kind, action = stage.get("kind"), stage.get("operation")
        if not isinstance(kind, str) or action not in _ACTIONS.get(kind, set()):
            raise ValueError("UNSUPPORTED_STAGE_OPERATION")
        args = stage.get("args")
        _safe_json(args)
        if not isinstance(args, dict):
            raise ValueError("INVALID_ARGUMENTS")
        # Existing native commands have stable exact schemas. All other action
        # schemas require an independent Phase 10 dispatcher check before use.
        if action == "blender.object.add_cube":
            if not set(args).issubset({"name", "size", "location"}):
                raise ValueError("INVALID_ARGUMENTS")
            if "name" in args and (not isinstance(args["name"], str) or
                                   not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", args["name"])):
                raise ValueError("INVALID_OBJECT_NAME")
            if "size" in args and (type(args["size"]) not in (int, float) or not 0.001 <= args["size"] <= 10000):
                raise ValueError("INVALID_CUBE_SIZE")
            if "location" in args and (not isinstance(args["location"], list) or len(args["location"]) != 3 or
                any(type(v) not in (int, float) or not -100000 <= v <= 100000 for v in args["location"])):
                raise ValueError("INVALID_CUBE_LOCATION")
        elif action in {"blender.scene.summary", "blender.project.save_copy"} and args:
            raise ValueError("INVALID_ARGUMENTS")
        deps = stage.get("depends_on")
        if not isinstance(deps, list) or not deps or any(not isinstance(d, str) or d not in seen for d in deps) or len(set(deps)) != len(deps):
            if index != 0 or deps != []:
                raise ValueError("INVALID_STAGE_DEPENDENCIES")
        if index > 0 and output[-1]["id"] not in deps:
            raise ValueError("INVALID_STAGE_DEPENDENCIES")
        retries = stage.get("max_retries", 0)
        if type(retries) is not int or not 0 <= retries <= 2:
            raise ValueError("INVALID_STAGE_RETRIES")
        expected = _hex(stage.get("expected_scene_revision"), _HEX64, "CHECKPOINT_CONFLICT")
        if expected != revision:
            # At planning time, every stage uses the same approved source revision;
            # the executor must request and verify newer revisions after mutations.
            raise ValueError("CHECKPOINT_CONFLICT")
        step = {"id": sid, "kind": kind, "operation": action, "args": args,
                "depends_on": deps, "max_retries": retries, "expected_scene_revision": expected}
        step["idempotency_key"] = hashlib.sha256(_canonical([project, plan_id, revision, step]).encode()).hexdigest()
        output.append(step)
        seen.add(sid)
    if output[0]["kind"] != "PLAN" or output[-1]["kind"] not in {"VALIDATE", "SNAPSHOT", "EXPORT"}:
        raise ValueError("INVALID_STAGE_ORDER")
    digest = hashlib.sha256(_canonical(output).encode()).hexdigest()
    return {"plan_id": plan_id, "project_id": project, "source_revision": revision,
            "plan_digest": digest, "stages": output}


def _scene(context):
    try:
        import bpy
    except ImportError as error:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE") from error
    scene = context.get("scene") if isinstance(context, dict) else None
    if scene is None or not isinstance(scene, bpy.types.Scene):
        raise ValueError("MISSING_NATIVE_SCENE")
    return scene


def _read_receipts(scene):
    raw = scene.get(_RECEIPTS, "{}")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and len(data) <= 128:
            return data
    except (ValueError, TypeError):
        pass
    raise ValueError("NATIVE_RECEIPT_CORRUPT")


def confirm_native_stage(scene, *, idempotency_key, project_id, source_revision, object_name, native_receipt):
    """Trusted *local* integrator hook, never a remotely exposed operation.

    The native command must have already finished. Requires a matching receipt,
    the actual Blender object and explicit revision. Call only on Blender main thread.
    """
    import bpy
    if not isinstance(scene, bpy.types.Scene):
        raise ValueError("MISSING_NATIVE_SCENE")
    for value in (idempotency_key, project_id, source_revision):
        _hex(value, _HEX64, "INVALID_ARGUMENTS")
    if not isinstance(object_name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", object_name):
        raise ValueError("INVALID_OBJECT_NAME")
    if scene.objects.get(object_name) is None:
        raise ValueError("MISSING_REFERENCE")
    if not isinstance(native_receipt, dict) or native_receipt.get("native_execution_verified") is not True or \
       object_name not in native_receipt.get("created", []):
        raise ValueError("NATIVE_RENDER_UNCONFIRMED")
    receipts = _read_receipts(scene)
    record = {"project_id": project_id, "source_revision": source_revision, "object": object_name}
    if idempotency_key in receipts and receipts[idempotency_key] != record:
        raise ValueError("CHECKPOINT_CONFLICT")
    receipts[idempotency_key] = record
    if len(receipts) > 128:
        raise ValueError("NATIVE_RECEIPT_LIMIT")
    scene[_RECEIPTS] = _canonical(receipts)
    return record


def audit(operation: str, payload: dict, context: dict) -> dict:
    data = validate(operation, payload)
    scene = _scene(context)
    receipts = _read_receipts(scene)
    # Scene revision verification is the dispatcher responsibility. No claim
    # about .blend file hash is possible without a native snapshot checksum.
    evidence = []
    # journal_status has no stages in its payload: enumerate native *scene*
    # receipts scoped to this project and approved revision. No Android stage
    # state is fabricated by treating the Blender ID property as a SQLite row.
    for key, proof in receipts.items():
        if not isinstance(proof, dict) or proof.get("project_id") != data["project_id"] or proof.get("source_revision") != data["source_revision"]:
            continue
        evidence.append({"idempotency_key": key,
                         "object": proof.get("object"),
                         "native_object_present": scene.objects.get(proof.get("object", "")) is not None})
    evidence.sort(key=lambda item: item["idempotency_key"])
    return {"operation": operation, "state": "observed", "scene": scene.name,
            "plan_id": data["plan_id"], "confirmed_stages": evidence,
            "journal_authority": "Android AgentJournal SQLite; not accessible from bpy audit",
            "visual_quality_verified": False, "quality_reduced": False}


def execute(operation: str, payload: dict, context: dict) -> dict:
    data = validate(operation, payload)
    scene = _scene(context)
    if context.get("cancellation_requested") is True:
        raise RuntimeError("CANCELLED")
    if operation == "omega.agent.journal_status":
        result = audit(operation, payload, context)
        result["state"] = "succeeded"
        result["native_execution_verified"] = True  # verified only a native read
        result["created"] = []
    else:
        result = {"operation": operation, "state": "succeeded", "scene": scene.name,
                  "plan_id": data["plan_id"], "plan_digest": data["plan_digest"],
                  "stage_keys": [s["idempotency_key"] for s in data["stages"]],
                  "created": [], "native_execution_verified": True,
                  "visual_quality_verified": False, "quality_reduced": False,
                  "warnings": ["Planning only: zero scene edits; P10 must dispatch native stage actions."]}
    result["source_revision"] = data["source_revision"]
    result["artifact"] = {"kind": "none", "sha256": None}
    return result
