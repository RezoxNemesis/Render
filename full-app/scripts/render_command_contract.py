# SPDX-License-Identifier: GPL-2.0-or-later
"""Deterministic, completely local creator recipes, never general-purpose AI.

Every accepted brief is consumed by a documented grammar. Unknown words are
not silently discarded. ChatGPT can continue to compose arbitrary supported
typed operations with ``studio.plan.submit`` without this recipe grammar.
This module has no Blender, filesystem, network or process dependency.
"""
import copy
import hashlib
import json
import re

VERSION = "render.studio.command-recipes.v1"
OPS = {"studio.command.catalog": "agent", "studio.command.preview": "agent",
       "studio.command.submit": "agent"}
READ_ONLY = frozenset(("studio.command.catalog", "studio.command.preview"))
MAX_BRIEF = 240
MAX_NAME = 40
MAX_SEED = 2147483647
NAME = re.compile(r"^[A-Za-z](?:[A-Za-z0-9 _.-]{0,38}[A-Za-z0-9_.-])?$")
SHA = re.compile(r"^[a-f0-9]{64}$")
QUALITY = ("draft", "standard", "detail")

_MATERIALS = {"wood": "wood", "wooden": "wood", "metal": "metal",
              "metallic": "metal", "stone": "stone", "fabric": "fabric",
              "cloth": "fabric", "ceramic": "ceramic", "glowing": "emissive",
              "emissive": "emissive"}
_KINDS = ("crate", "barrel", "column", "arch", "stairs", "table", "rock", "tree")
_MOTION = {"float": "float", "floating": "float", "bounce": "bounce",
           "bouncing": "bounce", "orbit": "orbit", "orbiting": "orbit",
           "turntable": "turntable", "spin": "turntable", "spinning": "turntable"}
_DEFAULT_MATERIAL = {"crate": "wood", "barrel": "wood", "column": "stone",
                     "arch": "stone", "stairs": "stone", "table": "wood",
                     "rock": "stone", "tree": "wood"}
_SUBJECT = (r"(?:(?P<material>" + "|".join(_MATERIALS) + r") )?"
            r"(?P<kind>" + "|".join(_KINDS) + r")")
_MOTION_PATTERN = r"(?P<motion>" + "|".join(_MOTION) + r")"
_EXAMPLES = (
    ("asset", "Editable asset", "wooden crate asset"),
    ("product_scene", "Product camera study", "product scene with ceramic barrel"),
    ("forest", "Forest environment", "forest environment"),
    ("island", "Rocky island environment", "island environment"),
    ("mountains", "Mountain environment", "mountain environment"),
    ("dunes", "Dune environment", "dunes environment"),
    ("plains", "Plains environment", "plains environment"),
    ("animated_prop", "Animated prop", "animated metal barrel bounce"),
    ("studio_turntable", "Studio turntable", "studio turntable with wooden crate"),
    ("flexible_rig", "Flexible rig starter", "flexible rig starter"),
)
_LABELS = {ident: label for ident, label, _ in _EXAMPLES}


class BriefError(ValueError):
    """Static recovery guidance; untrusted brief contents are never echoed."""
    def __init__(self, code):
        self.code = code
        self.examples = [row[2] for row in _EXAMPLES]
        super().__init__(code + ": Try wooden crate asset, forest environment, "
                         "animated metal barrel bounce, studio turntable, "
                         "or flexible rig starter. See studio.command.catalog.")


def canonical_bytes(value):
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError, OverflowError) as exc:
        raise ValueError("STUDIO_COMMAND_JSON_INVALID") from exc
    if len(result) > 65536:
        raise ValueError("STUDIO_COMMAND_PAYLOAD_TOO_LARGE")
    return result


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def validate(op, payload):
    if type(op) is not str or op not in OPS:
        raise ValueError("STUDIO_COMMAND_OPERATION_UNAVAILABLE")
    if type(payload) is not dict:
        raise ValueError("STUDIO_COMMAND_FIELDS_INVALID")
    if op == "studio.command.catalog":
        if payload:
            raise ValueError("STUDIO_COMMAND_FIELDS_INVALID")
        return {}
    allowed = {"brief", "name", "seed", "quality"}
    required = {"brief"}
    if op == "studio.command.submit":
        allowed.add("preview_sha256")
        required.add("preview_sha256")
    if set(payload) - allowed or not required <= set(payload):
        raise ValueError("STUDIO_COMMAND_FIELDS_INVALID")
    brief = payload["brief"]
    if (type(brief) is not str or not 1 <= len(brief) <= MAX_BRIEF or
            not brief.strip() or any(ord(c) < 32 or ord(c) > 126 for c in brief)):
        raise ValueError("STUDIO_COMMAND_BRIEF_INVALID")
    name = payload.get("name")
    if "name" in payload and (type(name) is not str or not NAME.fullmatch(name)):
        raise ValueError("STUDIO_COMMAND_NAME_INVALID")
    seed = payload.get("seed", 0)
    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise ValueError("STUDIO_COMMAND_SEED_INVALID")
    quality = payload.get("quality", "standard")
    if type(quality) is not str or quality not in QUALITY:
        raise ValueError("STUDIO_COMMAND_QUALITY_INVALID")
    result = {"brief": brief, "seed": seed, "quality": quality}
    if name is not None:
        result["name"] = name
    if op == "studio.command.submit":
        sha = payload["preview_sha256"]
        if type(sha) is not str or not SHA.fullmatch(sha):
            raise ValueError("STUDIO_COMMAND_PREVIEW_HASH_INVALID")
        result["preview_sha256"] = sha
    canonical_bytes(result)
    return result


def parse_brief(brief):
    """A small whole-string grammar; no keyword-based fallback or execution."""
    text = " ".join(brief.lower().strip().split())
    text = re.sub(r"[.!]$", "", text)
    text = re.sub(r"^please ", "", text)
    text = re.sub(r"^(?:create|make|build|add) (?:an? |the )?", "", text)
    matches = []

    def match(pattern, recipe, defaults=None):
        result = re.fullmatch(pattern, text)
        if result:
            row = dict(defaults or {})
            row.update({key: value for key, value in result.groupdict().items() if value})
            row["id"] = recipe
            matches.append(row)

    match(r"product scene(?: (?:of |with )?" + _SUBJECT + r")?", "product_scene",
          {"kind": "barrel", "material": "ceramic"})
    match(r"(?:asset|model)(?: (?:of |with )?" + _SUBJECT + r")?", "asset",
          {"kind": "crate"})
    match(_SUBJECT + r"(?: asset| model)?", "asset")
    match(r"(?:animated prop|animated|animate)(?: (?:of |with )?" + _SUBJECT +
          r")?(?: (?:(?:with|using) )?" + _MOTION_PATTERN + r")?", "animated_prop",
          {"kind": "barrel", "motion": "float"})
    match(r"(?:studio turntable|turntable)(?: (?:of |with |for )?" + _SUBJECT + r")?",
          "studio_turntable", {"kind": "crate", "motion": "turntable"})
    match(r"(?:flexible rig starter|rig starter|flexible rig)"
          r"(?: (?:for |with )?(?:fabric )?column)?", "flexible_rig",
          {"kind": "column", "material": "fabric"})
    environment = re.fullmatch(r"(forest|woodland|island|mountain|mountains|dunes|plains)"
                               r"(?: environment| scene| landscape)?", text)
    if environment:
        ident = {"mountain": "mountains", "woodland": "forest"}.get(
            environment[1], environment[1])
        matches.append({"id": ident})
    if len(matches) != 1:
        tokens = set(re.findall(r"[a-z]+", text))
        environments = tokens & {"forest", "woodland", "island", "mountain",
                                 "mountains", "dunes", "plains"}
        material_values = {_MATERIALS[word] for word in tokens if word in _MATERIALS}
        ambiguous = (len(matches) > 1 or bool(tokens & {"and", "or", "versus", "vs"}) or
                     len(environments) > 1 or len(tokens & set(_KINDS)) > 1 or
                     len(material_values) > 1)
        raise BriefError("STUDIO_COMMAND_AMBIGUOUS_BRIEF" if ambiguous else
                         "STUDIO_COMMAND_UNSUPPORTED_BRIEF")
    result = matches[0]
    result["label"] = _LABELS[result["id"]]
    if "kind" in result:
        result["material"] = _MATERIALS.get(result.get("material"),
                                              _DEFAULT_MATERIAL[result["kind"]])
    if "motion" in result:
        result["motion"] = _MOTION[result["motion"]]
    return result


def compile_request(payload):
    """Produce fully normalized creator steps without inspecting or editing bpy."""
    request = validate("studio.command.preview", payload)
    recipe = parse_brief(request["brief"])
    import render_creator_contract as Creator
    level = QUALITY.index(request["quality"])
    detail = level + 1
    seed = request["seed"]
    ident = recipe["id"]
    default_suffix = recipe.get("kind", ident).title().replace("_", "")
    name = request.get("name", "Creator_" + ident.title().replace("_", "") + "_" + default_suffix)
    # One canonical request binds omitted defaults exactly like explicit defaults.
    request["name"] = name
    steps = []
    warnings = ["New geometry is placed at the scene origin; review placement before rendering."]

    def add(action, **values):
        operation = "studio.create." + action
        steps.append({"operation": operation, "payload": Creator.validate(operation, values)})

    def model(kind, suffix="_Asset", material=None, size=2, model_detail=None, color=None):
        target = name + suffix
        add("model", name=target, kind=kind, size=size,
            detail=detail if model_detail is None else model_detail, seed=seed)
        surface = {"object": target, "preset": material or _DEFAULT_MATERIAL[kind], "scale": 5}
        if color is not None:
            surface["color"] = color
        add("material", **surface)
        return target

    def camera(target, radius):
        add("camera", target=target, preset="hero", name=name + "_Camera",
            start=1, end=120, radius=radius)
        warnings.extend(("The new camera becomes the active scene camera.",
                         "Camera studies use the scene's existing lighting."))

    if ident in ("asset", "product_scene", "animated_prop", "studio_turntable"):
        target = model(recipe["kind"], material=recipe["material"])
        if ident in ("animated_prop", "studio_turntable"):
            motion = recipe["motion"]
            amount = {"turntable": 1, "float": .45, "bounce": 1, "orbit": 1.5}[motion]
            add("motion", object=target, preset=motion, start=1, end=120,
                amount=amount, loop=True)
            warnings.append("The new prop receives a looping motion over frames 1 to 120.")
        if ident != "asset":
            camera(target, 8)
    elif ident == "flexible_rig":
        target = model("column", material="fabric", size=3, model_detail=3,
                       color=[.18, .35, .58])
        add("rig", object=target, name=name + "_Rig", segments=(3, 6, 9)[level])
        camera(target, 9)
        warnings.append("This starter is a deformable column with a straight bone chain, not a human rig.")
    else:
        size = (32, 48, 64)[level]
        resolution = (16, 32, 64)[level]
        style = "plains" if ident == "forest" else ident
        height = {"forest": (1, 2, 3), "island": (4, 7, 11),
                  "mountains": (8, 12, 18), "dunes": (2, 4, 6),
                  "plains": (.4, .8, 1.2)}[ident][level]
        ground = name + "_Terrain"
        add("terrain", name=ground, size=size, resolution=resolution,
            height=height, seed=seed, style=style)
        color = {"forest": [.16, .24, .09], "island": [.43, .36, .21],
                 "mountains": [.29, .31, .33], "dunes": [.62, .42, .16],
                 "plains": [.22, .34, .12]}[ident]
        add("material", object=ground, preset="stone", color=color, scale=5)
        if ident in ("forest", "island", "mountains"):
            kind = "tree" if ident == "forest" else "rock"
            source = model(kind, suffix="_Source", size=3 if kind == "tree" else 2,
                           color=[.12, .27, .08] if kind == "tree" else None)
            count = {"forest": (24, 72, 180), "island": (12, 24, 48),
                     "mountains": (16, 36, 80)}[ident][level]
            add("scatter", name=name + "_Scatter", source=source, count=count,
                extent=size * (.7 if ident == "island" else .9), seed=seed,
                min_scale=.65, max_scale=1.35, terrain=ground)
            warnings.append("The editable scatter source remains visible at the origin.")
        camera(ground, size * 1.1)
        warnings.append("Terrain is a height field; the recipe adds no water simulation or downloaded assets.")
    if not 1 <= len(steps) <= 16:
        raise ValueError("STUDIO_COMMAND_RECIPE_STEP_BUDGET")
    complexity = estimate_complexity(steps)
    return {"contract": VERSION, "creator_contract": Creator.VERSION,
            "planner_type": "deterministic_local_recipes", "language_model": False,
            "request": request, "recipe": recipe, "name": name, "steps": steps,
            "total_steps": len(steps), "estimated_complexity": complexity,
            "warnings": warnings, "preview_only_no_job_created": True,
            "scene_modified_by_command": False,
            "typed_plan_route": "studio.plan.submit",
            "general_free_text_supported": False}


def estimate_complexity(steps):
    import render_creator_contract as Creator
    objects = vertices = instances = triangles = keyframes = bones = 0
    estimates = {}
    for step in steps:
        action = step["operation"].rsplit(".", 1)[-1]
        p = step["payload"]
        if action in ("model", "terrain", "scatter", "camera", "rig"):
            objects += 1
        if action == "model":
            # These are creator-owned upper bounds, not invented benchmark timings.
            estimate = Creator.estimate_model(p["kind"], p["detail"])
            estimates[p["name"]] = estimate
            vertices += estimate["vertices"]
            triangles += estimate["triangles"]
        elif action == "terrain":
            vertices += (p["resolution"] + 1) ** 2
            triangles += 2 * p["resolution"] ** 2
        elif action == "scatter":
            vertices += p["count"]
            instances += p["count"]
            triangles += p["count"] * estimates[p["source"]]["triangles"]
        elif action == "motion":
            keyframes += 6 if p["preset"] == "turntable" else 99
        elif action == "camera" and p["preset"] == "orbit":
            keyframes += 231
        elif action == "rig":
            bones += p["segments"]
    return {"created_objects": objects, "mesh_vertices_upper_bound": vertices,
            "evaluated_triangles_upper_bound": triangles, "scatter_instances": instances,
            "keyframes_upper_bound": keyframes, "rig_bones": bones,
            "conservative_upper_bounds": True, "render_time_estimated": False,
            "scope": "new recipe geometry and keys only; excludes the existing scene"}


def seal_preview(value):
    """The digest covers every preview field except the digest itself."""
    result = copy.deepcopy(value)
    result.pop("preview_sha256", None)
    result["preview_sha256"] = digest(result)
    return result


def plan_id(request, preview_sha256):
    return digest({"contract": VERSION, "request": request,
                   "preview_sha256": preview_sha256})[:32]


def catalog():
    rows = []
    for ident, label, example in _EXAMPLES:
        rows.append({"id": ident, "label": label, "example": example,
                     "brief": example,
                     "supports_model_selection": ident in (
                         "asset", "product_scene", "animated_prop", "studio_turntable")})
    return {"contract": VERSION, "planner_type": "deterministic_local_recipes",
            "language_model": False, "general_free_text_supported": False,
            "recipes": rows, "models": list(_KINDS),
            "materials": sorted(set(_MATERIALS.values())),
            "motions": sorted(set(_MOTION.values())), "quality": list(QUALITY),
            "defaults": {"quality": "standard", "seed": 0},
            "limits": {"brief_characters": MAX_BRIEF, "name_characters": MAX_NAME,
                       "seed_maximum": MAX_SEED, "steps_per_plan": 16,
                       "recipe_scatter_instances": 180},
            "supported_forms": [
                "[material] model [asset]", "product scene [with [material] model]",
                "forest|island|mountain|dunes|plains environment",
                "animated [material] model [float|bounce|orbit|turntable]",
                "studio turntable [with [material] model]", "flexible rig starter"],
            "optional_prefixes": ["please", "create a", "make a", "build a", "add a"],
            "workflow": ["studio.command.preview", "review steps and warnings",
                         "studio.command.submit with the exact preview_sha256",
                         "studio.plan.status"],
            "typed_plan_guidance": "For other supported workflows, ChatGPT can search studio.tool.search "
                                   "and compose explicit typed studio.plan.submit steps.",
            "network_requests": False, "scene_mutation": False}


def capabilities():
    fields = {"brief": {"type": "string", "minLength": 1, "maxLength": MAX_BRIEF},
              "name": {"type": "string", "pattern": NAME.pattern, "maxLength": MAX_NAME},
              "seed": {"type": "integer", "minimum": 0, "maximum": MAX_SEED, "default": 0},
              "quality": {"enum": list(QUALITY), "default": "standard"}}
    result = []
    for operation in OPS:
        props = {} if operation.endswith("catalog") else copy.deepcopy(fields)
        required = [] if operation.endswith("catalog") else ["brief"]
        if operation.endswith("submit"):
            props["preview_sha256"] = {"type": "string", "pattern": SHA.pattern}
            required.append("preview_sha256")
        result.append({"operation": operation, "workspace": "agent",
                       "read_only": operation in READ_ONLY,
                       "description": "Local documented creator recipes; not a language model. "
                                      "Preview before queued submission.",
                       "input_schema": {"type": "object", "additionalProperties": False,
                                        "required": required, "properties": props}})
    return result
