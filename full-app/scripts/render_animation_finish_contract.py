# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded, bpy-free interface for render preparation and whole-action retiming."""
import copy
import math
import re

VERSION = "render.animation.finish.v1"
OPS = {"studio.finish.inspect": "cinema", "studio.finish.preset": "cinema",
       "studio.keyframes.inspect": "animation", "studio.keyframes.retime": "animation"}
READ_ONLY = frozenset({"studio.finish.inspect", "studio.keyframes.inspect"})
MAX_CURVES = 512
MAX_KEYS = 20_000
PRESETS = {"draft": {"width": 854, "height": 480, "samples": 16},
           "standard": {"width": 1280, "height": 720, "samples": 64},
           "final": {"width": 1920, "height": 1080, "samples": 128}}
ENGINES = ("keep", "CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "BLENDER_WORKBENCH")
_NAME = {"type": "string", "minLength": 1, "maxLength": 128}
_SCHEMAS = {
    "studio.finish.inspect": ((), {}),
    "studio.finish.preset": (("preset",), {
        "preset": {"type": "string", "enum": list(PRESETS)},
        "engine": {"type": "string", "enum": list(ENGINES), "default": "keep"},
        "width": {"type": "integer", "minimum": 16, "maximum": 8192, "multipleOf": 2},
        "height": {"type": "integer", "minimum": 16, "maximum": 8192, "multipleOf": 2},
        "fps": {"type": "integer", "minimum": 1, "maximum": 120},
        "start": {"type": "integer", "minimum": 1, "maximum": 100000},
        "end": {"type": "integer", "minimum": 1, "maximum": 100000}}),
    "studio.keyframes.inspect": (("action",), {"action": _NAME}),
    "studio.keyframes.retime": (("action", "expected_sha256", "scale"), {
        "action": _NAME,
        "expected_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "scale": {"type": "number", "minimum": .05, "maximum": 20},
        "offset": {"type": "number", "minimum": -100000, "maximum": 100000, "default": 0},
        "pivot": {"type": "number", "minimum": 0, "maximum": 100000, "default": 0},
        "allow_shared_action": {"type": "boolean", "default": False}}),
}
_DESCRIPTIONS = {
    "studio.finish.inspect": "Read camera, timeline, external-image availability and render cost before the existing render queue. No render starts.",
    "studio.finish.preset": "Explicitly apply draft/standard/final resolution and sample settings. Optional timing fields are deliberate changes; existing render jobs remain immutable.",
    "studio.keyframes.inspect": "Read whole-action key counts, frame range, retiming restrictions and a revision token across legacy and slotted actions.",
    "studio.keyframes.retime": "Retiming formula: pivot + (old_frame - pivot) * scale + offset. Changes all action slots and Bezier handle times; refuses stale/shared-unapproved/NLA-used actions.",
}


def validate(operation, payload):
    if type(operation) is not str or operation not in OPS:
        raise ValueError("FINISH_OPERATION_UNAVAILABLE")
    required, properties = _SCHEMAS[operation]
    if type(payload) is not dict or set(payload) - set(properties) or not set(required) <= set(payload):
        raise ValueError("FINISH_FIELDS_INVALID")
    result = {}
    for key, spec in properties.items():
        if key not in payload and "default" not in spec:
            continue
        value = payload.get(key, spec.get("default"))
        if spec["type"] == "integer":
            if type(value) is not int or not spec["minimum"] <= value <= spec["maximum"]:
                raise ValueError("FINISH_INTEGER_INVALID")
            if "multipleOf" in spec and value % spec["multipleOf"]:
                raise ValueError("FINISH_EVEN_DIMENSIONS_REQUIRED")
        elif spec["type"] == "number":
            if (type(value) not in (int, float) or not spec["minimum"] <= value <= spec["maximum"]
                    or not math.isfinite(value)):
                raise ValueError("FINISH_NUMBER_INVALID")
            value = float(value)
        elif spec["type"] == "boolean":
            if type(value) is not bool:
                raise ValueError("FINISH_BOOLEAN_INVALID")
        elif spec["type"] == "string":
            if type(value) is not str:
                raise ValueError("FINISH_TEXT_INVALID")
            if "enum" in spec and value not in spec["enum"]:
                raise ValueError("FINISH_PRESET_INVALID")
            if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
                raise ValueError("FINISH_REVISION_INVALID")
            if key == "action" and (not 1 <= len(value) <= 128 or any(ord(c) < 32 for c in value)):
                raise ValueError("FINISH_ACTION_NAME_INVALID")
        result[key] = value
    if "start" in result and "end" in result and result["end"] < result["start"]:
        raise ValueError("FINISH_FRAME_RANGE_INVALID")
    return result


def capabilities():
    return [{"operation": operation, "workspace": OPS[operation],
             "description": _DESCRIPTIONS[operation], "read_only": operation in READ_ONLY,
             "checkpoint_before_change": operation not in READ_ONLY,
             "native_bpy_required": True,
             "input_schema": {"type": "object", "additionalProperties": False,
                              "required": list(required), "properties": copy.deepcopy(properties)}}
            for operation, (required, properties) in _SCHEMAS.items()]
