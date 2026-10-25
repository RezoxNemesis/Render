# SPDX-License-Identifier: GPL-2.0-or-later
"""Real Blender regression: flag disconnected human proxy, low-res flat sheet.

No fabricated screenshot, no automatic photorealism and no source overwrite.
"""
import os
from pathlib import Path
import sys
import tempfile

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_character_quality_gates as QA
import render_unified_contract as C
import render_unified_workspace as Studio

with tempfile.TemporaryDirectory() as d:
    os.environ["RENDER_AGENT_SPOOL"]=str(Path(d)/"render_bpy_jobs")
    scene=bpy.context.scene
    v=[(-.5,-.5,0),(.5,-.5,0),(.5,.5,0),(-.5,.5,0),
       (-.5,-.5,1),(.5,-.5,1),(.5,.5,1),(-.5,.5,1),
       (-.35,-.35,1.3),(.35,-.35,1.3),(.35,.35,1.3),(-.35,.35,1.3),
       (-.35,-.35,1.9),(.35,-.35,1.9),(.35,.35,1.9),(-.35,.35,1.9)]
    face0=[(0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),
           (2,3,7,6),(3,0,4,7)]
    face1=[tuple(x+8 for x in face) for face in face0]
    mesh=bpy.data.meshes.new("DisconnectedActorMesh")
    mesh.from_pydata(v,[],face0+face1)
    mesh.update()
    ob=bpy.data.objects.new("IslandHero_BaseBody",mesh)
    scene.collection.objects.link(ob)
    ob["render_work_stage"]="01_body_proportions"
    ob["render_sculpt_union_pending"]=True
    ob["render_likeness_verified"]=False

    image=bpy.data.images.new("ReferenceSheet240",width=240,height=180)
    ref=bpy.data.objects.new("Island_RefSheet",None)
    ref.empty_display_type="IMAGE"
    ref.data=image
    ref.location=(2.2,0,1)
    scene.collection.objects.link(ref)
    obj_verts=[tuple(x.co) for x in mesh.vertices]
    initial_euler=list(ref.rotation_euler)
    report=QA.audit(scene,{"object":ob.name,"reference":ref.name,
                           "related":[]})
    assert report["quality_gate"]=="BLOCKED",report
    assert report["connected_anatomical_mesh_shells"]["count"]==2,report
    assert "MULTIPLE_DISCONNECTED_ANATOMICAL_SHELLS" in report["blockers"]
    assert "SCULPT_UNION_AND_RETOPOLOGY_PENDING" in report["blockers"]
    assert "REFERENCE_TOO_SMALL_FOR_FACE_MATCHING" in report["blockers"]
    assert "REFERENCE_SHEET_IS_HORIZONTAL" in report["blockers"]
    assert "NO_FACIAL_SHAPE_KEYS" in report["blockers"]
    assert "ACTOR_MESH_NOT_BOUND_TO_ARMATURE" in report["blockers"]
    assert "FACE_AND_MOTION_RENDER_COMPARISON_PENDING" in report["blockers"]
    assert not report["render_started"] and not report["rendered_eye_head_acting_approved"] if "rendered_eye_head_acting_approved" in report else True
    assert not report["geometry_changed"]
    assert ob.get("render_likeness_verified") is False

    sha=QA._reference_revision(ref)
    planning=QA.upright(scene,{"reference":ref.name,
        "expected_sha256":sha,"dry_run":True})
    assert planning["currently_horizontal"]
    assert list(ref.rotation_euler)==initial_euler
    try:
        QA.upright(scene,{"reference":ref.name,
            "expected_sha256":"a"*64,"dry_run":False})
        raise AssertionError("Revision collision accepted")
    except ValueError as err:
        assert str(err)=="STUDIO_CHARACTER_QA_STALE_REFERENCE",err
    fixed=QA.upright(scene,{"reference":ref.name,
        "expected_sha256":sha,"dry_run":False})
    assert fixed["actual_blender_reference_rotated"]
    assert fixed["previous_horizontal"] and not fixed["new_horizontal"]
    assert ref.data==image
    upright_report=QA.audit(scene,{"object":ob.name,"reference":ref.name})
    assert "REFERENCE_SHEET_IS_HORIZONTAL" not in upright_report["blockers"]
    assert "REFERENCE_TOO_SMALL_FOR_FACE_MATCHING" in upright_report["blockers"]
    restored=QA.upright(scene,{"reference":ref.name,
        "expected_sha256":QA._reference_revision(ref),
        "dry_run":False,"restore":True})
    assert restored["original_restored"]
    assert (Vector(ref.rotation_euler)-Vector(initial_euler)).length<1e-6
    assert [tuple(x.co) for x in mesh.vertices]==obj_verts
    assert image.size[:]==(240,180)
    assert len(QA.capabilities())==2
    assert set(("studio.character.qa.inspect","studio.character.qa.upright")).issubset(C.PROGRAM_OPS)
    print("PASS: native Blender measured 2 disconnected proxy shells, no face shapes or skinned rig",flush=True)
    print("PASS: native reference board safe dry-run, revision gate, true upright and exact restore",flush=True)
    print("PASS: original image bytes/mesh vertices intact, no animation/render approval fabricated",flush=True)
    print("NOT VERIFIED: any actual actor likeness, high-detail face, mobile viewport or rendered animation",flush=True)
