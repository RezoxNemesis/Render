# SPDX-License-Identifier: GPL-2.0-or-later
"""RENDER OMEGA P05: bounded, editable synthetic anatomical character.

This is a stylized *surface authoring stage*, not a likeness reconstruction or
finished skinned rig. All bpy mutations occur only in execute on Blender's main
thread; no startup registration, arbitrary operators, or filesystem access.
"""
import hashlib
import json
import math
import re

CONTRACT_VERSION = "RENDER-OMEGA-1"
OPERATION_NAMES = ("omega.character.create", "omega.character.audit")
_STYLE = "stylized_anatomical_v1"
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SEGMENTS = 64
_SOURCE_HEIGHT = 2.301  # Synthetic crown above the z=0 shoe sole.


def validate(operation, payload):
    """Pure strict validation; never import bpy or touch a project."""
    if operation not in OPERATION_NAMES:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    if not isinstance(payload, dict):
        raise ValueError("INVALID_ARGUMENTS")
    allowed = {"name"} if operation.endswith(".audit") else {
        "name", "style", "height_m", "reference_sha256"}
    if set(payload) - allowed:
        raise ValueError("INVALID_ARGUMENTS")
    name = payload.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("INVALID_ARGUMENTS")
    if operation.endswith(".audit"):
        return {"name": name}
    style = payload.get("style", _STYLE)
    if style != _STYLE:
        raise ValueError("UNSUPPORTED_NATIVE_FEATURE")
    height = payload.get("height_m", 1.75)
    if isinstance(height, bool) or not isinstance(height, (int, float)) or not math.isfinite(height) or not 1.5 <= height <= 2.1:
        raise ValueError("INVALID_ARGUMENTS")
    ref = payload.get("reference_sha256")
    if ref is not None and (not isinstance(ref, str) or not _SHA.fullmatch(ref)):
        raise ValueError("INVALID_ARGUMENTS")
    return {"name": name, "style": style, "height_m": float(height),
            "reference_sha256": ref}


def _scale(height_m):
    """Meters per source-mesh unit; height_m is actual crown elevation."""
    return height_m / _SOURCE_HEIGHT


def _digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _native(context):
    try:
        import bpy
    except ImportError as exc:
        raise RuntimeError("UNSUPPORTED_NATIVE_FEATURE") from exc
    if not isinstance(context, dict) or not isinstance(context.get("scene"), bpy.types.Scene):
        raise ValueError("INVALID_ARGUMENTS")
    return bpy, context["scene"]


def _existing(scene, name):
    for coll in scene.collection.children:
        if coll.get("omega_character_name") == name and coll.get("omega_phase") == 5:
            return coll
    return None


def _material(bpy, label, rgba, roughness):
    mat = bpy.data.materials.new(label)
    mat.diffuse_color = (*rgba, 1.0)
    mat.use_nodes = True
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*rgba, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def _loft(bpy, coll, name, rings, mat, segments=_SEGMENTS, face_relief=False, uv=True):
    """Single real closed quad surface; rings are (cx,cy,z,rx,ry)."""
    vertices = []
    for cx, cy, z, rx, ry in rings:
        for j in range(segments):
            angle = 2 * math.pi * j / segments
            x = cx + rx * math.cos(angle)
            y = cy + ry * math.sin(angle)
            if face_relief and z >= 1.93 and math.sin(angle) < -0.20:
                weight = min(1.0, (-math.sin(angle)) ** 4)
                def bump(at_x, at_z, sx, sz):
                    return math.exp(-0.5 * (((x - at_x) / sx) ** 2 +
                                             ((z - at_z) / sz) ** 2))
                # Inset eye sockets; actual surface displacements for nose/lips.
                y += weight * (0.021 * (bump(-0.079, 2.135, .039, .025) +
                                        bump(.079, 2.135, .039, .025))
                               - 0.065 * bump(0, 2.091, .033, .057)
                               - 0.021 * bump(0, 2.035, .072, .012)
                               - 0.012 * bump(0, 1.993, .074, .024)
                               - 0.012 * (bump(-.081, 2.164, .041, .013) +
                                          bump(.081, 2.164, .041, .013)))
            vertices.append((x, y, z))
    faces = []
    for k in range(len(rings) - 1):
        for j in range(segments):
            a, b = k * segments + j, k * segments + (j + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    faces.extend([tuple(reversed(range(segments))),
                  tuple((len(rings) - 1) * segments + j for j in range(segments))])
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = len(poly.vertices) == 4
    if uv:
        layer = mesh.uv_layers.new(name="CharacterUV")
        for k, poly in enumerate(mesh.polygons):
            for n, loop_index in enumerate(poly.loop_indices):
                vi = mesh.loops[loop_index].vertex_index
                ridx, sidx = divmod(vi, segments)
                u = (sidx / segments)
                if k < (len(rings) - 1) * segments and n in (1, 2) and sidx == 0:
                    u = 1.0
                layer.data[loop_index].uv = (u, ridx / (len(rings) - 1))
    return obj


def _interp_rings(controls, step):
    result = []
    for (z0, rx0, ry0), (z1, rx1, ry1) in zip(controls, controls[1:]):
        slices = max(1, int(math.ceil((z1 - z0) / step)))
        for i in range(slices):
            t = i / slices
            t = t * t * (3.0 - 2.0 * t)
            result.append((0, 0, z0 + (z1 - z0) * i / slices,
                           rx0 * (1-t) + rx1 * t,
                           ry0 * (1-t) + ry1 * t))
    z, rx, ry = controls[-1]
    result.append((0, 0, z, rx, ry))
    return result


def _tube(bpy, coll, name, centers, radii, mat, segments=16):
    rings = [(x, y, z, r, r) for (x, y, z), r in zip(centers, radii)]
    if rings[0][2] > rings[-1][2]:
        rings.reverse()
    return _loft(bpy, coll, name, rings, mat, segments)


def _curve(bpy, coll, name, coords, material, bevel):
    data = bpy.data.curves.new(name + "_curve", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 12
    data.bevel_depth = bevel
    data.bevel_resolution = 2
    poly = data.splines.new("POLY")
    poly.points.add(len(coords) - 1)
    for point, (x, y, z) in zip(poly.points, coords):
        point.co = (x, y, z, 1.0)
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    data.materials.append(material)
    return obj


def _landmarks():
    positions = {"pelvis": (0, 0, 0.99), "navel": (0, -.14, 1.2),
                 "sternum": (0, -.15, 1.52), "neck": (0, 0, 1.81),
                 "chin": (0, -.13, 1.95), "nose_tip": (0, -.195, 2.09),
                 "crown": (0, 0, 2.29)}
    for side, sign in (("Left", -1), ("Right", 1)):
        positions.update({side + "Shoulder": (sign * .365, 0, 1.63),
                          side + "Elbow": (sign * .47, 0, 1.31),
                          side + "Wrist": (sign * .55, -.012, 1.00),
                          side + "Hand": (sign * .56, -.015, .88),
                          side + "Hip": (sign * .166, 0, .99),
                          side + "Knee": (sign * .18, -.023, .54),
                          side + "Ankle": (sign * .19, 0, .13),
                          side + "Toe": (sign * .19, -.22, .055),
                          side + "Eye": (sign * .079, -.11, 2.135)})
    return positions


def _construct(bpy, scene, coll, name, height):
    prefix = "Omega_" + name + "_"
    skin = _material(bpy, prefix + "Skin", (.48, .30, .22), .66)
    coat = _material(bpy, prefix + "Coat", (.065, .16, .24), .8)
    trouser = _material(bpy, prefix + "Trousers", (.09, .105, .14), .73)
    dark = _material(bpy, prefix + "Hair", (.075, .051, .04), .84)
    sclera = _material(bpy, prefix + "Eyes", (.83, .79, .7), .35)
    iris = _material(bpy, prefix + "Iris", (.15, .32, .27), .32)
    shoes = _material(bpy, prefix + "Shoes", (.035, .039, .045), .56)
    body_shape = [(0.955,.23,.145),(1.07,.225,.15),(1.21,.181,.127),
                  (1.41,.266,.163),(1.54,.316,.177),(1.61,.346,.145),
                  (1.68,.305,.12),(1.74,.125,.087),(1.81,.077,.077),
                  (1.875,.078,.079),(1.925,.116,.110),(1.97,.147,.133),
                  (2.04,.164,.151),(2.12,.172,.15),(2.19,.15,.132),
                  (2.245,.110,.1),(2.285,.032,.035)]
    rings = _interp_rings(body_shape, .009)
    body = _loft(bpy, coll, prefix + "BodyHead", rings, skin, face_relief=True)
    body["omega_mesh_role"] = "continuous_torso_neck_head_with_face_relief"
    # Loose shoulder and hip boundary joints are deliberate and reported as
    # seams until a real integrated retopology / deform test is performed.
    for side, sgn in (("Left", -1), ("Right", 1)):
        arm = _loft(bpy, coll, prefix + side + "Arm", [
            (sgn*.345,0,1.625,.115,.123),
            (sgn*.40,0,1.51,.10,.10),
            (sgn*.47,0,1.31,.077,.08),
            (sgn*.50,0,1.24,.071,.075),
            (sgn*.54,-.015,1.01,.047,.052),
            (sgn*.558,-.018,.956,.064,.038),
            (sgn*.565,-.02,.866,.068,.031)], skin, 32)
        arm["omega_mesh_role"] = "arm_palm_with_finger_seams"
        fingers = [(-.05,.080,.057),(-.026,.064,.080),(0,.064,.089),
                   (.027,.057,.080),(.055,.043,.061)]
        for i, (offset, r, length) in enumerate(fingers):
            x = sgn*.565 + offset * sgn
            _tube(bpy, coll, prefix + side + "Finger" + str(i+1), [
                (x,-.035,.867), (x + .009*sgn,-.045,.867-length*.50),
                (x + .013*sgn,-.046,.867-length)],
                [r*.23, r*.19, r*.12], skin, 12)
        _loft(bpy, coll, prefix + side + "Leg", [
            (sgn*.166,0,.986,.127,.134),
            (sgn*.173,-.01,.775,.114,.115),
            (sgn*.18,-.026,.55,.072,.080),
            (sgn*.186,.009,.36,.085,.086),
            (sgn*.19,.005,.13,.054,.060)], skin, 32)
        _loft(bpy, coll, prefix + side + "Pant", [
            (sgn*.166,0,.994,.132,.139),
            (sgn*.173,-.01,.781,.119,.121),
            (sgn*.18,-.024,.54,.080,.089),
            (sgn*.186,.009,.33,.090,.092),
            (sgn*.19,.004,.16,.066,.066)], trouser, 32)
        # Mesh boot tapers to the leg and grows toward the front-facing toe.
        _loft(bpy, coll, prefix + side + "Shoe", [
            (sgn*.19,-.095,0.0,.079,.148),
            (sgn*.19,-.074,.08,.073,.139),
            (sgn*.19,-.023,.15,.066,.074)], shoes, 32)
        x = sgn*.081
        eye = _tube(bpy, coll, prefix + side + "EyeWhite", [
            (x,-.112,2.132), (x,-.129,2.136), (x,-.112,2.14)],
            [.031,.030,.027], sclera, 24)
        eye["omega_mesh_role"] = "editable_eye_with_socket_relief"
        _tube(bpy, coll, prefix + side + "Iris", [
            (x,-.131,2.135), (x,-.136,2.136), (x,-.131,2.137)],
            [.014,.013,.013], iris, 20)
        _curve(bpy, coll, prefix + side + "Eyebrow", [
            (x+sgn*dx,-.135 + abs(dx)*.25,2.179 + .009*(1-abs(dx)/.046))
            for dx in (-.046,-.024,0,.024,.046)], dark, .004)
        _loft(bpy, coll, prefix + side + "Ear", [
            (sgn*.171,.004,2.047,.022,.031),
            (sgn*.181,.004,2.103,.031,.026),
            (sgn*.175,.004,2.159,.018,.020)], skin, 20)
    _curve(bpy, coll, prefix + "MouthLine", [
        (x,-.155 + .020*abs(x)/.072,2.034 - .004*math.cos(math.pi*x/.072))
        for x in (-.072,-.054,-.036,-.018,0,.018,.036,.054,.072)], dark, .0028)
    # Hair cap follows skull and 28 separately editable groom strands.
    _loft(bpy, coll, prefix + "HairCap", [
        (0,0,2.178,.153,.135), (0,0,2.20,.155,.138),
        (0,0,2.244,.118,.109), (0,0,2.286,.046,.047),
        (0,0,2.301,.009,.010)], dark)
    for i in range(28):
        angle = 2*math.pi*i/28
        x = .145*math.cos(angle)
        y = .123*math.sin(angle)
        length = .105 if y > -.015 else .036
        _curve(bpy, coll, prefix + "HairStrand%02d" % i, [
            (.65*x,.65*y,2.277), (x,y,2.20),
            (x*1.04,y*1.11,2.18-length)], dark, .0034)
    # Shirt is a separately editable shaped garment, not a renamed body box.
    shirt = _loft(bpy, coll, prefix + "Shirt", [
        (0,0,1.09,.226,.153),(0,0,1.22,.19,.136),
        (0,0,1.42,.277,.174),(0,0,1.53,.327,.189),
        (0,0,1.60,.351,.159),(0,0,1.675,.302,.13)], coat)
    shirt["omega_mesh_role"] = "separate_garment_with_annotated_openings"
    for obj in coll.objects:
        if obj.type in {"MESH", "CURVE"}:
            obj.scale = (_scale(height),) * 3
    # Three genuine editable Blender cameras; do NOT change active camera or render settings.
    from mathutils import Vector
    for label, position in (("Front", (0,-5,1.45)),
                            ("Side", (5,0,1.45)),
                            ("ThreeQuarter", (3,-4,1.75))):
        camera = bpy.data.cameras.new(prefix + label + "CameraData")
        ob = bpy.data.objects.new(prefix + label + "Camera", camera)
        coll.objects.link(ob)
        ob.location = tuple(v * _scale(height) for v in position)
        focus = Vector((0,0,1.3*_scale(height)))
        ob.rotation_euler = (focus-ob.location).to_track_quat("-Z", "Y").to_euler()
        camera.type = "ORTHO"
        camera.ortho_scale = 3.0 * _scale(height)
    return body


def _readback(bpy, scene, coll, revision):
    meshes = [ob for ob in coll.objects if ob.type == "MESH"]
    curves = [ob for ob in coll.objects if ob.type == "CURVE"]
    cameras = [ob for ob in coll.objects if ob.type == "CAMERA"]
    body = next((ob for ob in meshes if ob.get("omega_mesh_role") ==
                "continuous_torso_neck_head_with_face_relief"), None)
    faces = sum(len(ob.data.polygons) for ob in meshes)
    vertices = sum(len(ob.data.vertices) for ob in meshes)
    uv_ok = bool(meshes) and all(len(ob.data.uv_layers) > 0 for ob in meshes)
    checks = {"editable_body_head_surface": body is not None and len(body.data.vertices) > 1000,
              "uv_layers_on_meshes": uv_ok,
              "actual_hair_curves": len(curves) >= 25,
              "three_editable_views": len(cameras) == 3,
              "hands_with_fingers": sum("Finger" in ob.name for ob in meshes) == 10,
              "leg_and_foot_geometry": sum("Shoe" in ob.name for ob in meshes) == 2,
              "face_surface_relief": body is not None and body.get("omega_mesh_role") is not None}
    warnings = ["Shoulder, hip, garment and finger junctions have annotated seams; not a seamless retopology.",
                "No skin weights or deforming rig: Phase 06 must bind and verify.",
                "Synthetic anatomical style: reference likeness and artistic quality are not visually verified."]
    return {"operation": "omega.character.audit", "state": "succeeded",
            "scene": scene.name, "source_revision": revision,
            "created": [], "artifact": {"kind": "none", "sha256": None},
            "native_execution_verified": True, "visual_quality_verified": False,
            "quality_reduced": False, "warnings": warnings,
            "character_stage": "SCULPTED" if all(checks.values()) else "FAILED_QUALITY_GATE",
            "checks": checks, "mesh_vertices": vertices, "mesh_faces": faces,
            "mesh_parts": len(meshes), "hair_curves": len(curves),
            "landmarks": json.loads(coll["omega_landmarks_json"]),
            "uv_layers": sum(len(ob.data.uv_layers) for ob in meshes),
            "view_cameras": sorted(ob.name for ob in cameras),
            "body_object": body.name if body else None,
            "collection": coll.name, "reference_sha256": coll.get("omega_reference_sha256") or None}


def execute(operation, payload, context):
    args = validate(operation, payload)
    if operation == "omega.character.audit":
        return audit(operation, args, context)
    bpy, scene = _native(context)
    revision = _digest(args)
    existing = _existing(scene, args["name"])
    if existing:
        if existing.get("omega_source_revision") != revision:
            raise ValueError("CHECKPOINT_CONFLICT")
        receipt = _readback(bpy, scene, existing, revision)
        if receipt["character_stage"] == "FAILED_QUALITY_GATE":
            raise ValueError("CHECKPOINT_CONFLICT")
        receipt.update(operation=operation, already_complete=True)
        return receipt
    if context.get("dry_run"):
        return {"operation": operation, "state": "validated", "scene": scene.name,
                "source_revision": revision, "native_execution_verified": False,
                "visual_quality_verified": False, "quality_reduced": False,
                "created": [], "artifact": {"kind": "none", "sha256": None},
                "warnings": ["Dry run did not create geometry."]}
    if context.get("cancellation_requested") is True:
        raise RuntimeError("CANCELLED")
    coll = bpy.data.collections.new("OmegaChar_" + args["name"])
    scene.collection.children.link(coll)
    try:
        _construct(bpy, scene, coll, args["name"], args["height_m"])
        coll["omega_character_name"] = args["name"]
        coll["omega_phase"] = 5
        coll["omega_source_revision"] = revision
        coll["omega_reference_sha256"] = args["reference_sha256"] or ""
        coll["omega_landmarks_json"] = json.dumps({k: [round(v*_scale(args["height_m"]), 6) for v in xyz]
                                                  for k, xyz in _landmarks().items()}, sort_keys=True)
        coll["omega_mesh_seams"] = "shoulders;hips;fingers;shirt;shoes;eyes;ears;hair"
        result = _readback(bpy, scene, coll, revision)
        if result["character_stage"] == "FAILED_QUALITY_GATE":
            raise RuntimeError("FAILED_QUALITY_GATE")
        result["operation"] = operation
        result["created"] = sorted(ob.name for ob in coll.objects)
        result["already_complete"] = False
        return result
    except Exception:
        for ob in list(coll.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(coll)
        raise


def audit(operation, payload, context):
    args = validate(operation, payload)
    bpy, scene = _native(context)
    coll = _existing(scene, args["name"])
    if coll is None:
        raise ValueError("MISSING_REFERENCE")
    receipt = _readback(bpy, scene, coll, coll["omega_source_revision"])
    if operation == "omega.character.create":
        receipt["operation"] = operation
    return receipt
