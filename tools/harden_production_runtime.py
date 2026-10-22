"""Additional exact-source build integration for verified render isolation."""
from pathlib import Path

def apply(root):
    def patch(path,before,after):
        file=root/path;s=file.read_text()
        if after in s:return
        if s.count(before)!=1:raise RuntimeError('PRODUCTION_SOURCE_DRIFT: '+path)
        file.write_text(s.replace(before,after,1))
    runtime='full-app/scripts/render_production.py'
    patch(runtime,'def _step(root,p):', '''def _render_exact(scene, frame):
    # Blender render operators can inherit the active window's frame even with
    # a different scene= argument. Explicitly switch context, then restore it.
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
