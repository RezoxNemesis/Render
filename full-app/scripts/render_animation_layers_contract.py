# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded native cutout, parallax-camera and time-varying shape contracts."""
import copy
import math

from render_creator_contract import NAME, name, real, integer

VERSION = "render.studio.animation.layers.v1"
MAX_MORPH_VERTICES = 50_000
OPS = {
    "studio.animation.catalog": "animation",
    "studio.animation.layer.create": "drawing",
    "studio.animation.parallax.create": "cinema",
    "studio.animation.morph.create": "animation",
}
READ_ONLY = frozenset({"studio.animation.catalog"})


def _number(low, high, default):
    return {"type": "number", "minimum": low, "maximum": high, "default": default}


def _integer(low, high, default):
    return {"type": "integer", "minimum": low, "maximum": high, "default": default}


def _enum(values, default):
    return {"type": "string", "enum": values, "default": default}


_NAME = {"type": "string", "pattern": NAME.pattern, "minLength": 1, "maxLength": 64}
_START = _integer(1, 100_000, 1)
_END = _integer(3, 100_000, 120)
_SCHEMAS = {
    "studio.animation.catalog": ((), {}),
    "studio.animation.layer.create": (("name",), {
        "name": _NAME,
        "shape": _enum(["rectangle", "ellipse", "polygon"], "rectangle"),
        "width": _number(.01, 100, 4), "height": _number(.01, 100, 3),
        "x": _number(-1000, 1000, 0), "y": _number(-1000, 1000, 0),
        "depth": _number(-100, 100, 0),
        "color": {"type": "array", "minItems": 3, "maxItems": 3,
                  "items": {"type": "number", "minimum": 0, "maximum": 1},
                  "default": [.3, .55, .8]},
        "points": {"type": "array", "minItems": 3, "maxItems": 128,
                   "items": {"type": "array", "minItems": 2, "maxItems": 2,
                             "items": {"type": "number", "minimum": -1, "maximum": 1}},
                   "description": "Simple polygon boundary in normalized -1..1 local coordinates; required only for polygon."},
    }),
    "studio.animation.parallax.create": (("name", "layers"), {
        "name": _NAME,
        "layers": {"type": "array", "minItems": 2, "maxItems": 32, "items": _NAME},
        "start": _START, "end": _END,
        "distance": _number(.1, 1000, 20),
        "travel_x": _number(-100, 100, 2), "travel_y": _number(-100, 100, 0),
        "lens_mm": _number(10, 200, 50),
        "interpolation": _enum(["LINEAR", "BEZIER"], "BEZIER"),
    }),
    "studio.animation.morph.create": (("object", "name"), {
        "object": _NAME, "name": _NAME,
        "preset": _enum(["breathe", "twist", "wave"], "breathe"),
        "amount": _number(.001, 1, .1),
        "start": _START, "end": _END,
        "loop": {"type": "boolean", "default": True},
    }),
}
_DESCRIPTIONS = {
    "studio.animation.catalog": "List native 2D cutout, 2.5D parallax and animated shape-key tools and limits.",
    "studio.animation.layer.create": "Create an editable flat-color cutout mesh in the XY plane. Polygon points are normalized; positive depth is toward the camera. No external image is fetched.",
    "studio.animation.parallax.create": "Create and activate a new perspective camera, key its horizontal/vertical travel, and verify real distinct layer depths. Existing layer transforms and animations stay intact.",
    "studio.animation.morph.create": "Create a private mesh copy with an animated breathe, twist or wave shape key. Preserves the original mesh datablock and refuses existing shape keys. Time-varying 3D, not a four-spatial-dimension engine.",
}


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def _on_segment(a, b, p):
    return (abs(_cross(a, b, p)) < 1e-9
            and min(a[0], b[0])-1e-9 <= p[0] <= max(a[0], b[0])+1e-9
            and min(a[1], b[1])-1e-9 <= p[1] <= max(a[1], b[1])+1e-9)


def _intersects(a, b, c, d):
    cross = (_cross(a,b,c), _cross(a,b,d), _cross(c,d,a), _cross(c,d,b))
    if cross[0]*cross[1] < 0 and cross[2]*cross[3] < 0:
        return True
    return (_on_segment(a,b,c) or _on_segment(a,b,d)
            or _on_segment(c,d,a) or _on_segment(c,d,b))


def polygon(points):
    if type(points) is not list or not 3 <= len(points) <= 128:
        raise ValueError("ANIMATION_POLYGON_INVALID")
    result = []
    for p in points:
        if type(p) is not list or len(p) != 2:
            raise ValueError("ANIMATION_POLYGON_INVALID")
        result.append([real(v, -1, 1) for v in p])
    count = len(result)
    for i, point in enumerate(result):
        for other in result[i+1:]:
            if math.dist(point, other) < 1e-6:
                raise ValueError("ANIMATION_POLYGON_REPEATED_VERTEX")
        a, b = point, result[(i+1) % count]
        for j in range(i+1, count):
            if j == i+1 or i == 0 and j == count-1:
                continue
            if _intersects(a, b, result[j], result[(j+1) % count]):
                raise ValueError("ANIMATION_POLYGON_SELF_INTERSECTION")
    area = sum(result[i][0]*result[(i+1)%count][1]
               -result[(i+1)%count][0]*result[i][1] for i in range(count)) / 2
    if abs(area) < 1e-6:
        raise ValueError("ANIMATION_POLYGON_AREA_TOO_SMALL")
    return result if area > 0 else list(reversed(result))


def validate(operation, payload):
    if type(operation) is not str or operation not in OPS:
        raise ValueError("ANIMATION_LAYERS_OPERATION_UNAVAILABLE")
    required, properties = _SCHEMAS[operation]
    if type(payload) is not dict or set(payload)-set(properties) or not set(required) <= set(payload):
        raise ValueError("ANIMATION_LAYERS_FIELDS_INVALID")
    clean = {}
    for key, spec in properties.items():
        if key in payload:
            value = payload[key]
        elif "default" in spec:
            value = copy.deepcopy(spec["default"])
        else:
            continue
        kind = spec["type"]
        if kind == "string":
            if "enum" in spec:
                if type(value) is not str or value not in spec["enum"]:
                    raise ValueError("ANIMATION_LAYERS_PRESET_INVALID")
                clean[key] = value
            else:
                clean[key] = name(value)
        elif kind == "number":
            clean[key] = real(value, spec["minimum"], spec["maximum"])
        elif kind == "integer":
            clean[key] = integer(value, spec["minimum"], spec["maximum"])
        elif kind == "boolean":
            if type(value) is not bool:
                raise ValueError("ANIMATION_LAYERS_BOOLEAN_INVALID")
            clean[key] = value
        elif key == "points":
            clean[key] = polygon(value)
        elif key == "color":
            if type(value) is not list or len(value) != 3:
                raise ValueError("ANIMATION_COLOR_INVALID")
            clean[key] = [real(x, 0, 1) for x in value]
        elif key == "layers":
            if type(value) is not list or not 2 <= len(value) <= 32:
                raise ValueError("ANIMATION_LAYER_COUNT_INVALID")
            clean[key] = [name(x) for x in value]
            if len(set(clean[key])) != len(clean[key]):
                raise ValueError("ANIMATION_LAYER_DUPLICATE")
    if "start" in clean and not 2 <= clean["end"]-clean["start"] <= 10_000:
        raise ValueError("ANIMATION_FRAME_RANGE_INVALID")
    if operation == "studio.animation.layer.create":
        if (clean["shape"] == "polygon") != ("points" in clean):
            raise ValueError("ANIMATION_POLYGON_POINTS_REQUIRED_ONLY_FOR_POLYGON")
    if operation == "studio.animation.parallax.create":
        if clean["name"] in clean["layers"]:
            raise ValueError("ANIMATION_SELF_REFERENCE")
        if abs(clean["travel_x"])+abs(clean["travel_y"]) < .001:
            raise ValueError("ANIMATION_PARALLAX_TRAVEL_REQUIRED")
    if operation == "studio.animation.morph.create" and clean["name"] == "Basis":
        raise ValueError("ANIMATION_MORPH_RESERVED_NAME")
    return clean


def capabilities():
    return [{"operation": operation, "workspace": OPS[operation],
             "read_only": operation in READ_ONLY,
             "checkpoint_before_change": operation not in READ_ONLY,
             "implemented_as": "native_blender_datablocks",
             "description": _DESCRIPTIONS[operation],
             "input_schema": {"type": "object", "additionalProperties": False,
                              "required": list(required), "properties": copy.deepcopy(properties)}}
            for operation, (required, properties) in _SCHEMAS.items()]


def catalog():
    return {"contract": VERSION, "operations": capabilities(),
            "layer_shapes": ["rectangle", "ellipse", "polygon"],
            "morph_presets": ["breathe", "twist", "wave"],
            "limits": {"polygon_vertices": 128, "parallax_layers": 32,
                       "morph_vertices": MAX_MORPH_VERTICES, "frame_span": 10_000},
            "layer_plane": "XY; positive Z is toward the camera",
            "existing_animation_overwritten": False,
            "morph_scope": "3D mesh shape-key deformation over time",
            "four_spatial_dimensions": False, "raster_paint_engine": False}
