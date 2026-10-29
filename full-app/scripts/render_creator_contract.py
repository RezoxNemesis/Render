# SPDX-License-Identifier: GPL-2.0-or-later
"""Strict, bpy-free contract for editable native Blender creator tools.

The schemas are the public API for Android, the Blender panel and ChatGPT.
No operation accepts Python, a path, a URL, an expression or an executable.
"""
import copy
import math
import re

VERSION = "render.studio.creator.v1"
NAME = re.compile(r"^[A-Za-z](?:[A-Za-z0-9 _.-]{0,62}[A-Za-z0-9_.-])?$")
OPS = {
    "studio.create.catalog": "assets",
    "studio.create.model": "assets",
    "studio.create.terrain": "simulation",
    "studio.create.scatter": "simulation",
    "studio.create.material": "materials",
    "studio.create.motion": "animation",
    "studio.create.camera": "cinema",
    "studio.create.rig": "characters",
}
READ_ONLY = frozenset({"studio.create.catalog"})
MODEL_KINDS = ("crate", "barrel", "column", "arch", "stairs", "table", "rock", "tree")
TERRAIN_STYLES = ("island", "mountains", "dunes", "plains")
MATERIAL_PRESETS = ("wood", "metal", "stone", "fabric", "ceramic", "emissive")
MOTION_PRESETS = ("turntable", "float", "bounce", "orbit")
CAMERA_PRESETS = ("hero", "orbit", "top", "closeup")
MAX_SCATTER_TRIANGLES = 2_000_000
MAX_SOURCE_TRIANGLES = 200_000
MAX_RIG_VERTICES = 100_000


def name(value):
    if type(value) is not str or not NAME.fullmatch(value) or value.endswith(" "):
        raise ValueError("CREATOR_NAME_INVALID")
    return value


def real(value, low, high):
    if type(value) not in (int, float):
        raise ValueError("CREATOR_NUMBER_INVALID")
    # Range comparison precedes float conversion, including arbitrarily big ints.
    if not low <= value <= high or not math.isfinite(value):
        raise ValueError("CREATOR_NUMBER_INVALID")
    return float(value)


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("CREATOR_INTEGER_INVALID")
    return value


def _num(low, high, default):
    return {"type": "number", "minimum": low, "maximum": high, "default": default}


def _int(low, high, default=None):
    result = {"type": "integer", "minimum": low, "maximum": high}
    if default is not None:
        result["default"] = default
    return result


def _enum(values, default=None):
    result = {"type": "string", "enum": list(values)}
    if default is not None:
        result["default"] = default
    return result


_IDENT = {"type": "string", "pattern": NAME.pattern, "minLength": 1,
          "maxLength": 64, "description": "ASCII object name; no trailing space."}
_SEED = _int(0, 2**31 - 1, 0)
_START = _int(1, 100_000, 1)
_END = _int(2, 100_000, 120)
_SCHEMAS = {
    "studio.create.catalog": ((), {}),
    "studio.create.model": (("name", "kind"), {
        "name": _IDENT, "kind": _enum(MODEL_KINDS),
        "size": _num(.05, 100, 2), "detail": _int(1, 3, 2), "seed": _SEED}),
    "studio.create.terrain": (("name",), {
        "name": _IDENT, "size": _num(.1, 2048, 64),
        "resolution": _int(4, 128, 32), "height": _num(0, 512, 8),
        "seed": _SEED, "style": _enum(TERRAIN_STYLES, "island")}),
    "studio.create.scatter": (("name", "source", "count"), {
        "name": _IDENT, "source": _IDENT, "count": _int(1, 10_000),
        "extent": _num(.1, 2048, 20), "seed": _SEED,
        "min_scale": _num(.01, 10, .7), "max_scale": _num(.01, 10, 1.3),
        "terrain": _IDENT}),
    "studio.create.material": (("object", "preset"), {
        "object": _IDENT, "preset": _enum(MATERIAL_PRESETS),
        "scale": _num(.05, 256, 5),
        "color": {"type": "array", "minItems": 3, "maxItems": 3,
                  "items": {"type": "number", "minimum": 0, "maximum": 1}}}),
    "studio.create.motion": (("object", "preset"), {
        "object": _IDENT, "preset": _enum(MOTION_PRESETS),
        "start": _START, "end": _END, "amount": _num(.001, 100, 1),
        "loop": {"type": "boolean", "default": True}}),
    "studio.create.camera": (("target", "preset"), {
        "target": _IDENT, "preset": _enum(CAMERA_PRESETS),
        "name": dict(_IDENT, default="CreatorCamera"), "start": _START,
        "end": _END, "radius": _num(.1, 10_000, 8)}),
    "studio.create.rig": (("object",), {
        "object": _IDENT, "name": dict(_IDENT, default="CreatorRig"),
        "segments": _int(2, 32, 4)}),
}
_DESCRIPTIONS = {
    "studio.create.catalog": "List native creator presets, limits and supported workflows.",
    "studio.create.model": "Create an editable mesh prop; size is its approximate height in Blender units.",
    "studio.create.terrain": "Create a seeded heightfield mesh; resolution is cells per side, size is width.",
    "studio.create.scatter": "Instance an evaluated mesh on seeded points, optionally raycast onto terrain; extent is square width.",
    "studio.create.material": "Apply an editable procedural Principled material to this mesh; preserve earlier material datablocks.",
    "studio.create.motion": "Create a new transform action; amount is revolutions for turntable and units for other presets. Existing animation is rejected.",
    "studio.create.camera": "Create and activate a camera aimed at target bounds; orbit samples moving target bounds at editable keys.",
    "studio.create.rig": "Create a weighted connected deform chain along the mesh's longest local axis. Suitable for flexible props, not humanoid auto-rigging.",
}


def validate(operation, payload):
    """Return normalized JSON data; never mutate the caller's payload."""
    if type(operation) is not str or operation not in OPS:
        raise ValueError("CREATOR_OPERATION_UNAVAILABLE")
    required, properties = _SCHEMAS[operation]
    if (type(payload) is not dict or set(payload) - set(properties)
            or not set(required) <= set(payload)):
        raise ValueError("CREATOR_FIELDS_INVALID")
    result = {}
    for key, spec in properties.items():
        if key in payload:
            value = payload[key]
        elif "default" in spec:
            value = spec["default"]
        else:
            continue
        kind = spec["type"]
        if kind == "string":
            if "enum" in spec:
                if type(value) is not str or value not in spec["enum"]:
                    raise ValueError("CREATOR_PRESET_INVALID")
                result[key] = value
            else:
                result[key] = name(value)
        elif kind == "number":
            result[key] = real(value, spec["minimum"], spec["maximum"])
        elif kind == "integer":
            result[key] = integer(value, spec["minimum"], spec["maximum"])
        elif kind == "boolean":
            if type(value) is not bool:
                raise ValueError("CREATOR_BOOLEAN_INVALID")
            result[key] = value
        elif kind == "array":
            if type(value) is not list or len(value) != 3:
                raise ValueError("CREATOR_COLOR_INVALID")
            result[key] = [real(x, 0, 1) for x in value]
    if operation == "studio.create.scatter":
        if result["min_scale"] > result["max_scale"]:
            raise ValueError("CREATOR_SCALE_RANGE_INVALID")
        if result["name"] == result["source"] or result["name"] == result.get("terrain"):
            raise ValueError("CREATOR_SELF_REFERENCE")
    if operation in ("studio.create.motion", "studio.create.camera"):
        if not 1 <= result["end"] - result["start"] <= 10_000:
            raise ValueError("CREATOR_FRAME_RANGE_INVALID")
    if operation == "studio.create.camera" and result["name"] == result["target"]:
        raise ValueError("CREATOR_SELF_REFERENCE")
    if operation == "studio.create.rig" and result["name"] == result["object"]:
        raise ValueError("CREATOR_SELF_REFERENCE")
    return result


def capabilities():
    result = []
    for operation, workspace in OPS.items():
        required, properties = _SCHEMAS[operation]
        result.append({
            "operation": operation, "workspace": workspace,
            "read_only": operation in READ_ONLY,
            "checkpoint_before_change": operation not in READ_ONLY,
            "implemented_as": "native_blender_datablocks",
            "description": _DESCRIPTIONS[operation],
            "input_schema": {"type": "object", "additionalProperties": False,
                             "required": list(required),
                             "properties": copy.deepcopy(properties)},
        })
    return result


def catalog():
    return {
        "contract": VERSION, "engine": "Blender bpy",
        "models": list(MODEL_KINDS), "terrain_styles": list(TERRAIN_STYLES),
        "material_presets": list(MATERIAL_PRESETS),
        "motion_presets": list(MOTION_PRESETS), "camera_presets": list(CAMERA_PRESETS),
        "operations": capabilities(),
        "limits": {"terrain_cells_per_side": 128, "terrain_vertices": 16_641,
                   "scatter_instances": 10_000,
                   "scatter_evaluated_triangles": MAX_SCATTER_TRIANGLES,
                   "scatter_source_triangles": MAX_SOURCE_TRIANGLES,
                   "rig_vertices": MAX_RIG_VERTICES, "rig_bones": 32,
                   "animation_frame_span": 10_000},
        "scatter_storage": "one point mesh and a Geometry Nodes instance tree; no realized mesh copies",
        "rig_scope": "weighted deform chain for flexible props; not humanoid auto-rigging",
        "existing_animation_overwritten": False,
        "procedural_assets_have_no_external_downloads": True,
        "neural_3d_generation": False,
        "physical_device_performance_guaranteed": False,
    }


def estimate_model(kind, detail=2):
    """Stable conservative preflight bounds; actual mesh counts are in receipts."""
    if type(kind) is not str or kind not in MODEL_KINDS:
        raise ValueError("CREATOR_PRESET_INVALID")
    integer(detail, 1, 3)
    return {"vertices": 4096, "triangles": 8192,
            "conservative_upper_bound": True, "kind": kind, "detail": detail}
