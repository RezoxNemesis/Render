# SPDX-License-Identifier: GPL-2.0-or-later
"""Native creator tools: meshes, heightfields, instances, shaders, actions and rigs.

Every successful result corresponds to actual editable Blender datablocks.
The production dispatcher owns checkpoints, frozen-scene checks and serialization.
This module also rolls back its own partial edits if a native operation fails.
"""
import math
import random

import bpy
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree
import render_creator_contract as C


class _Transaction:
    """Track only our new IDs and explicit reversals; never delete existing IDs."""
    def __init__(self):
        self.created = []
        self.undo = []
        self.active = bpy.context.view_layer.objects.active
        self.selected = list(bpy.context.selected_objects)

    def add(self, collection, block):
        self.created.append((collection, block))
        return block

    def defer(self, callback):
        self.undo.append(callback)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        # Armature edit mode must be left before unlinking its object/data.
        current = bpy.context.object
        if current is not None and current.mode != "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="OBJECT")
            except (RuntimeError, ReferenceError):
                pass
        if exc_type is not None:
            for callback in reversed(self.undo):
                try:
                    callback()
                except (RuntimeError, ReferenceError, AttributeError):
                    pass
            # Objects and node groups own references to the remaining datablocks.
            for collection_name in ("objects", "node_groups", "actions", "armatures",
                                    "cameras", "materials", "meshes"):
                for collection, block in reversed(self.created):
                    if collection != collection_name:
                        continue
                    try:
                        getattr(bpy.data, collection).remove(block, do_unlink=True)
                    except (RuntimeError, ReferenceError, TypeError):
                        pass
        self.restore_selection()
        return False

    def restore_selection(self):
        try:
            for ob in list(bpy.context.selected_objects):
                ob.select_set(False)
            for ob in self.selected:
                if ob.name in bpy.context.view_layer.objects:
                    ob.select_set(True)
            if self.active is not None and self.active.name in bpy.context.view_layer.objects:
                bpy.context.view_layer.objects.active = self.active
            else:
                bpy.context.view_layer.objects.active = None
        except (RuntimeError, ReferenceError, AttributeError):
            pass


def _object(scene, name, kind=None, editable=True):
    ob = scene.objects.get(name)
    if ob is None or kind is not None and ob.type != kind:
        raise ValueError("CREATOR_OBJECT_NOT_FOUND")
    if ob.mode != "OBJECT":
        raise ValueError("CREATOR_OBJECT_MODE_REQUIRED")
    if editable and (ob.library is not None or ob.override_library is not None
                     or ob.data is not None and ob.data.library is not None):
        raise ValueError("CREATOR_LOCAL_EDITABLE_OBJECT_REQUIRED")
    return ob


def _new_name(name):
    if name in bpy.data.objects or name in bpy.data.collections:
        raise ValueError("CREATOR_NAME_EXISTS")
    return name


def _tag(ob, kind):
    ob["render_creator_contract"] = C.VERSION
    ob["render_creator_kind"] = kind


def _mesh_object(tx, scene, name, vertices, faces, material_indices=None):
    mesh = tx.add("meshes", bpy.data.meshes.new(name + "_Mesh"))
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    if mesh.validate(verbose=False):
        raise RuntimeError("CREATOR_INVALID_GENERATED_GEOMETRY")
    ob = tx.add("objects", bpy.data.objects.new(name, mesh))
    scene.collection.objects.link(ob)
    if material_indices is not None:
        for face, index in zip(mesh.polygons, material_indices):
            face.material_index = index
    return ob


def _simple_material(tx, name, color, metallic=0, roughness=.65):
    mat = tx.add("materials", bpy.data.materials.new(name))
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("CREATOR_PRINCIPLED_SHADER_UNAVAILABLE")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


class _Geometry:
    def __init__(self):
        self.vertices = []
        self.faces = []
        self.materials = []

    def add(self, vertices, faces, material=0):
        offset = len(self.vertices)
        self.vertices.extend(tuple(v) for v in vertices)
        self.faces.extend(tuple(offset + i for i in face) for face in faces)
        self.materials.extend([material] * len(faces))

    def box(self, center, dimensions, material=0, yaw=0):
        x, y, z = (v / 2 for v in dimensions)
        points = [(-x, -y, -z), (x, -y, -z), (x, y, -z), (-x, y, -z),
                  (-x, -y, z), (x, -y, z), (x, y, z), (-x, y, z)]
        c, s = math.cos(yaw), math.sin(yaw)
        points = [(a*c-b*s+center[0], a*s+b*c+center[1], d+center[2])
                  for a, b, d in points]
        self.add(points, [(3, 2, 1, 0), (0, 1, 5, 4), (1, 2, 6, 5),
                          (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], material)

    def lathe(self, profile, sides, material=0, center=(0, 0), caps=True):
        vertices, rings, faces = [], [], []
        for profile_index, (z, radius) in enumerate(profile):
            if profile_index == len(profile)-1 and len(profile) > 2 and profile[-1] == profile[0]:
                rings.append(rings[0])
                continue
            ring = []
            if radius == 0:
                ring.append(len(vertices))
                vertices.append((center[0], center[1], z))
            else:
                for j in range(sides):
                    angle = j * 2 * math.pi / sides
                    ring.append(len(vertices))
                    vertices.append((center[0] + math.cos(angle) * radius,
                                     center[1] + math.sin(angle) * radius, z))
            rings.append(ring)
        for lower, upper in zip(rings, rings[1:]):
            for j in range(sides):
                k = (j + 1) % sides
                if len(lower) == 1:
                    faces.append((lower[0], upper[k], upper[j]))
                elif len(upper) == 1:
                    faces.append((lower[j], lower[k], upper[0]))
                else:
                    faces.append((lower[j], lower[k], upper[k], upper[j]))
        if caps and len(rings[0]) > 1:
            faces.append(tuple(reversed(rings[0])))
        if caps and len(rings[-1]) > 1:
            faces.append(tuple(rings[-1]))
        self.add(vertices, faces, material)

    def hoop(self, z, radius, width, thickness, sides, material=1):
        # Closed annular cross section. Repeated first ring closes the profile.
        self.lathe([(z-width/2, radius-thickness), (z-width/2, radius),
                    (z+width/2, radius), (z+width/2, radius-thickness),
                    (z-width/2, radius-thickness)], sides, material, caps=False)


def _model_geometry(kind, size, detail, seed):
    g = _Geometry()
    s = size
    sides = 8 + detail * 4
    if kind == "crate":
        boards = 2 + detail
        gap = .012*s
        board = (s - gap*(boards+1)) / boards
        for i in range(boards):
            a = -s/2 + gap + board/2 + i*(board+gap)
            for y in (-.46*s, .46*s):
                g.box((a, y, .5*s), (board, .08*s, s))
            for x in (-.46*s, .46*s):
                g.box((x, a, .5*s), (.08*s, board, s))
            for z in (.04*s, .96*s):
                g.box((a, 0, z), (board, .84*s, .08*s))
        for x in (-.4*s, .4*s):
            for y in (-.505*s, .505*s):
                g.box((x, y, .5*s), (.12*s, .07*s, s), 1)
        for z in (.08*s, .92*s):
            for y in (-.505*s, .505*s):
                g.box((0, y, z), (s, .07*s, .12*s), 1)
    elif kind == "barrel":
        g.lathe([(0, .34*s), (.08*s, .39*s), (.25*s, .44*s),
                 (.5*s, .46*s), (.75*s, .44*s), (.92*s, .39*s), (s, .34*s)], sides)
        for z, radius in ((.12, .407), (.5, .473), (.88, .407)):
            g.hoop(z*s, radius*s, .055*s, .022*s, sides)
    elif kind == "column":
        g.box((0, 0, .035*s), (.52*s, .52*s, .07*s), 1)
        g.box((0, 0, .10*s), (.42*s, .42*s, .06*s))
        profile = []
        for j in range(detail*8+1):
            t = j/(detail*8)
            profile.append(((.14+.70*t)*s, (.15-.025*t+.012*math.sin(math.pi*t))*s))
        g.lathe(profile, sides)
        g.lathe([(.84*s, .13*s), (.90*s, .22*s), (.94*s, .22*s)], sides)
        g.box((0, 0, .97*s), (.5*s, .5*s, .06*s), 1)
    elif kind == "arch":
        for x in (-.365*s, .365*s):
            g.box((x, 0, .275*s), (.17*s, .32*s, .55*s))
            g.box((x, 0, .035*s), (.25*s, .42*s, .07*s), 1)
        segments = 6 + detail*6
        vertices = []
        for y in (-.16*s, .16*s):
            for radius in (.28*s, .45*s):
                for j in range(segments+1):
                    a = j*math.pi/segments
                    vertices.append((math.cos(a)*radius, y, .55*s+math.sin(a)*radius))
        n = segments+1
        faces = []
        for j in range(segments):
            # front, back, inner barrel, outer barrel surfaces
            faces.extend([(j, j+1, n+j+1, n+j),
                          (2*n+j, 3*n+j, 3*n+j+1, 2*n+j+1),
                          (j, 2*n+j, 2*n+j+1, j+1),
                          (n+j, n+j+1, 3*n+j+1, 3*n+j)])
        faces.extend([(0, n, 3*n, 2*n), (n-1, 3*n-1, 4*n-1, 2*n-1)])
        g.add(vertices, [tuple(reversed(face)) for face in faces])
    elif kind == "stairs":
        steps = 3 + detail*3
        profile = [(-s/2, 0), (s/2, 0), (s/2, s)]
        for j in range(steps, 0, -1):
            y = -s/2+(j-1)*s/steps
            profile.append((y, j*s/steps))
            if j > 1:
                profile.append((y, (j-1)*s/steps))
        n = len(profile)
        vertices = [(x, y, z) for x in (-.45*s, .45*s) for y, z in profile]
        faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
        faces.extend((j, (j+1)%n, (j+1)%n+n, j+n) for j in range(n))
        g.add(vertices, faces)
    elif kind == "table":
        for x in (-.38*s, .38*s):
            for y in (-.26*s, .26*s):
                g.box((x, y, .34*s), (.10*s, .10*s, .68*s), 1)
        for y in (-.26*s, .26*s):
            g.box((0, y, .61*s), (.84*s, .07*s, .12*s), 1)
        if detail > 1:
            g.box((0, 0, .22*s), (.76*s, .06*s, .07*s), 1)
        boards = 2+detail
        for j in range(boards):
            x = -.5*s+(j+.5)*s/boards
            g.box((x, 0, .72*s), (s/boards-.008*s, .72*s, .08*s))
    elif kind == "rock":
        rnd = random.Random(seed)
        rings = 3+detail*2
        vertices = [(0, 0, .02*s)]
        for i in range(1, rings):
            polar = math.pi*i/rings
            for j in range(sides):
                angle = j*2*math.pi/sides
                radius = math.sin(polar)*(.43+rnd.uniform(-.065, .065))*s
                vertices.append((radius*math.cos(angle), .8*radius*math.sin(angle),
                                 (.48-.46*math.cos(polar)+rnd.uniform(-.035, .035))*s))
        top = len(vertices)
        vertices.append((.03*s, -.02*s, .96*s))
        faces = []
        for j in range(sides):
            k = (j+1)%sides
            faces.append((0, 1+k, 1+j))
            for i in range(rings-2):
                a = 1+i*sides
                faces.append((a+j, a+k, a+sides+k, a+sides+j))
            a = 1+(rings-2)*sides
            faces.append((a+j, a+k, top))
        g.add(vertices, faces)
    elif kind == "tree":
        g.lathe([(0, .045*s), (.3*s, .035*s), (.65*s, .018*s)], sides, 1)
        for z, radius, height in ((.26, .29, .43), (.47, .23, .36), (.66, .16, .34)):
            g.lathe([(z*s, radius*s), ((z+height)*s, 0)], sides)
    return g


def _model(tx, scene, p):
    name = _new_name(p["name"])
    g = _model_geometry(p["kind"], p["size"], p["detail"], p["seed"])
    if len(g.vertices) > 4096 or sum(len(f)-2 for f in g.faces) > 8192:
        raise RuntimeError("CREATOR_MODEL_BUDGET_EXCEEDED")
    ob = _mesh_object(tx, scene, name, g.vertices, g.faces, g.materials)
    palettes = {"tree": ((.075, .24, .12), (.19, .075, .025)),
                "rock": ((.32, .36, .39), (.2, .22, .24)),
                "column": ((.61, .58, .49), (.42, .40, .35)),
                "arch": ((.52, .48, .39), (.38, .35, .29)),
                "stairs": ((.40, .43, .46), (.27, .30, .33))}
    colors = palettes.get(p["kind"], ((.30, .12, .04), (.12, .055, .022)))
    if p["kind"] == "barrel":
        colors = (colors[0], (.18, .2, .23))
    for i, color in enumerate(colors):
        ob.data.materials.append(_simple_material(tx, name+"_Surface_"+str(i+1), color,
                                 metallic=.8 if p["kind"] == "barrel" and i == 1 else 0))
    _tag(ob, p["kind"])
    ob["render_creator_seed"] = p["seed"]
    return {"object": ob.name, "kind": p["kind"], "vertices": len(ob.data.vertices),
            "polygons": len(ob.data.polygons), "native_editable_mesh": True,
            "size": p["size"], "detail": p["detail"], "seed": p["seed"]}


def _hash_noise(x, y, seed):
    n = (x*374761393 + y*668265263 + seed*1442695041) & 0xffffffff
    n = ((n ^ (n >> 13))*1274126177) & 0xffffffff
    return ((n ^ (n >> 16)) & 0xffffffff)/4294967295


def _noise(x, y, seed):
    ix, iy = math.floor(x), math.floor(y)
    a, b = x-ix, y-iy
    a, b = a*a*(3-2*a), b*b*(3-2*b)
    lo = _hash_noise(ix, iy, seed)*(1-a)+_hash_noise(ix+1, iy, seed)*a
    hi = _hash_noise(ix, iy+1, seed)*(1-a)+_hash_noise(ix+1, iy+1, seed)*a
    return lo*(1-b)+hi*b


def _height(x, y, style, seed, height):
    total, weight = 0., 0.
    for octave in range(4):
        amp = .5**octave
        frequency = 2**octave*2.5
        total += amp*_noise(x*frequency+13.7, y*frequency+9.2, seed+octave*101)
        weight += amp
    n = total/weight
    if style == "island":
        falloff = max(0., 1.-(x*x+y*y))**1.7
        return height*falloff*(.30+.70*n)
    if style == "mountains":
        return height*(.35*n+.65*(1-abs(2*n-1))**3)
    if style == "dunes":
        wave = .5+.5*math.sin(x*10+y*4+n*2.5)
        return height*(wave*.68+n*.32)
    return height*n*.08


def _terrain(tx, scene, p):
    name = _new_name(p["name"])
    res, size = p["resolution"], p["size"]
    vertices, faces = [], []
    for y in range(res+1):
        for x in range(res+1):
            nx, ny = x/res*2-1, y/res*2-1
            vertices.append((nx*size/2, ny*size/2,
                             _height(nx, ny, p["style"], p["seed"], p["height"])))
    for y in range(res):
        for x in range(res):
            a = y*(res+1)+x
            faces.append((a, a+1, a+res+2, a+res+1))
    ob = _mesh_object(tx, scene, name, vertices, faces)
    uv = ob.data.uv_layers.new(name="CreatorTerrainUV")
    for face in ob.data.polygons:
        face.use_smooth = True
        for li in face.loop_indices:
            co = ob.data.vertices[ob.data.loops[li].vertex_index].co
            uv.data[li].uv = (co.x/size+.5, co.y/size+.5)
    colors = {"island": ((.12, .25, .075), (.52, .46, .25)),
              "mountains": ((.17, .20, .15), (.65, .66, .63)),
              "dunes": ((.40, .22, .07), (.82, .63, .32)),
              "plains": ((.08, .19, .045), (.32, .39, .13))}
    low, high = colors[p["style"]]
    mat = _simple_material(tx, name+"_TerrainSurface", low, roughness=.92)
    tree = mat.node_tree
    coord = tree.nodes.new("ShaderNodeTexCoord")
    separate = tree.nodes.new("ShaderNodeSeparateXYZ")
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*low, 1)
    ramp.color_ramp.elements[1].color = (*high, 1)
    tree.links.new(coord.outputs["Generated"], separate.inputs["Vector"])
    tree.links.new(separate.outputs["Z"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], tree.nodes.get("Principled BSDF").inputs["Base Color"])
    coord.location = (-700, 0); separate.location = (-470, 0); ramp.location = (-240, 0)
    ob.data.materials.append(mat)
    _tag(ob, "terrain")
    ob["render_creator_seed"] = p["seed"]
    ob["render_creator_terrain_size"] = size
    ob["render_creator_terrain_resolution"] = res
    return {"object": ob.name, "style": p["style"], "seed": p["seed"],
            "vertices": len(vertices), "quads": len(faces),
            "resolution": res, "size": size,
            "native_editable_heightfield": True,
            "height_range": [min(v[2] for v in vertices), max(v[2] for v in vertices)]}


def _evaluated_triangles(ob, depsgraph):
    evaluated = ob.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    if mesh is None:
        raise ValueError("CREATOR_SCATTER_SOURCE_HAS_NO_MESH")
    try:
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)
    finally:
        evaluated.to_mesh_clear()


def _bounds(ob, depsgraph=None):
    target = ob.evaluated_get(depsgraph) if depsgraph is not None else ob
    points = [target.matrix_world @ Vector(v) for v in target.bound_box]
    if not points or all(tuple(v) == (-1., -1., -1.) for v in target.bound_box):
        center = target.matrix_world.translation.copy()
        return center, center.copy(), center.copy()
    lower = Vector(tuple(min(v[i] for v in points) for i in range(3)))
    upper = Vector(tuple(max(v[i] for v in points) for i in range(3)))
    return (lower+upper)/2, lower, upper


def _scatter(tx, scene, p):
    name = _new_name(p["name"])
    source = _object(scene, p["source"], "MESH", editable=False)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = _evaluated_triangles(source, depsgraph)
    if triangles < 1 or triangles > C.MAX_SOURCE_TRIANGLES:
        raise ValueError("CREATOR_SCATTER_SOURCE_BUDGET_EXCEEDED")
    if triangles*p["count"] > C.MAX_SCATTER_TRIANGLES:
        raise ValueError("CREATOR_SCATTER_TRIANGLE_BUDGET_EXCEEDED")
    center = Vector((0, 0, 0))
    surface, inverse, top, direction = None, None, None, None
    if "terrain" in p:
        terrain = _object(scene, p["terrain"], "MESH", editable=False)
        surface = BVHTree.FromObject(terrain, depsgraph)
        center, low, high = _bounds(terrain, depsgraph)
        if abs(terrain.matrix_world.determinant()) < 1e-12:
            raise ValueError("CREATOR_TERRAIN_TRANSFORM_SINGULAR")
        inverse = terrain.matrix_world.inverted()
        direction = (inverse.to_3x3() @ Vector((0, 0, -1))).normalized()
        top = high.z+max(1., high.z-low.z)
    evaluated_source = source.evaluated_get(depsgraph)
    source_matrix = evaluated_source.matrix_world
    _, rotation, scale = source_matrix.decompose()
    if min(abs(v) for v in scale) < 1e-8:
        raise ValueError("CREATOR_SOURCE_TRANSFORM_SINGULAR")
    base_offset = -min((source_matrix.to_3x3() @ Vector(v)).z for v in evaluated_source.bound_box)
    rnd = random.Random(p["seed"])
    points, scales, rotations = [], [], []
    half = p["extent"]/2
    attempts = 0
    while len(points) < p["count"] and attempts < p["count"]*8+64:
        attempts += 1
        x, y = center.x+rnd.uniform(-half, half), center.y+rnd.uniform(-half, half)
        z = 0.
        if surface is not None:
            hit, normal, index, distance = surface.ray_cast(inverse @ Vector((x, y, top)), direction)
            if hit is None:
                continue
            z = (terrain.matrix_world @ hit).z
        factor = rnd.uniform(p["min_scale"], p["max_scale"])
        yaw = rnd.uniform(-math.pi, math.pi)
        points.append((x, y, z+base_offset*factor))
        scales.append(tuple(v*factor for v in scale))
        rotations.append(tuple((Quaternion((0, 0, 1), yaw) @ rotation).to_euler("XYZ")))
    if len(points) != p["count"]:
        raise ValueError("CREATOR_SCATTER_TERRAIN_COVERAGE_INSUFFICIENT")
    ob = _mesh_object(tx, scene, name, points, [])
    scale_attr = ob.data.attributes.new("creator_scale", "FLOAT_VECTOR", "POINT")
    rot_attr = ob.data.attributes.new("creator_rotation", "FLOAT_VECTOR", "POINT")
    for data, value in zip(scale_attr.data, scales):
        data.vector = value
    for data, value in zip(rot_attr.data, rotations):
        data.vector = value
    group = tx.add("node_groups", bpy.data.node_groups.new(name+"_Instances", "GeometryNodeTree"))
    if hasattr(group, "interface"):
        group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    else:
        group.inputs.new("NodeSocketGeometry", "Geometry")
        group.outputs.new("NodeSocketGeometry", "Geometry")
    nodes, links = group.nodes, group.links
    incoming = nodes.new("NodeGroupInput")
    outgoing = nodes.new("NodeGroupOutput")
    info = nodes.new("GeometryNodeObjectInfo")
    info.transform_space = "ORIGINAL"
    info.inputs["Object"].default_value = source
    info.inputs["As Instance"].default_value = False
    pack = nodes.new("GeometryNodeGeometryToInstance")
    instances = nodes.new("GeometryNodeInstanceOnPoints")
    attr_scale = nodes.new("GeometryNodeInputNamedAttribute")
    attr_scale.data_type = "FLOAT_VECTOR"
    attr_scale.inputs["Name"].default_value = "creator_scale"
    attr_rotation = nodes.new("GeometryNodeInputNamedAttribute")
    attr_rotation.data_type = "FLOAT_VECTOR"
    attr_rotation.inputs["Name"].default_value = "creator_rotation"
    links.new(incoming.outputs["Geometry"], instances.inputs["Points"])
    links.new(info.outputs["Geometry"], pack.inputs["Geometry"])
    links.new(pack.outputs["Instances"], instances.inputs["Instance"])
    links.new(attr_scale.outputs["Attribute"], instances.inputs["Scale"])
    links.new(attr_rotation.outputs["Attribute"], instances.inputs["Rotation"])
    links.new(instances.outputs["Instances"], outgoing.inputs["Geometry"])
    incoming.location=(-600, 160); info.location=(-800, -60); pack.location=(-540, -60)
    attr_scale.location=(-540, -240); attr_rotation.location=(-540, -440)
    instances.location=(-160, 160); outgoing.location=(120, 160)
    mod = ob.modifiers.new("Creator Linked Instances", "NODES")
    mod.node_group = group
    _tag(ob, "scatter")
    ob["render_creator_source"] = source.name
    ob["render_creator_count"] = p["count"]
    ob["render_creator_seed"] = p["seed"]
    return {"object": ob.name, "source": source.name, "instances": len(points),
            "seed": p["seed"], "point_mesh_vertices": len(ob.data.vertices),
            "source_triangles": triangles, "estimated_visible_triangles": triangles*len(points),
            "native_geometry_nodes_instances": True, "realized_mesh_copies": 0,
            "terrain": p.get("terrain"), "terrain_projection": surface is not None}


_COLORS = {"wood": (.32, .13, .045), "metal": (.36, .40, .45),
           "stone": (.35, .37, .34), "fabric": (.14, .25, .38),
           "ceramic": (.72, .78, .80), "emissive": (.10, .48, 1.)}


def _procedural_material(tx, name, preset, color, scale):
    rough = {"wood": .55, "metal": .28, "stone": .82, "fabric": .94,
             "ceramic": .19, "emissive": .30}[preset]
    mat = _simple_material(tx, name, color, metallic=1 if preset == "metal" else 0,
                           roughness=rough)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if preset == "emissive":
        socket = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if socket is None:
            raise RuntimeError("CREATOR_EMISSION_SHADER_UNAVAILABLE")
        socket.default_value = (*color, 1)
        strength = bsdf.inputs.get("Emission Strength")
        if strength is not None:
            strength.default_value = 4.
    else:
        coord = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1, 1, 1)
        links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
        if preset in ("wood", "fabric"):
            texture = nodes.new("ShaderNodeTexWave")
            texture.wave_type = "RINGS" if preset == "wood" else "BANDS"
            if preset == "wood":
                texture.rings_direction = "Z"
                texture.inputs["Distortion"].default_value = 3.
                texture.inputs["Detail"].default_value = 2.
            else:
                texture.bands_direction = "DIAGONAL"
        else:
            texture = nodes.new("ShaderNodeTexNoise")
            texture.inputs["Detail"].default_value = 2.
            texture.inputs["Roughness"].default_value = .65
        texture.inputs["Scale"].default_value = scale
        links.new(mapping.outputs["Vector"], texture.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        dark = .62 if preset in ("wood", "stone", "fabric") else .85
        ramp.color_ramp.elements[0].color = (*(x*dark for x in color), 1)
        ramp.color_ramp.elements[1].color = (*(min(1., x*1.2+.025) for x in color), 1)
        links.new(texture.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        bump = nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = .18 if preset in ("stone", "fabric") else .06
        bump.inputs["Distance"].default_value = .035 if preset == "stone" else .008
        links.new(texture.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        coord.location=(-1000, 100); mapping.location=(-800, 100)
        texture.location=(-580, 100); ramp.location=(-300, 160); bump.location=(-260, -150)
    bsdf.location=(40, 100)
    mat["render_creator_material_preset"] = preset
    return mat


def _material(tx, scene, p):
    ob = _object(scene, p["object"], "MESH")
    if len(ob.data.materials) >= 128:
        raise ValueError("CREATOR_MATERIAL_SLOT_BUDGET_EXCEEDED")
    if len(ob.data.polygons) == 0:
        raise ValueError("CREATOR_MATERIAL_SURFACE_REQUIRED")
    mat = _procedural_material(tx, ob.name+"_"+p["preset"], p["preset"],
                               p.get("color", _COLORS[p["preset"]]), p["scale"])
    old_mesh = ob.data
    copied = old_mesh.users > 1
    if copied:
        mesh = tx.add("meshes", old_mesh.copy())
        tx.defer(lambda: setattr(ob, "data", old_mesh))
        ob.data = mesh
    else:
        mesh = old_mesh
    old_indices = [face.material_index for face in mesh.polygons]
    index = len(mesh.materials)
    def restore():
        if len(mesh.materials) > index:
            mesh.materials.pop(index=index)
        for face, old in zip(mesh.polygons, old_indices):
            face.material_index = old
    tx.defer(restore)
    mesh.materials.append(mat)
    for face in mesh.polygons:
        face.material_index = index
    return {"object": ob.name, "material": mat.name, "preset": p["preset"],
            "shader_nodes": len(mat.node_tree.nodes), "native_shader_graph": True,
            "previous_material_slots_preserved": True,
            "shared_mesh_copied_for_object_local_edit": copied}


def _curves(action):
    """Blender 4.x legacy and 4.4+/5.x slotted actions, without duplicate curves."""
    result, seen = [], set()
    try:
        legacy = action.fcurves
    except (AttributeError, RuntimeError):
        legacy = ()
    for curve in legacy:
        seen.add(curve.as_pointer()); result.append(curve)
    for layer in getattr(action, "layers", ()):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", ()):
                for curve in bag.fcurves:
                    if curve.as_pointer() not in seen:
                        seen.add(curve.as_pointer()); result.append(curve)
    return result


def _finish_action(action, loop=False, offset=False, interpolation="LINEAR"):
    curves = _curves(action)
    if not curves:
        raise RuntimeError("CREATOR_NATIVE_ACTION_EMPTY")
    for curve in curves:
        for key in curve.keyframe_points:
            key.interpolation = interpolation
            if interpolation == "BEZIER":
                key.handle_left_type = "AUTO_CLAMPED"
                key.handle_right_type = "AUTO_CLAMPED"
        if loop:
            cycle = curve.modifiers.new("CYCLES")
            cycle.mode_before = "REPEAT_OFFSET" if offset else "REPEAT"
            cycle.mode_after = "REPEAT_OFFSET" if offset else "REPEAT"
        curve.update()
    return curves


def _action(tx, ob, name):
    previous = ob.animation_data
    if previous is not None and (previous.action is not None or previous.nla_tracks or previous.drivers):
        raise ValueError("CREATOR_EXISTING_ANIMATION_PRESERVED")
    if previous is None:
        tx.defer(lambda: ob.animation_data_clear())
    else:
        tx.defer(lambda: setattr(ob.animation_data, "action", None))
    act = tx.add("actions", bpy.data.actions.new(name))
    ob.animation_data_create()
    ob.animation_data.action = act
    return act


def _motion(tx, scene, p):
    ob = _object(scene, p["object"])
    if any(not constraint.mute for constraint in ob.constraints):
        raise ValueError("CREATOR_CONSTRAINED_MOTION_REQUIRES_MANUAL_EDIT")
    old_location = ob.location.copy()
    old_rotation = ob.rotation_euler.copy()
    old_quaternion = ob.rotation_quaternion.copy()
    old_axis_angle = tuple(ob.rotation_axis_angle)
    old_mode = ob.rotation_mode
    def restore():
        ob.rotation_mode = old_mode
        ob.location = old_location
        ob.rotation_euler = old_rotation
        ob.rotation_quaternion = old_quaternion
        ob.rotation_axis_angle = old_axis_angle
    tx.defer(restore)
    act = _action(tx, ob, ob.name+"_Creator_"+p["preset"])
    base_rotation = ob.matrix_basis.to_quaternion().to_euler("XYZ")
    if p["preset"] == "turntable":
        ob.rotation_mode = "XYZ"
    steps = 1 if p["preset"] == "turntable" else 32
    for i in range(steps+1):
        t = i/steps
        frame = p["start"] + (p["end"]-p["start"])*t
        if p["preset"] == "turntable":
            ob.rotation_euler = (base_rotation.x, base_rotation.y,
                                 base_rotation.z+2*math.pi*p["amount"]*t)
            path = "rotation_euler"
        else:
            location = old_location.copy()
            if p["preset"] == "float":
                location.z += p["amount"]*math.sin(2*math.pi*t)
            elif p["preset"] == "bounce":
                location.z += p["amount"]*4*t*(1-t)
            else:
                location.x += p["amount"]*(math.cos(2*math.pi*t)-1)
                location.y += p["amount"]*math.sin(2*math.pi*t)
            ob.location = location
            path = "location"
        if not ob.keyframe_insert(data_path=path, frame=frame, group="Creator Motion"):
            raise RuntimeError("CREATOR_KEYFRAME_INSERT_FAILED")
    curves = _finish_action(act, p["loop"], p["preset"] == "turntable",
                            "BEZIER" if p["preset"] in ("float", "bounce") else "LINEAR")
    # Evaluate the result at the user's current time without moving the timeline.
    scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
    return {"object": ob.name, "action": act.name, "preset": p["preset"],
            "start": p["start"], "end": p["end"], "loop": p["loop"],
            "fcurves": len(curves), "keyframes": sum(len(c.keyframe_points) for c in curves),
            "native_transform_action": True, "existing_animation_overwritten": False}


def _camera(tx, scene, p):
    target = _object(scene, p["target"], editable=False)
    name = _new_name(p["name"])
    camera = tx.add("cameras", bpy.data.cameras.new(name+"_Lens"))
    camera.lens = {"hero": 50, "orbit": 40, "top": 50, "closeup": 85}[p["preset"]]
    camera.clip_start = .01
    camera.clip_end = max(1000., p["radius"]*100)
    camera_ob = tx.add("objects", bpy.data.objects.new(name, camera))
    scene.collection.objects.link(camera_ob)
    camera_ob.rotation_mode = "QUATERNION"
    previous_camera = scene.camera
    previous_frame, previous_subframe = scene.frame_current, scene.frame_subframe
    tx.defer(lambda: setattr(scene, "camera", previous_camera))
    action = None
    try:
        if p["preset"] == "orbit":
            action = _action(tx, camera_ob, name+"_Orbit")
            previous_rotation = None
            for i in range(33):
                t = i/32
                frame = p["start"]+(p["end"]-p["start"])*t
                whole = math.floor(frame)
                scene.frame_set(whole, subframe=frame-whole)
                center, low, high = _bounds(target, bpy.context.evaluated_depsgraph_get())
                a = t*math.pi*2-math.pi/2
                location = center+Vector((math.cos(a), math.sin(a), .45))*p["radius"]
                rotation = (center-location).to_track_quat("-Z", "Y")
                if previous_rotation is not None and rotation.dot(previous_rotation) < 0:
                    rotation.negate()
                camera_ob.location = location
                camera_ob.rotation_quaternion = rotation
                previous_rotation = rotation.copy()
                if not camera_ob.keyframe_insert(data_path="location", frame=frame, group="Creator Camera"):
                    raise RuntimeError("CREATOR_CAMERA_KEYFRAME_FAILED")
                if not camera_ob.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="Creator Camera"):
                    raise RuntimeError("CREATOR_CAMERA_KEYFRAME_FAILED")
            _finish_action(action)
        else:
            bpy.context.view_layer.update()
            center, low, high = _bounds(target, bpy.context.evaluated_depsgraph_get())
            direction = Vector((0, 0, 1)) if p["preset"] == "top" else Vector((1, -1, .65))
            if p["preset"] == "closeup":
                direction = Vector((.5, -1, .3))
            camera_ob.location = center+direction.normalized()*p["radius"]
            camera_ob.rotation_quaternion = (center-camera_ob.location).to_track_quat("-Z", "Y")
        scene.camera = camera_ob
        _tag(camera_ob, "camera")
    finally:
        scene.frame_set(previous_frame, subframe=previous_subframe)
    return {"object": camera_ob.name, "camera": camera_ob.name, "target": target.name,
            "preset": p["preset"], "active_scene_camera": scene.camera.name,
            "lens_mm": camera.lens, "action": action.name if action is not None else None,
            "native_camera": True,
            "target_tracking": "sampled_native_keyframes" if action is not None else "creation_time_bounds",
            "frame_range": [p["start"], p["end"]] if action is not None else None}


def _rig(tx, scene, p):
    ob = _object(scene, p["object"], "MESH")
    name = _new_name(p["name"])
    if not ob.data.polygons or any(mod.type == "NODES" for mod in ob.modifiers):
        raise ValueError("CREATOR_RIG_EDITABLE_SURFACE_REQUIRED")
    if not 4 <= len(ob.data.vertices) <= C.MAX_RIG_VERTICES:
        raise ValueError("CREATOR_RIG_VERTEX_BUDGET_EXCEEDED")
    if any(mod.type == "ARMATURE" for mod in ob.modifiers):
        raise ValueError("CREATOR_EXISTING_ARMATURE_PRESERVED")
    if abs(ob.matrix_world.determinant()) < 1e-12:
        raise ValueError("CREATOR_RIG_TRANSFORM_SINGULAR")
    bone_names = ["CreatorBone_%02d" % (i+1) for i in range(p["segments"])]
    if any(ob.vertex_groups.get(n) is not None for n in bone_names):
        raise ValueError("CREATOR_RIG_VERTEX_GROUP_EXISTS")
    lower = [min(v.co[i] for v in ob.data.vertices) for i in range(3)]
    upper = [max(v.co[i] for v in ob.data.vertices) for i in range(3)]
    axis = max(range(3), key=lambda i: upper[i]-lower[i])
    length = upper[axis]-lower[axis]
    if length < .0001:
        raise ValueError("CREATOR_RIG_MESH_TOO_SMALL")
    midpoint = Vector(tuple((a+b)/2 for a, b in zip(lower, upper)))
    armature = tx.add("armatures", bpy.data.armatures.new(name+"_Bones"))
    rig = tx.add("objects", bpy.data.objects.new(name, armature))
    scene.collection.objects.link(rig)
    rig.matrix_world = ob.matrix_world.copy()
    rig.show_in_front = True
    armature.display_type = "BBONE"
    for selected in list(bpy.context.selected_objects):
        selected.select_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        previous = None
        for i, bone_name in enumerate(bone_names):
            bone = armature.edit_bones.new(bone_name)
            head, tail = midpoint.copy(), midpoint.copy()
            head[axis] = lower[axis]+length*i/p["segments"]
            tail[axis] = lower[axis]+length*(i+1)/p["segments"]
            bone.head, bone.tail = head, tail
            bone.use_deform = True
            if previous is not None:
                bone.parent = previous
                bone.use_connect = True
            previous = bone
    finally:
        if rig.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    old_mesh = ob.data
    copied = old_mesh.users > 1
    if copied:
        mesh = tx.add("meshes", old_mesh.copy())
        tx.defer(lambda: setattr(ob, "data", old_mesh))
        ob.data = mesh
    groups = []
    for bone_name in bone_names:
        group = ob.vertex_groups.new(name=bone_name)
        groups.append(group)
        tx.defer(lambda group=group: ob.vertex_groups.remove(group))
    for vertex in ob.data.vertices:
        value = (vertex.co[axis]-lower[axis])/length*p["segments"]-.5
        lo = math.floor(value)
        fraction = value-lo
        a = max(0, min(p["segments"]-1, lo))
        b = max(0, min(p["segments"]-1, lo+1))
        if a == b:
            groups[a].add([vertex.index], 1., "REPLACE")
        else:
            groups[a].add([vertex.index], 1-fraction, "REPLACE")
            groups[b].add([vertex.index], fraction, "REPLACE")
    modifier = ob.modifiers.new("Creator Deform Chain", "ARMATURE")
    tx.defer(lambda: ob.modifiers.remove(modifier))
    modifier.object = rig
    modifier.use_deform_preserve_volume = True
    _tag(rig, "deform_chain")
    return {"object": rig.name, "rig": rig.name, "mesh": ob.name,
            "bones": bone_names, "segments": len(armature.bones), "axis": "XYZ"[axis],
            "weighted_vertices": len(ob.data.vertices), "native_armature_modifier": True,
            "shared_mesh_copied_for_object_local_edit": copied,
            "rig_scope": "flexible_prop_deform_chain", "humanoid_auto_rig": False}


_HANDLERS = {"studio.create.model": _model, "studio.create.terrain": _terrain,
             "studio.create.scatter": _scatter, "studio.create.material": _material,
             "studio.create.motion": _motion, "studio.create.camera": _camera,
             "studio.create.rig": _rig}


def execute(operation, payload, root, scene):
    """Run on Blender's main thread through the production checkpoint dispatcher."""
    p = C.validate(operation, payload)
    if operation == "studio.create.catalog":
        return C.catalog()
    if scene != bpy.context.scene:
        raise ValueError("CREATOR_ACTIVE_SCENE_REQUIRED")
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        raise ValueError("CREATOR_OBJECT_MODE_REQUIRED")
    with _Transaction() as tx:
        return _HANDLERS[operation](tx, scene, p)
