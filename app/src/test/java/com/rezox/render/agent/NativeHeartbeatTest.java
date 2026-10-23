package com.rezox.render.agent;
import android.content.Context;
import android.os.Process;
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
public class NativeHeartbeatTest {
    @Test public void freshFileFromPreviousProcessCannotClaimEditorReadiness()throws Exception{
        Context app=RuntimeEnvironment.getApplication();File file=new File(app.getFilesDir(),"render_bpy_jobs/ready");
        file.getParentFile().mkdirs();
        try{
            for(String invalid:new String[]{"",Integer.toString(Process.myPid()+1),"invalid"}){
                Files.write(file.toPath(),invalid.getBytes(StandardCharsets.US_ASCII));
                assertFalse(NativeHeartbeat.ready(app));
                assertFalse(NativeHeartbeat.observedCurrentProcess(app));
            }
            Files.write(file.toPath(),Integer.toString(Process.myPid()).getBytes(StandardCharsets.US_ASCII));
            assertTrue(NativeHeartbeat.ready(app));
            file.setLastModified(System.currentTimeMillis()-20000);assertFalse(NativeHeartbeat.ready(app));
            assertTrue(NativeHeartbeat.observedCurrentProcess(app));
        }finally{Files.deleteIfExists(file.toPath());}
    }
}
