# SPDX-License-Identifier: GPL-2.0-or-later
"""Strict native-sculpt interaction contract; no remote Python or fake touches."""
import hashlib
import json
import math
import re

VERSION = "render.studio.direct-sculpt.v1"
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,79}$")
SHA = re.compile(r"^[a-f0-9]{64}$")
MAX_POINTS = 128
MAX_HASH_VERTICES = 2000000
OPS = (
    "studio.artist.sculpt.inspect",
    "studio.artist.sculpt.enter",
    "studio.artist.sculpt.stroke",
    "studio.artist.sculpt.leave",
    "studio.artist.sculpt.brush.select",
)
BRUSH_PRESETS = {"DRAW":"Draw","SMOOTH":"Smooth","GRAB":"Grab",
                 "CLAY_STRIPS":"Clay Strips","INFLATE":"Inflate","CREASE":"Crease"}

def _real(value, lo, hi):
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError("DIRECT_SCULPT_NUMBER_INVALID")
    return float(value)

def _object(value):
    if type(value) is not str or not NAME.fullmatch(value):
        raise ValueError("DIRECT_SCULPT_OBJECT_INVALID")
    return value

def validate(op, data):
    if op not in OPS:
        raise ValueError("DIRECT_SCULPT_OPERATION_UNAVAILABLE")
    if not isinstance(data, dict):
        raise ValueError("DIRECT_SCULPT_ENVELOPE_INVALID")
    allowed = {
        OPS[0]: {"object", "viewport_index"},
        OPS[1]: {"object", "viewport_index"},
        OPS[2]: {"object", "viewport_index", "expected_mesh_sha256",
                 "expected_view_sha256", "points"},
        OPS[3]: {"object", "viewport_index"},
        OPS[4]: {"object", "viewport_index", "brush"},
    }[op]
    if set(data) - allowed or "object" not in data:
        raise ValueError("DIRECT_SCULPT_FIELDS_INVALID")
    _object(data["object"])
    index = data.get("viewport_index", 0)
    if type(index) is not int or not 0 <= index <= 7:
        raise ValueError("DIRECT_SCULPT_VIEWPORT_INVALID")
    if op == OPS[4] and data.get("brush") not in BRUSH_PRESETS:
        raise ValueError("DIRECT_SCULPT_BRUSH_NOT_ALLOWED")
    if op == OPS[2]:
        if not {"points", "expected_mesh_sha256", "expected_view_sha256"} <= set(data):
            raise ValueError("DIRECT_SCULPT_REVISION_REQUIRED")
        if not (type(data["expected_mesh_sha256"]) is str and SHA.fullmatch(data["expected_mesh_sha256"])
                and type(data["expected_view_sha256"]) is str and SHA.fullmatch(data["expected_view_sha256"])):
            raise ValueError("DIRECT_SCULPT_REVISION_INVALID")
        points = data["points"]
        if not isinstance(points, list) or not 2 <= len(points) <= MAX_POINTS:
            raise ValueError("DIRECT_SCULPT_STROKE_LENGTH_INVALID")
        for point in points:
            if not isinstance(point, dict) or set(point) - {"x", "y", "pressure"} or not {"x", "y"} <= set(point):
                raise ValueError("DIRECT_SCULPT_POINT_FIELDS_INVALID")
            _real(point["x"], 0, 1)
            _real(point["y"], 0, 1)
            _real(point.get("pressure", 1.0), 0.01, 1)
        if all(points[0][key] == p[key] for p in points[1:] for key in ("x", "y")):
            raise ValueError("DIRECT_SCULPT_ZERO_LENGTH_STROKE")
    return data

def view_digest(width, height, view_matrix):
    if type(width) is not int or type(height) is not int or width < 2 or height < 2:
        raise ValueError("DIRECT_SCULPT_WINDOW_INVALID")
    flat = [float(v) for row in view_matrix for v in row]
    if len(flat) != 16 or any(not math.isfinite(v) for v in flat):
        raise ValueError("DIRECT_SCULPT_VIEW_MATRIX_INVALID")
    raw = json.dumps([width, height, flat], separators=(",",":"), allow_nan=False)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()

def to_operator_stroke(points, width, height):
    """Top-left normalised 2D coordinates -> Blender WINDOW-region pixels."""
    if type(width) is not int or type(height) is not int or width < 2 or height < 2:
        raise ValueError("DIRECT_SCULPT_WINDOW_INVALID")
    result = []
    for i, point in enumerate(points):
        x = _real(point["x"], 0, 1) * (width - 1)
        y = (1 - _real(point["y"], 0, 1)) * (height - 1)
        result.append({
            "name": "RenderDirectNativeSculpt",
            "mouse": (x, y),
            "mouse_event": (x, y),
            "location": (0, 0, 0),
            "pressure": _real(point.get("pressure", 1), .01, 1),
            "size": 24.0,
            "time": i / 60.0,
            "is_start": i == 0,
            "pen_flip": False,
        })
    return result

def capabilities():
    obj = {"type":"string","pattern":NAME.pattern}
    viewport = {"type":"integer","minimum":0,"maximum":7}
    sha = {"type":"string","pattern":SHA.pattern}
    point = {"type":"object","additionalProperties":False,
             "required":["x","y"],
             "properties":{"x":{"type":"number","minimum":0,"maximum":1},
                           "y":{"type":"number","minimum":0,"maximum":1},
                           "pressure":{"type":"number","minimum":.01,"maximum":1}}}
    return [{"operation":op,"workspace":"sculpt","requires_native_blender":True,
             "native_touch_event_fabricated":False,
             "actual_sculpt_operator_required":op == OPS[2],
             "input_schema":{"type":"object","additionalProperties":False,
                "required":["object"] + (["expected_mesh_sha256","expected_view_sha256","points"] if op == OPS[2] else ["brush"] if op==OPS[4] else []),
                "properties":dict({"object":obj,"viewport_index":viewport},
                    **({"expected_mesh_sha256":sha,"expected_view_sha256":sha,
                        "points":{"type":"array","minItems":2,"maxItems":MAX_POINTS,
                                  "items":point}} if op == OPS[2] else {"brush":{"enum":list(BRUSH_PRESETS)}} if op==OPS[4] else {}))}}
            for op in OPS]
