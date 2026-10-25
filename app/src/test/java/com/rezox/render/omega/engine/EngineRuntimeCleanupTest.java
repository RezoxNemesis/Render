package com.rezox.render.omega.engine;

import java.io.File;
import java.nio.file.Files;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import static org.junit.Assert.*;

public class EngineRuntimeCleanupTest {
    @Rule public TemporaryFolder temp = new TemporaryFolder();

    @Test public void obsoleteApkPythonLinkDoesNotStrandPreviousRuntime() throws Exception {
        File previous = temp.newFolder("5.3.previous");
        File bin = new File(previous,"python/bin");
        assertTrue(bin.mkdirs());
        File shortcut = new File(bin,"python3.13");
        Files.createSymbolicLink(shortcut.toPath(),new File(temp.getRoot(),"removed-apk/libpython.so").toPath());
        assertFalse(shortcut.exists());
        assertTrue(Files.isSymbolicLink(shortcut.toPath()));
        EngineRuntimeCleanup.remove(previous);
        assertFalse(previous.exists());
    }

    @Test public void cleanupUnlinksDirectoryShortcutAndPreservesItsTarget() throws Exception {
        File outside = temp.newFolder("Production");
        File project = new File(outside,"owner-project.blend");
        Files.write(project.toPath(),new byte[]{4,8,15,16,23,42});
        File stage = temp.newFolder("5.3.prepare");
        Files.createSymbolicLink(new File(stage,"shortcut").toPath(),outside.toPath());
        EngineRuntimeCleanup.remove(stage);
        assertFalse(stage.exists());
        assertArrayEquals(new byte[]{4,8,15,16,23,42},Files.readAllBytes(project.toPath()));
    }

    @Test public void missingTreeAndDanglingRootAreBothSafe() throws Exception {
        File link = new File(temp.getRoot(),"5.3.prepare");
        EngineRuntimeCleanup.remove(link);
        Files.createSymbolicLink(link.toPath(),new File(temp.getRoot(),"removed-runtime").toPath());
        EngineRuntimeCleanup.remove(link);
        assertFalse(Files.isSymbolicLink(link.toPath()));
    }
}
