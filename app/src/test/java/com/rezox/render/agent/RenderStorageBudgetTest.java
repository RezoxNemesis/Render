package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class RenderStorageBudgetTest {
    private JSONObject spec(int width,int height,int frames,int fps,int bitrate)throws Exception{
        return new JSONObject().put("width",width).put("height",height)
            .put("frame_count",frames).put("fps",fps).put("fps_base",1.0)
            .put("bitrate",bitrate);
    }
    @Test public void largeFrameSetUsesLongsAndNeverDowngrades()throws Exception{
        JSONObject result=RenderStorageBudget.estimate(
            spec(8192,8192,100000,24,160000000),24L*1024*1024*1024);
        assertTrue(result.getLong("nominal_uncompressed_animation_bytes")>10_000_000_000L);
        assertTrue(result.getLong("nominal_video_bytes")>10_000_000_000L);
        assertTrue(result.getLong("estimated_segment_count")>1);
        assertTrue(result.getBoolean("segmenting_required_for_reliability"));
        assertTrue(result.getBoolean("can_render_next_frame"));
        assertFalse(result.getBoolean("large_single_mp4_muxer_verified"));
        assertFalse(result.getBoolean("render_quality_reduced"));
    }
    @Test public void lowDiskPausesNextFrameWithoutChangingSettings()throws Exception{
        JSONObject spec=spec(3840,2160,6000,24,80000000);
        JSONObject low=RenderStorageBudget.estimate(spec,100L*1024*1024);
        assertFalse(low.getBoolean("can_render_next_frame"));
        JSONObject high=RenderStorageBudget.estimate(spec,25L*1024*1024*1024);
        assertTrue(high.getBoolean("can_render_next_frame"));
        assertEquals(3840,spec.getInt("width"));
        assertFalse(low.getBoolean("render_quality_reduced"));
        assertEquals(low.getLong("nominal_uncompressed_animation_bytes"),
            high.getLong("nominal_uncompressed_animation_bytes"));
    }
    @Test public void validatedJobScopeAndStatusSurviveApplicationRestart()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String job="9".repeat(32);
        File manifest=ProductionFiles.file(app,job,"manifest.json");
        try{
            JSONObject state=new JSONObject().put("job_id",job)
                .put("state","ready").put("fingerprint","fixture")
                .put("next_frame",142).put("frames",new JSONObject())
                .put("spec",spec(640,360,24,24,16000000)
                    .put("start",140).put("end",163));
            Files.write(manifest.toPath(),state.toString().getBytes(StandardCharsets.UTF_8));
            JSONObject plan=RenderStorageBudget.forJob(app,job);
            assertEquals(24,ProductionBatch.jobStatus(app,job).getInt("total_frames"));
            assertFalse(plan.getBoolean("render_quality_reduced"));
            assertTrue(plan.getLong("minimum_for_next_frame_bytes")>0);
        }finally{manifest.delete();}
    }
    @Test public void invalidSpecCannotOverflowOrLaunderUnsupportedDimensions()throws Exception{
        try{RenderStorageBudget.estimate(spec(8193,360,100,24,8000000),Long.MAX_VALUE);fail();}
        catch(IllegalArgumentException expected){}
        try{RenderStorageBudget.estimate(spec(8192,8192,100000,24,16000000),-1);fail();}
        catch(IllegalArgumentException expected){}
    }
}
