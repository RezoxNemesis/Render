package com.rezox.render;

import android.content.Context;
import android.util.AtomicFile;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/** Disk handoff also works when an ARM native bridge snapshots a separate environ. */
public final class NativeEditorConfiguration {
    private static final java.util.concurrent.atomic.AtomicInteger CONFIGURATIONS=new java.util.concurrent.atomic.AtomicInteger();
    private static volatile String launchId="";
    public static String launchId(){return launchId;}
    private NativeEditorConfiguration() {}

    public static void publish(Context context) throws Exception {
        // The previous process's file is never launch-completion evidence.
        java.nio.file.Files.deleteIfExists(new File(context.getFilesDir(),"render_bpy_jobs/ready").toPath());
        String mode = context.getSharedPreferences("render_mobile_ui", Context.MODE_PRIVATE)
                .getString("mode", "portrait");
        if (!"portrait".equals(mode) && !"landscape".equals(mode)) mode = "portrait";
        launchId=java.util.UUID.randomUUID().toString();
        JSONObject settings = new JSONObject().put("schema_version", 1)
                .put("target_package", context.getPackageName())
                .put("native_activity_launch_id", launchId)
                .put("command_spool_enabled", true).put("mobile_mode", mode);
        AtomicFile file = new AtomicFile(new File(context.getFilesDir(), "render_native_launch.json"));
        FileOutputStream out = file.startWrite();
        try {
            out.write(settings.toString().getBytes(StandardCharsets.UTF_8));
            file.finishWrite(out);
        } catch (Exception error) {
            file.failWrite(out);
            throw error;
        }
    }

    public static boolean handlesAssetConfigurationChanges(Context context) {
        try {
            android.content.pm.ActivityInfo info=context.getPackageManager().getActivityInfo(
                new android.content.ComponentName(context.getPackageName(),"org.blender.blender.BlenderActivity"),0);
            return (info.configChanges & 0x80000000)!=0;
        }catch(android.content.pm.PackageManager.NameNotFoundException missing){return false;}
    }

    /** Called only by the actual Android NativeActivity configuration callback. */
    public static void configurationChanged(Context context) {
        context.getSharedPreferences("render_editor_launch",Context.MODE_PRIVATE).edit()
            .putInt("native_configuration_pid",android.os.Process.myPid())
            .putInt("native_configuration_count",CONFIGURATIONS.incrementAndGet())
            .putLong("native_configuration_at_ms",System.currentTimeMillis()).apply();
    }
}
