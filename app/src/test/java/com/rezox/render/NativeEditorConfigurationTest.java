package com.rezox.render;

import android.content.Context;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class NativeEditorConfigurationTest {
    @Test public void launchIdentityChangesOnlyOnPublicationAndDoesNotCreateReadiness()throws Exception{
        Context app=RuntimeEnvironment.getApplication();File file=new File(app.getFilesDir(),"render_native_launch.json");
        File ready=new File(app.getFilesDir(),"render_bpy_jobs/ready");ready.getParentFile().mkdirs();
        Files.write(ready.toPath(),"old-process".getBytes(StandardCharsets.US_ASCII));
        NativeEditorConfiguration.publish(app);
        JSONObject first=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        assertFalse(ready.exists());assertTrue(first.getString("native_activity_launch_id").matches("[a-f0-9-]{36}"));
        assertEquals(1,first.getInt("schema_version"));assertTrue(first.getBoolean("command_spool_enabled"));
        NativeEditorConfiguration.publish(app);
        JSONObject second=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        assertNotEquals(first.getString("native_activity_launch_id"),second.getString("native_activity_launch_id"));
        assertFalse(ready.exists());assertFalse(NativeEditorConfiguration.handlesAssetConfigurationChanges(app));
    }
}
