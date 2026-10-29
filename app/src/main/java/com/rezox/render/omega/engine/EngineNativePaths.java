package com.rezox.render.omega.engine;

import android.content.Context;
import android.os.Environment;
import android.os.Looper;
import android.system.Os;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;

/** Prepare storage before NativeActivity receives input/focus events. */
public final class EngineNativePaths {
    private EngineNativePaths() {}

    /** A path lookup only: native code opens the already prepared private log. */
    public static String logPath(Context context) {
        return new File(context.getFilesDir(), "blender-startup.log").getAbsolutePath();
    }

    public static void prepare(Context context) throws IOException {
        if (Looper.myLooper() == Looper.getMainLooper())
            throw new IllegalStateException("NATIVE_STORAGE_PREPARATION_REQUIRES_BACKGROUND_THREAD");
        File log = new File(logPath(context));
        // Keep the immediately preceding startup failure for diagnostics.
        if (log.isFile() && log.length() > 0)
            Files.move(log.toPath(), new File(log.getParentFile(), "blender-startup.previous.log").toPath(),
                    StandardCopyOption.REPLACE_EXISTING);
        try (FileOutputStream probe = new FileOutputStream(log, true)) {
            probe.getFD().sync();
        }
        context.getSharedPreferences("render_editor_launch", Context.MODE_PRIVATE).edit()
                .putString("native_log_path", log.getAbsolutePath()).apply();

        // Keep an existing native/artist override. This affects only Blender's
        // factory /tmp fallback, never scene output paths or frozen render jobs.
        String existing = Os.getenv("BLENDER_ANDROID_OUTPUT_DIR");
        if (existing != null && !existing.isEmpty()) return;
        File external = context.getExternalFilesDir(null);
        File[] parents = {
                Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
                Environment.getExternalStorageDirectory(), external, context.getFilesDir()};
        for (File parent : parents) {
            if (parent == null) continue;
            File directory = new File(parent, "Blender");
            File probe = null;
            try {
                if (!directory.isDirectory() && !directory.mkdirs()) continue;
                // Never truncate an artist's existing file as a writability test.
                probe = File.createTempFile(".render-write-", ".probe", directory);
                try (FileOutputStream stream = new FileOutputStream(probe)) {
                    stream.getFD().sync();
                }
                Os.setenv("BLENDER_ANDROID_OUTPUT_DIR", directory.getAbsolutePath(), true);
                context.getSharedPreferences("render_editor_launch", Context.MODE_PRIVATE).edit()
                        .putString("native_output_path", directory.getAbsolutePath()).apply();
                return;
            } catch (Exception unavailable) {
                // Scoped storage may deny the public destination. Try the next
                // existing default; explicit native Blender paths are unchanged.
            } finally {
                if (probe != null && probe.exists()) probe.delete();
            }
        }
        throw new IOException("NO_WRITABLE_NATIVE_RENDER_DIRECTORY");
    }
}
