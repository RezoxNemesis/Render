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
    @Test public void creatorLaunchRequestIsConsumedOnceWithoutChangingMobileMode()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        app.getSharedPreferences("render_mobile_ui",Context.MODE_PRIVATE).edit()
            .putBoolean("creator_focus",true).putString("mode","landscape").commit();
        NativeEditorConfiguration.publish(app);
        File file=new File(app.getFilesDir(),"render_native_launch.json");
        JSONObject first=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        assertTrue(first.getBoolean("creator_focus"));
        assertEquals("landscape",first.getString("mobile_mode"));
        assertFalse(app.getSharedPreferences("render_mobile_ui",Context.MODE_PRIVATE)
            .getBoolean("creator_focus",false));
        NativeEditorConfiguration.publish(app);
        JSONObject second=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        assertFalse(second.getBoolean("creator_focus"));
        assertEquals("landscape",second.getString("mobile_mode"));
    }
    @Test public void animationLaunchIsConsumedOnceWithoutEnablingCreator()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        app.getSharedPreferences("render_mobile_ui",Context.MODE_PRIVATE).edit()
            .putBoolean("animation_focus",true).putBoolean("creator_focus",false).commit();
        NativeEditorConfiguration.publish(app);
        File file=new File(app.getFilesDir(),"render_native_launch.json");
        JSONObject first=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        assertTrue(first.getBoolean("animation_focus"));
        assertFalse(first.getBoolean("creator_focus"));
        NativeEditorConfiguration.publish(app);
        JSONObject second=new JSONObject(new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8));
        assertFalse(second.getBoolean("animation_focus"));
    }
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
