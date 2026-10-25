package com.rezox.render.omega.engine;

import android.content.Context;
import android.os.Looper;
import android.system.Os;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.FutureTask;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ConcurrentHashMap;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.LooperMode;
import org.robolectric.annotation.Implementation;
import org.robolectric.annotation.Implements;
import org.robolectric.annotation.Resetter;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE,shadows=EngineNativePathsTest.EnvironmentOs.class)
@LooperMode(LooperMode.Mode.PAUSED)
public class EngineNativePathsTest {
    /** Robolectric's Os environment functions are no-ops; model just those calls. */
    @Implements(Os.class)
    public static class EnvironmentOs {
        private static final ConcurrentHashMap<String,String> variables=new ConcurrentHashMap<>();
        @Implementation protected static String getenv(String name){return variables.get(name);}
        @Implementation protected static void setenv(String name,String value,boolean overwrite){
            if(overwrite)variables.put(name,value);else variables.putIfAbsent(name,value);
        }
        @Implementation protected static void unsetenv(String name){variables.remove(name);}
        @Resetter public static void reset(){variables.clear();}
    }
    private static void write(File file,String value) throws Exception {
        Files.write(file.toPath(),value.getBytes(StandardCharsets.UTF_8));
    }
    private static String read(File file) throws Exception {
        return new String(Files.readAllBytes(file.toPath()),StandardCharsets.UTF_8);
    }
    @Test public void mainThreadRefusalDoesNotRotateOrTruncateExistingLog() throws Exception {
        Context app=RuntimeEnvironment.getApplication();
        File log=new File(EngineNativePaths.logPath(app));
        write(log,"previous startup evidence");
        File previous=new File(log.getParentFile(),"blender-startup.previous.log");
        write(previous,"older startup evidence");
        assertSame(Looper.getMainLooper(),Looper.myLooper());
        try {
            EngineNativePaths.prepare(app);
            fail("Storage preparation must refuse to run on the UI thread");
        } catch (IllegalStateException expected) {
            assertEquals("NATIVE_STORAGE_PREPARATION_REQUIRES_BACKGROUND_THREAD",expected.getMessage());
        }
        assertEquals("previous startup evidence",read(log));
        assertEquals("older startup evidence",read(previous));
    }

    @Test public void backgroundPreparationRetainsFailureAndArtistOutputOverride() throws Exception {
        Context app=RuntimeEnvironment.getApplication();
        File log=new File(EngineNativePaths.logPath(app));
        File output=new File(app.getFilesDir(),"OwnerOutput");assertTrue(output.isDirectory()||output.mkdirs());
        File retained=new File(output,"keep-existing-output.txt");
        write(retained,"artist data must remain unchanged");
        write(log,"failure from the preceding native launch");
        String original=Os.getenv("BLENDER_ANDROID_OUTPUT_DIR");
        try {
            Os.setenv("BLENDER_ANDROID_OUTPUT_DIR",output.getAbsolutePath(),true);
            FutureTask<Void> prepared=new FutureTask<>(()->{EngineNativePaths.prepare(app);return null;});
            new Thread(prepared,"native-storage-test").start();prepared.get(15,TimeUnit.SECONDS);
            assertEquals(output.getAbsolutePath(),Os.getenv("BLENDER_ANDROID_OUTPUT_DIR"));
            assertEquals("artist data must remain unchanged",read(retained));
            assertEquals("failure from the preceding native launch",read(
                    new File(log.getParentFile(),"blender-startup.previous.log")));
            assertEquals(0,log.length());
            assertEquals(log.getAbsolutePath(),app.getSharedPreferences("render_editor_launch",0)
                    .getString("native_log_path",""));
        } finally {
            if(original==null)Os.unsetenv("BLENDER_ANDROID_OUTPUT_DIR");
            else Os.setenv("BLENDER_ANDROID_OUTPUT_DIR",original,true);
        }
    }
}
