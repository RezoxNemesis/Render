"""Exact-source build integration for verified render isolation and native detail tools."""
from pathlib import Path

def apply(root):
    def patch(path,before,after):
        file=root/path;s=file.read_text()
        if after in s:return
        if s.count(before)!=1:raise RuntimeError('PRODUCTION_SOURCE_DRIFT: '+path+' '+repr(before[:80]))
        file.write_text(s.replace(before,after,1))
    runtime='full-app/scripts/render_production.py'
    patch(runtime,'def _step(root,p):', '''def _render_exact(scene, frame):
    # A render operator can inherit the active window frame despite scene=.
    window=bpy.context.window
    original=window.scene if window else None
    try:
        if window:window.scene=scene
        scene.frame_set(frame)
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            result=bpy.ops.render.render(write_still=True,scene=scene.name)
        if scene.frame_current!=frame:
            raise RuntimeError('RENDER_FRAME_CONTEXT_MISMATCH')
        return result
    finally:
        if window and original is not None:window.scene=original

def _step(root,p):''')
    patch(runtime,'result=bpy.ops.render.render(write_still=True,scene=scene.name)\n        if \'FINISHED\' not in result or not tmp.is_file()',
          'result=_render_exact(scene,frame)\n        if \'FINISHED\' not in result or not tmp.is_file()')
    patch(runtime,"    elif hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_render_samples'):scene.eevee.taa_render_samples=spec['samples']",
          "    elif hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_render_samples'):scene.eevee.taa_render_samples=spec['samples']\n    elif hasattr(scene,'eevee') and hasattr(scene.eevee,'taa_samples'):scene.eevee.taa_samples=spec['samples']\n    else:raise ValueError('REQUESTED_SAMPLE_CONTROL_UNAVAILABLE')")
    patch(runtime,"    spec=C.render_spec(p)\n    if scene.camera is None:",
          "    spec=C.render_spec(p)\n    unpacked=[image for image in bpy.data.images if image.source=='FILE' and not image.packed_file]\n    if unpacked:raise ValueError('PACK_EXTERNAL_IMAGES_BEFORE_CHECKPOINT')\n    if scene.camera is None:")
    detail="'project.list','project.restore','mesh.edit','curve.create','shape.create','shape.keys','rig.create','rig.bind','rig.keys'"
    patch(runtime,"    if operation=='scene.inspect':",'''    if operation in ('''+detail+'''):
        detail_path=Path(__file__).with_name('render_production_detail.py')
        detail_spec=importlib.util.spec_from_file_location('render_production_detail',detail_path)
        detail_module=importlib.util.module_from_spec(detail_spec)
        detail_spec.loader.exec_module(detail_module)
        return detail_module.execute(operation,p,root,scene,C)
    if operation=='scene.inspect':''')
    patch('full-app/scripts/render_production_contract.py',
          "    'project.create', 'project.checkpoint', 'scene.inspect', 'mesh.create',",
          "    'project.create', 'project.checkpoint', 'scene.inspect', 'mesh.create',\n    "+detail+",")
    patch('app/src/main/java/com/rezox/render/agent/ProductionBridge.java',
          '"project.create","project.checkpoint",',
          '"project.create","project.checkpoint","project.list","project.restore","mesh.edit","curve.create","shape.create","shape.keys","rig.create","rig.bind","rig.keys",')
    patch('tools/assemble_full_native.py',
          'for name in ("render_production.py", "render_production_contract.py"):',
          'for name in ("render_production.py", "render_production_contract.py", "render_production_detail.py"):')
    patch(runtime,"return dict(C.file_receipt(file),category='Projects',source_unchanged=True)",
          "return dict(C.file_receipt(file),category='Projects',scene=scene.name,source_unchanged=True)")
    patch('full-app/scripts/render_production_detail.py',
          'if ob.name in bpy.data.objects:ob.select_set(False)',
          'if name in bpy.data.objects:bpy.data.objects[name].select_set(False)')
    java='app/src/main/java/com/rezox/render/agent/ProductionVideoEncoder.java'
    patch(java,'try{fill(bitmap,image);}finally{image.close();}',
          'try{ProductionYuv.fill(bitmap,image);}finally{image.close();}')
    patch(java,'format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);',
          'format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);\n        format.setInteger(MediaFormat.KEY_COLOR_STANDARD,MediaFormat.COLOR_STANDARD_BT601_NTSC);\n        format.setInteger(MediaFormat.KEY_COLOR_RANGE,MediaFormat.COLOR_RANGE_LIMITED);')
