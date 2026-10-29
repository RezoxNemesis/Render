# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded native humanoid motion and evaluated-pose quality contracts."""
import copy
import math
import re

VERSION = "render.motion.lab.v1"
OPS = {"studio.motion.rig.create": "characters", "studio.motion.clip.create": "animation",
       "studio.motion.audit": "animation"}
READ_ONLY = frozenset({"studio.motion.audit"})
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_. -]{0,47}(?<! )$")
PRESETS = ("walk", "idle", "squat")
MAX_SAMPLES = 512
MAX_BONES = 128


def name(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError("MOTION_NAME_INVALID")
    return value


def real(value, low, high):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise ValueError("MOTION_NUMBER_INVALID")
    return float(value)


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("MOTION_INTEGER_INVALID")
    return value


def fields(value, required, allowed):
    if type(value) is not dict or set(value) - set(allowed) or not set(required) <= set(value):
        raise ValueError("MOTION_FIELDS_INVALID")


def sample_frames(start, end, step, contacts=()):
    frames = set(range(start, end + 1, step)) | {end}
    for contact in contacts:
        frames.update((contact["start"], contact["end"]))
    if len(frames) > MAX_SAMPLES:
        raise ValueError("MOTION_SAMPLE_BUDGET_EXCEEDED")
    return sorted(frames)


def validate(operation, payload):
    if type(operation) is not str or operation not in OPS:
        raise ValueError("MOTION_OPERATION_UNAVAILABLE")
    if operation == "studio.motion.rig.create":
        fields(payload, ("name",), ("name", "height", "origin"))
        origin = payload.get("origin", [0, 0, 0])
        if type(origin) is not list or len(origin) != 3:
            raise ValueError("MOTION_ORIGIN_INVALID")
        return {"name": name(payload["name"]), "height": real(payload.get("height", 1.8), .5, 4),
                "origin": [real(x, -10000, 10000) for x in origin]}
    required = ("rig",)
    allowed = ("rig", "preset", "start", "end", "cycles", "stride") if operation.endswith("clip.create") else (
        "rig", "start", "end", "step", "contacts", "joints", "max_distance_per_frame")
    if operation.endswith("clip.create"):
        required += ("preset",)
    fields(payload, required, allowed)
    result = {"rig": name(payload["rig"]), "start": integer(payload.get("start", 1), 1, 100000),
              "end": integer(payload.get("end", 49), 2, 100000)}
    duration = result["end"] - result["start"]
    if not 1 <= duration <= 2400:
        raise ValueError("MOTION_FRAME_RANGE_INVALID")
    if operation.endswith("clip.create"):
        preset = payload["preset"]
        if type(preset) is not str or preset not in PRESETS:
            raise ValueError("MOTION_PRESET_INVALID")
        result.update(preset=preset, cycles=integer(payload.get("cycles", 1), 1, 4),
                      stride=real(payload.get("stride", .4), .05, .6))
        if not 24 * result["cycles"] <= duration <= 240:
            raise ValueError("MOTION_CLIP_FRAME_BUDGET_INVALID")
        return result
    result.update(step=integer(payload.get("step", 1), 1, 120),
                  max_distance_per_frame=real(payload.get("max_distance_per_frame", .2), .00001, 100))
    # Omitted maps mean use an owned clip's stored mappings; an explicit empty
    # list means do not claim that aspect has been checked.
    for field, maximum in (("contacts", 32), ("joints", 16)):
        if field not in payload:
            continue
        values = payload[field]
        if type(values) is not list or len(values) > maximum:
            raise ValueError("MOTION_MAPPING_LIMIT")
        clean = []
        for value in values:
            if field == "contacts":
                fields(value, ("bone", "start", "end"), ("bone", "start", "end", "max_drift"))
                item = {"bone": name(value["bone"]), "start": integer(value["start"], result["start"], result["end"]),
                        "end": integer(value["end"], result["start"], result["end"]),
                        "max_drift": real(value.get("max_drift", .01), .000001, 10)}
                if item["end"] <= item["start"]:
                    raise ValueError("MOTION_CONTACT_RANGE_INVALID")
            else:
                fields(value, ("parent", "child"), ("parent", "child", "min_degrees", "max_degrees"))
                item = {"parent": name(value["parent"]), "child": name(value["child"]),
                        "min_degrees": real(value.get("min_degrees", 0), 0, 180),
                        "max_degrees": real(value.get("max_degrees", 155), 0, 180)}
                if item["parent"] == item["child"] or item["min_degrees"] > item["max_degrees"]:
                    raise ValueError("MOTION_JOINT_RANGE_INVALID")
            if item in clean:
                raise ValueError("MOTION_DUPLICATE_MAPPING")
            clean.append(item)
        result[field] = clean
    sample_frames(result["start"], result["end"], result["step"], result.get("contacts", ()))
    return result


def _obj(required, properties):
    return {"type": "object", "additionalProperties": False, "required": list(required), "properties": properties}


def capabilities():
    ident = {"type": "string", "pattern": NAME.pattern, "maxLength": 48}
    frame = {"type": "integer", "minimum": 1, "maximum": 100000}
    contact = _obj(("bone", "start", "end"), {"bone": ident, "start": frame, "end": frame,
        "max_drift": {"type": "number", "minimum": .000001, "maximum": 10, "default": .01}})
    joint = _obj(("parent", "child"), {"parent": ident, "child": ident,
        "min_degrees": {"type": "number", "minimum": 0, "maximum": 180, "default": 0},
        "max_degrees": {"type": "number", "minimum": 0, "maximum": 180, "default": 155}})
    configs = {
        "studio.motion.rig.create": (("name",), {"name": ident,
            "height": {"type": "number", "minimum": .5, "maximum": 4, "default": 1.8},
            "origin": {"type": "array", "minItems": 3, "maxItems": 3,
                       "items": {"type": "number", "minimum": -10000, "maximum": 10000}, "default": [0, 0, 0]}}),
        "studio.motion.clip.create": (("rig", "preset"), {"rig": ident,
            "preset": {"type": "string", "enum": list(PRESETS)}, "start": dict(frame, default=1),
            "end": dict(frame, default=49), "cycles": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
            "stride": {"type": "number", "minimum": .05, "maximum": .6, "default": .4,
                       "description": "Walk cycle distance as a fraction of mannequin height."}}),
        "studio.motion.audit": (("rig",), {"rig": ident, "start": dict(frame, default=1), "end": dict(frame, default=49),
            "step": {"type": "integer", "minimum": 1, "maximum": 120, "default": 1},
            "contacts": {"type": "array", "maxItems": 32, "items": contact},
            "joints": {"type": "array", "maxItems": 16, "items": joint},
            "max_distance_per_frame": {"type": "number", "minimum": .00001, "maximum": 100, "default": .2}})}
    descriptions = {
        "studio.motion.rig.create": "Create an articulated humanoid mannequin with native bone weights and two leg IK controls; a motion-test starter, not a finished character.",
        "studio.motion.clip.create": "Add editable walk, idle or squat keys to an unanimated Motion Lab mannequin. Walk stance targets stay planted in world space.",
        "studio.motion.audit": "Evaluate world-space pose samples: declared foot-contact drift, declared joint flexion and per-frame jumps. Report measured failures; never certify perfect motion."}
    return [{"operation": op, "workspace": OPS[op], "read_only": op in READ_ONLY,
             "checkpoint_before_change": op not in READ_ONLY, "description": descriptions[op],
             "input_schema": copy.deepcopy(_obj(*configs[op])), "implemented_as": "native_blender_datablocks"}
            for op in OPS]
