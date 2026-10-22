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
public class RenderResumeRegressionTest {
    @Test public void endFrameIsAbsoluteNotFrameCount()throws Exception{
        JSONObject state=new JSONObject().put("start_frame",101)
            .put("end_frame",105).put("total_frames",5).put("next_frame",101);
        assertFalse(ProductionBatch.framesComplete(state));
        state.put("next_frame",105);
        assertFalse(ProductionBatch.framesComplete(state));
        state.put("next_frame",106);
        assertTrue(ProductionBatch.framesComplete(state));
    }
    @Test public void pausedSnapshotPreservesNonOneStart()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String id="d".repeat(32);
        File manifest=ProductionFiles.file(app,id,"manifest.json");
        JSONObject m=new JSONObject().put("job_id",id).put("state","paused_error")
            .put("next_frame",104).put("fingerprint","test")
            .put("frames",new JSONObject().put("101",new JSONObject())
                .put("102",new JSONObject()).put("103",new JSONObject()))
            .put("spec",new JSONObject().put("start",101).put("end",105)
                .put("frame_count",5));
        try{
            Files.write(manifest.toPath(),m.toString().getBytes(StandardCharsets.UTF_8));
            JSONObject status=ProductionBatch.jobStatus(app,id);
            assertEquals(3,status.getInt("completed_frames"));
            assertEquals(101,status.getInt("start_frame"));
            assertEquals(105,status.getInt("end_frame"));
            assertEquals(104,status.getInt("next_frame"));
            assertFalse(ProductionBatch.framesComplete(status));
            assertEquals("paused_error",status.getString("state"));
        }finally{manifest.delete();}
    }
    @Test public void manualRunnerCannotClaimMissingOrExternalJob(){
        Context app=RuntimeEnvironment.getApplication();
        assertFalse(RenderManualJobs.start(app,"../../private"));
        assertFalse(RenderManualJobs.start(app,"a".repeat(32)));
    }
}
