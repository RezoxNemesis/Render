# SPDX-License-Identifier: GPL-2.0-or-later
"""Real headless Blender evidence: duplicate geometry, material alpha, low-res texture.

Headless mode intentionally cannot claim a working viewport image. The
visual GPU tests belong to the separate windowed Xvfb acceptance flow.
"""
import os
from pathlib import Path
import sys
import tempfile
import bpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_viewport_fidelity as Fidelity
import render_viewport_fidelity_contract as Contract

with tempfile.TemporaryDirectory() as scratch:
    os.environ["RENDER_AGENT_SPOOL"]=str(Path(scratch)/"bpy_jobs")
    scene=bpy.context.scene
    before=(scene.render.engine,scene.render.fps,
            scene.render.resolution_x,scene.render.resolution_y,
            scene.render.resolution_percentage)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.mesh.primitive_cube_add(size=2,location=(0,0,0))
    target=bpy.context.object
    target.name="ActorHead"
    duplicate=target.copy()
    duplicate.name="DuplicateActorHead"
    scene.collection.objects.link(duplicate)
    assert target.data==duplicate.data
    assert target.data.users>=2

    material=bpy.data.materials.new("ThinTranslucentSkin")
    material.use_nodes=True
    material.diffuse_color=(.7,.5,.43,.45)
    if hasattr(material,"blend_method"):
        material.blend_method="BLEND"
    principled=next(n for n in material.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    principled.inputs["Alpha"].default_value=.6
    image=bpy.data.images.new("PoorQuality128",width=128,height=128,alpha=True)
    node=material.node_tree.nodes.new("ShaderNodeTexImage")
    node.image=image
    target.data.materials.append(material)
    # Both meshes share their data; the diagnosis detects double surfaces.
    target.scale=(1,1,1.4)
    duplicate.scale=(1,1,1.4)

    result=Fidelity.diagnose(scene,{"object":target.name})
    assert result["object_found"] and result["object"]==target.name,result
    assert "NON_UNIFORM_OBJECT_SCALE" in result["issues"],result
    assert "TRANSPARENT_OR_MIXED_ALPHA_MATERIAL" in result["issues"],result
    assert "SMALL_OR_MISSING_TEXTURE_IMAGES" in result["issues"],result
    assert "NEAR_COINCIDENT_MESHES_POSSIBLE_Z_FIGHTING" in result["issues"],result
    assert any(item["evidence"]=="same_mesh_data_and_transform"
               for item in result["overlap_candidates"]),result
    assert not result["geometry_modified"] and not result["material_modified"]
    assert result["diagnosis_limit"].startswith("Evidence-based"),result
    assert target.data.users==2
    assert len(target.data.polygons)==6
    assert scene.objects.get("DuplicateActorHead") is not None
    assert before==(scene.render.engine,scene.render.fps,
                    scene.render.resolution_x,scene.render.resolution_y,
                    scene.render.resolution_percentage)

    no_area=Fidelity.inspect(scene,{})
    assert not no_area["native_viewport_available"]
    try:
        Fidelity.apply(scene,{"profile":"CLEAN_SOLID"})
        raise AssertionError("Headless Blender produced a fake 3D viewport")
    except ValueError as error:
        assert str(error)=="STUDIO_PREVIEW_NATIVE_3D_VIEW_UNAVAILABLE",error
    caps=Fidelity.capabilities({})
    assert len(caps["operations"])==len(Contract.OPS)
    assert not caps["core_engine_replaced"]
    assert not caps["texture_or_mesh_reconstruction_available"]
    print("PASS: actual Blender detected a duplicate coplanar actor mesh, non-uniform scale,",flush=True)
    print("      alpha material and 128px source texture, WITHOUT changing render or art",flush=True)
    print("PASS: no dummy viewport generated in real Blender background mode",flush=True)
    print("NOT VERIFIED: Android GPU tearing resolved, facial detail created, native phone screen AA",flush=True)
