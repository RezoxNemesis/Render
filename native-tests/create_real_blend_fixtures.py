# SPDX-License-Identifier: GPL-2.0-or-later
"""Generate REAL Blender project fixtures with upstream bpy on a Linux CI host.

This is a test tool only; end-user Render/Android never requires desktop Blender
or a remote render server. The files exercise Android's own native C++ readers.
"""
import argparse
import gzip
import json
import os
import pathlib
import sys

import bpy


def main():
    arguments = sys.argv
    arguments = arguments[arguments.index("--") + 1:] if "--" in arguments else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(arguments)
    destination = pathlib.Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=False)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    scene = bpy.context.scene

    def make_mesh_object(name, shift):
        mesh = bpy.data.meshes.new(name + "_Mesh")
        mesh.from_pydata([(0, 0, 0), (1.2, 0, 0), (0, 1.1, 0), (0, 0, 1.4)],
                         [], [(0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3)])
        mesh.update()
        ob = bpy.data.objects.new(name, mesh)
        scene.collection.objects.link(ob)
        ob.location = (shift, 0.0, 0.0)
        return ob

    first = make_mesh_object("Render_RealMesh_A", 0.0)
    second = make_mesh_object("Render_RealMesh_B", 3.0)
    scene.frame_start = 1
    scene.frame_end = 24
    first.location.x = 0
    first.keyframe_insert(data_path="location", frame=1)
    first.location.x = 2
    first.keyframe_insert(data_path="location", frame=24)
    bpy.context.view_layer.objects.active = first

    plain = destination / "render_real_scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(plain), compress=False, check_existing=False)

    mat = bpy.data.materials.new("Render_RealMaterial")
    mat.use_nodes = True
    first.data.materials.append(mat)
    extra = bpy.data.scenes.new("Render_AdditionalScene")
    extra.frame_start = 1
    extra.frame_end = 48
    advanced = destination / "render_animated_scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(advanced), compress=False, check_existing=False)
    native_compressed = destination / "render_blender_compressed_scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(native_compressed), compress=True, check_existing=False)

    gzip_file = destination / "render_real_scene.blend.gz"
    with plain.open("rb") as stream:
        with gzip_file.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, filename="", mode="wb",
                               compresslevel=6, mtime=0) as compressed:
                while True:
                    block = stream.read(1048576)
                    if not block:
                        break
                    compressed.write(block)

    manifest = {
        "generator": "Actual upstream Blender Python API (bpy)",
        "blender_version": bpy.app.version_string,
        "raw": plain.name,
        "animated": advanced.name,
        "gzip_envelope": gzip_file.name,
        "blender_native_compressed": native_compressed.name,
        "expected_minimum": {"objects": 2, "meshes": 2, "scenes": 1},
    }
    (destination / "fixture_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print("Render test fixtures generated:", json.dumps(manifest))
    for p in (plain, advanced, gzip_file, native_compressed):
        assert p.is_file() and p.stat().st_size > 1024, f"Invalid output: {p}"


if __name__ == "__main__":
    main()
