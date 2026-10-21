# SPDX-License-Identifier: GPL-2.0-or-later
"""Smoke test typed Render commands with the REAL Blender bpy interpreter.

Runs on a temporary Linux CI runner solely to validate bpy semantics. The
Android app uses the identical startup timer with its native Blender build.
"""
import json
import os
from pathlib import Path
import runpy
import tempfile
import time

import bpy

def main():
    bpy.ops.wm.read_factory_settings(use_empty=False)
    with tempfile.TemporaryDirectory(prefix="render-real-bpy-") as sandbox:
        root=Path(sandbox)/"render_bpy_jobs"
        root.mkdir()
        os.environ["RENDER_AGENT_SPOOL"]=str(root)
        code=runpy.run_path("full-app/scripts/render_agent_startup.py")
        execute=code["_poll"]
        uid="2b30a4d1b87947fe9f7e61c3940bca65"
        pending=root/"pending"
        result_dir=root/"results"
        def submit(action, args):
            (pending/(uid+".json")).write_text(
                json.dumps({"id":uid,"action":action,"args":args,
                            "deadline":time.time()+20}), encoding="utf8")
            execute()
            result_path=result_dir/(uid+".json")
            assert result_path.is_file(), "Blender did not produce an outcome"
            result=json.loads(result_path.read_text(encoding="utf8"))
            result_path.unlink()
            return result
        execute() # establish spool and timer heartbeat directory
        assert (root/"ready").is_file(), "Blender timer did not publish readiness"

        status=submit("blender.scene.summary",{})
        assert status["state"]=="succeeded",status
        assert status["result"]["blender_version"]==bpy.app.version_string
        assert status["result"]["scene"]==bpy.context.scene.name
        before=len(bpy.context.scene.objects)

        created=submit("blender.object.add_cube",
                       {"name":"NativeRenderCube","location":[1,2,3],"size":2.5})
        assert created["state"]=="succeeded",created
        assert created["result"]["name"]=="NativeRenderCube"
        assert tuple(bpy.data.objects["NativeRenderCube"].location)==(1.0,2.0,3.0)
        assert len(bpy.context.scene.objects)==before+1


        frame_result=submit("blender.scene.set_frame",{"frame":12})
        assert frame_result["state"]=="succeeded",frame_result
        assert frame_result["result"]["frame"]==12,frame_result
        assert bpy.context.scene.frame_current==12

        transform=submit("blender.object.set_transform",{
            "name":"NativeRenderCube","location":[0.0,1.0,2.0],
            "rotation_euler":[0.0,0.0,0.5],"scale":[1.0,2.0,1.0],
        })
        assert transform["state"]=="succeeded",transform
        selected=bpy.context.scene.objects["NativeRenderCube"]
        assert tuple(selected.location)==(0.0,1.0,2.0)
        assert tuple(selected.scale)==(1.0,2.0,1.0)
        assert abs(selected.rotation_euler.z-0.5)<0.000001

        for frame,position in [(1,[0,0,0]),(24,[3,0,1])]:
            key=submit("blender.object.keyframe",{
                "name":"NativeRenderCube","data_path":"location",
                "frame":frame,"value":position,
            })
            assert key["state"]=="succeeded",key
            assert key["result"]["inserted"] is True
            assert key["result"]["frame"]==frame
        assert selected.animation_data is not None
        assert selected.animation_data.action is not None
        bpy.context.scene.frame_set(24)
        assert abs(selected.location.x-3.0)<0.0001
        assert abs(selected.location.z-1.0)<0.0001

        added=submit("blender.object.add_primitive",{
            "name":"RenderSphere","kind":"UV_SPHERE","size":1.4,"location":[2,0,0]})
        assert added["state"]=="succeeded",added
        assert added["result"]["vertices"]>100,added
        assert bpy.data.objects["RenderSphere"].type=="MESH"

        camera=submit("blender.object.add_camera",{
            "name":"RenderCam","location":[0,-6,3]})
        assert camera["state"]=="succeeded",camera
        assert bpy.context.scene.camera.name=="RenderCam"

        light=submit("blender.object.add_light",{
            "name":"RenderLamp","light_type":"AREA","energy":800.0,
            "location":[0,-2,4],"color":[1.0,0.8,0.6]})
        assert light["state"]=="succeeded",light
        assert bpy.data.objects["RenderLamp"].data.type=="AREA"

        modifier=submit("blender.object.modifier_add",{
            "name":"RenderSphere","modifier_type":"SUBSURF","levels":1})
        assert modifier["state"]=="succeeded",modifier
        assert modifier["result"]["modifier_count"]>=1

        material=submit("blender.material.assign",{
            "name":"RenderSphere","material_name":"RenderCopper",
            "color":[0.8,0.45,0.2],"metallic":0.6,"roughness":0.34})
        assert material["state"]=="succeeded",material
        assert len(bpy.data.objects["RenderSphere"].data.materials)>=1

        # Full native-operator batching: one genuine Blender call, three
        # independently editable coloured meshes, bevels and replay protection.
        architecture={"assembly":"ArchitecturalAccent","parts":[
            {"name":"StoneBeam","kind":"CUBE","location":[0,0,2],
             "scale":[3,.2,.3],"color":[.8,.7,.6],"roughness":.6,"bevel":.06},
            {"name":"BlueGlass","kind":"CUBE","location":[0,-1,1.4],
             "scale":[.5,.08,.8],"color":[.08,.2,.45],"metallic":.1},
            {"name":"TerraceColumn","kind":"CYLINDER","location":[2,0,1],
             "scale":[.3,.3,1],"color":[.62,.62,.62]}
        ]}
        assembled=submit("blender.scene.batch_assembly",architecture)
        assert assembled["state"]=="succeeded",assembled
        assert assembled["result"]["created_count"]==3
        assert assembled["result"]["material_count"]==3
        names=assembled["result"]["objects"]
        assert len(names)==3
        assert all(bpy.data.objects.get(name) is not None for name in names)
        assert all(bpy.data.objects[name].data.materials for name in names)
        replay=submit("blender.scene.batch_assembly",architecture)
        assert replay["state"]=="succeeded" and replay["result"]["already_complete"]
        assert len([c for c in bpy.context.scene.collection.children
                    if c.get("render_assembly_key")=="ArchitecturalAccent"])==1
        conflicting={"assembly":"ArchitecturalAccent","parts":[
            dict(architecture["parts"][0],color=[.2,.1,.1])
        ]}
        conflict=submit("blender.scene.batch_assembly",conflicting)
        assert conflict["state"]=="failed" and conflict["error"]=="ASSEMBLY_NAME_REVISION_CONFLICT"
        audit=submit("blender.scene.visual_audit",{})
        assert audit["state"]=="succeeded",audit
        assert audit["result"]["ready_for_lively_video"] is False
        assert not audit["result"]["checks"]["pedestrians"]
        assert audit["result"]["pbr_node_materials"]>=3

        configured=submit("blender.scene.render_settings",{
            "resolution_x":64,"resolution_y":64,"engine":"CYCLES","samples":2,
            "denoising":False})
        assert configured["state"]=="succeeded",configured
        assert bpy.context.scene.render.resolution_x==64
        assert bpy.context.scene.render.resolution_percentage==100
        assert bpy.context.view_layer.cycles.use_denoising is False

        invalid_mat=submit("blender.material.assign",{
            "name":"RenderSphere","color":[1,0,2]})
        assert invalid_mat["state"]=="failed"
        assert invalid_mat["error"]=="INVALID_MATERIAL_COLOR"

        # Genuine CPU Cycles still: verify actual Blender engine output, not
        # simply action registration or a fabricated file reference.
        still=submit("blender.scene.render_still",{})
        assert still["state"]=="succeeded",still
        report=still["result"]
        image=root.parent/"Renders"/report["filename"]
        assert image.is_file(),image
        assert image.read_bytes()[:8]==b"\x89PNG\r\n\x1a\n"
        assert report["bytes"]==image.stat().st_size
        assert report["sha256"]==__import__("hashlib").sha256(image.read_bytes()).hexdigest()
        assert report["engine"]=="CYCLES"
        assert report["resolution"]==[64,64]
        assert report["executed_by"]=="bpy-main-thread-on-android"

        invalid_key=submit("blender.object.keyframe",{
            "name":"NativeRenderCube","data_path":"__class__","frame":25,
            "value":[1,2,3]})
        assert invalid_key["state"]=="failed"
        assert invalid_key["error"]=="INVALID_KEYFRAME_PATH"

        missing=submit("blender.object.set_transform",{
            "name":"NotAnObject","location":[1,2,3]})
        assert missing["state"]=="failed"
        assert missing["error"]=="OBJECT_NOT_FOUND"

        bad_frame=submit("blender.scene.set_frame",{"frame":"24"})
        assert bad_frame["state"]=="failed"
        assert bad_frame["error"]=="INVALID_FRAME"

        invalid=submit("python.eval",{"source":"raise AssertionError('not authorized')"})
        assert invalid["state"]=="failed",invalid
        assert invalid["error"]=="NATIVE_BLENDER_ACTION_UNAVAILABLE"

        expired_uid="ee302d6bd55c4eaeac4a8d6e23a2b6c3"
        (pending/(expired_uid+".json")).write_text(json.dumps({
            "id":expired_uid,"action":"blender.object.add_cube",
            "args":{"name":"MustNotExist"},"deadline":time.time()-1,
        }),encoding="utf8")
        execute()
        expired=json.loads((result_dir/(expired_uid+".json")).read_text(encoding="utf8"))
        assert expired["state"]=="failed" and expired["error"]=="COMMAND_EXPIRED",expired
        assert "MustNotExist" not in bpy.data.objects

        saved=submit("blender.project.save_copy",{})
        assert saved["state"]=="succeeded",saved
        filename=saved["result"]["filename"]
        assert filename.startswith("Render_") and filename.endswith(".blend")
        snapshot=root.parent/"Projects"/filename
        assert snapshot.is_file(),snapshot
        assert saved["result"]["bytes"]==snapshot.stat().st_size
        assert snapshot.stat().st_size>256
        import hashlib
        with snapshot.open("rb") as source:
            digest=hashlib.sha256()
            for block in iter(lambda:source.read(65536), b""):
                digest.update(block)
        assert saved["result"]["sha256"]==digest.hexdigest()
        assert saved["result"]["copied_without_changing_open_project"] is True

        print("PASS: actual Blender 3D geometry, camera, materials, modifiers, animation, PNG render and .blend saving")

if __name__=="__main__":
    main()
