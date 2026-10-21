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
    with tempfile.TemporaryDirectory(prefix="render-real-bpy-") as root_string:
        root=Path(root_string)
        os.environ["RENDER_AGENT_SPOOL"]=root_string
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

        print("PASS: genuine Blender bpy scene introspection, cube creation, invalid action and expired job")

if __name__=="__main__":
    main()
