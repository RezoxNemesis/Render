# SPDX-License-Identifier: GPL-2.0-or-later
"""Actual Blender scene viewport sampling: opt-in, bounded and reversible.

Cycles.preview_samples is not Cycles.samples (final output). The feature
fails honestly if bundled Blender exposes no supported viewport sample knob.
"""
import os
from pathlib import Path
import sys
import tempfile
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"full-app/scripts"))
import render_viewport_fidelity as Preview

with tempfile.TemporaryDirectory() as scratch:
    os.environ["RENDER_AGENT_SPOOL"]=str(Path(scratch)/"bpy_jobs")
    scene=bpy.context.scene
    original_engine=scene.render.engine
    original_fps=scene.render.fps
    scene.render.engine="CYCLES"
    before_final=int(scene.cycles.samples)
    support=Preview.sampling_inspect(scene,{})
    if not support["native_preview_sample_setting_available"]:
        print("SKIP: Bundled Cycles has no native preview_samples control",flush=True)
    else:
        count=support["native_samples"]
        assert support["setting"]=="preview_samples",support
        desired=16 if count!=16 else 24
        first=Preview.sampling_configure(scene,{
            "allow_viewport_sample_change":True,"samples":desired})
        assert first["samples_after"]==desired
        assert int(scene.cycles.samples)==before_final
        assert Preview.sampling_inspect(scene,{})["native_samples"]==desired
        try:
            Preview.sampling_configure(scene,{
                "allow_viewport_sample_change":True,"samples":64})
            raise AssertionError("Allowed mobile-intensive samples without opt-in")
        except ValueError as err:
            assert "HIGH_SAMPLES_REQUIRES_OPT_IN" in str(err),err
        allowed=Preview.sampling_configure(scene,{
            "allow_viewport_sample_change":True,"allow_high_gpu_load":True,
            "samples":48})
        assert allowed["samples_after"]==48
        assert int(scene.cycles.samples)==before_final
        restored=Preview.sampling_configure(scene,{
            "allow_viewport_sample_change":True,"restore":True})
        assert restored["samples_after"]==count,restored
        assert restored["original_restored"]
        assert int(scene.cycles.samples)==before_final
        print("PASS: actual Cycles viewport samples changed and restored",count,"->",desired,flush=True)
        print("PASS: original Cycles final-render samples unchanged:",before_final,flush=True)
    scene.render.engine=original_engine
    assert scene.render.fps==original_fps
    print("NOT CLAIMED: Android viewport fps increase, GPU compatibility or face detail reconstruction",flush=True)
