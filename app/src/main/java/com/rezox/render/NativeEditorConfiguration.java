package com.rezox.render;

import android.content.Context;
import android.util.AtomicFile;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/** Disk handoff also works when an ARM native bridge snapshots a separate environ. */
public final class NativeEditorConfiguration {
    private NativeEditorConfiguration() {}

    public static void publish(Context context) throws Exception {
        // The previous process's file is never launch-completion evidence.
        java.nio.file.Files.deleteIfExists(new File(context.getFilesDir(),"render_bpy_jobs/ready").toPath());
        String mode = context.getSharedPreferences("render_mobile_ui", Context.MODE_PRIVATE)
                .getString("mode", "portrait");
        if (!"portrait".equals(mode) && !"landscape".equals(mode)) mode = "portrait";
        JSONObject settings = new JSONObject().put("schema_version", 1)
                .put("target_package", context.getPackageName())
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
}
