package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class NativeBlenderUiStatusTest {
    @Test public void blenderReceivesActualProgressAndPersistentPauseReason()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        AgentWorkPresence.begin(c,"render.batch","Binder");
        AgentWorkPresence.stage(c,"Rendering frame 104",60);
        File path=new File(ProductionFiles.root(c),"native_ui_status.json");
        JSONObject progress=new JSONObject(new String(Files.readAllBytes(path.toPath()),StandardCharsets.UTF_8));
        assertEquals("running",progress.getString("state"));assertEquals(60,progress.getInt("progress"));
        assertEquals("Rendering animation",progress.getString("action"));
        AgentWorkPresence.finish(c,"succeeded",new JSONObject().put("paused",true)
            .put("reason","PAUSED_THERMAL_PRESSURE"));
        JSONObject paused=new JSONObject(new String(Files.readAllBytes(path.toPath()),StandardCharsets.UTF_8));
        assertEquals("paused",paused.getString("state"));
        assertEquals("Waiting for Android to cool",paused.getString("stage"));
        assertFalse(paused.has("device_token"));assertFalse(paused.has("device_id"));
    }
    @Test public void diagnosticWriteCannotFollowSymlinkOrAbortCommand()throws Exception{
        Context c=RuntimeEnvironment.getApplication();File outside=File.createTempFile("ui-status-outside",".json");
        File link=new File(ProductionFiles.root(c),"native_ui_status.json");Files.deleteIfExists(link.toPath());
        try{
            Files.write(outside.toPath(),"preserved".getBytes(StandardCharsets.UTF_8));Files.createSymbolicLink(link.toPath(),outside.toPath());
            AgentWorkPresence.begin(c,"render.batch","Binder");
            assertEquals("preserved",new String(Files.readAllBytes(outside.toPath()),StandardCharsets.UTF_8));
            assertTrue(AgentWorkPresence.snapshot(c).isWorking());
        }finally{Files.deleteIfExists(link.toPath());outside.delete();}
    }
}
