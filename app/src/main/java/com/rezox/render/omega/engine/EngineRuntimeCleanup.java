package com.rezox.render.omega.engine;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;

/** Deletes only a launcher's replaceable runtime tree; never follows links. */
public final class EngineRuntimeCleanup {
    private EngineRuntimeCleanup() {}

    public static void remove(File path) throws IOException {
        // File.exists follows the target. An APK upgrade can leave the native
        // Python shortcut dangling after Android removes the old APK directory.
        // Unlink it before testing existence, or its parent stays non-empty.
        if (Files.isSymbolicLink(path.toPath())) {
            Files.delete(path.toPath());
            return;
        }
        if (!path.exists()) return;
        if (path.isDirectory()) {
            File[] children = path.listFiles();
            if (children == null) throw new IOException("CANNOT_LIST_RUNTIME_CLEANUP");
            for (File child : children) remove(child);
        }
        Files.delete(path.toPath());
    }
}
