package com.rezox.render.omega.engine;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class EngineEvidenceTest {
    @Test public void realStartupStagesAreBoundedAndNeverClaimPixels()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        context.getSharedPreferences(EngineEvidence.PREF,Context.MODE_PRIVATE)
            .edit().clear().commit();
        EngineEvidence.record(context,EngineEvidence.Stage.PREFLIGHT_ACCEPTED);
        EngineEvidence.record(context,EngineEvidence.Stage.NATIVE_LIBRARY_LOADED);
        EngineEvidence.record(context,EngineEvidence.Stage.EDITOR_ACTIVITY_REQUESTED);
        JSONObject status=EngineEvidence.snapshot(context);
        assertFalse(status.getBoolean("native_vulkan_frame_observed"));
        assertFalse(status.getBoolean("activity_launch_is_frame_proof"));
        assertFalse(status.getBoolean("quality_reduced"));
        assertNotNull(status.getJSONObject("vulkan"));
        JSONArray events=status.getJSONArray("events");
        assertEquals(3,events.length());
        assertEquals("EDITOR_ACTIVITY_REQUESTED",
            events.getJSONObject(events.length()-1).getString("stage"));
        assertTrue(EngineEvidence.text(context).contains("Native frame actually verified: NO"));
        assertFalse(status.toString().contains("token"));
        for(int i=0;i<42;i++)
            EngineEvidence.record(context,EngineEvidence.Stage.RUNTIME_CACHE_REUSED);
        assertEquals(24,EngineEvidence.events(context).length());
        assertEquals("RUNTIME_CACHE_REUSED",EngineEvidence.events(context)
            .getJSONObject(23).getString("stage"));
    }
    @Test public void evidenceDoesNotMutateAppProjects()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        java.io.File project=new java.io.File(context.getFilesDir(),
            "Production/Projects/P01-test.blend");
        assertTrue(project.getParentFile().isDirectory()||
            project.getParentFile().mkdirs());
        byte[] original=new byte[]{66,76,69,78,68,69,82,0,1};
        java.nio.file.Files.write(project.toPath(),original);
        try{
            EngineEvidence.record(context,EngineEvidence.Stage.NATIVE_CONTROLS_ATTACHED);
            EngineEvidence.snapshot(context);
            assertArrayEquals(original,java.nio.file.Files.readAllBytes(project.toPath()));
        }finally{project.delete();}
    }
}
