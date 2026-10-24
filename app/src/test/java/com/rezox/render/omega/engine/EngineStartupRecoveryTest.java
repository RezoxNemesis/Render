package com.rezox.render.omega.engine;

import android.content.Context;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.file.Files;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class EngineStartupRecoveryTest {
    @Test public void processRestorationAfterInterruptedStartupWaitsForAnExplicitRetry(){
        Context c=RuntimeEnvironment.getApplication();
        assertTrue(EngineStartupRecovery.allowAutomaticStart(c,null));
        EngineStartupRecovery.markPending(c);
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,null));
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,"restored-unrecognized-request"));
    }
    @Test public void restoredIntentCannotReplayAConsumedExplicitLaunch(){
        Context c=RuntimeEnvironment.getApplication();
        String first=EngineStartupRecovery.request(c);
        assertTrue(EngineStartupRecovery.allowAutomaticStart(c,first));
        EngineStartupRecovery.markPending(c);
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,first));
        String second=EngineStartupRecovery.request(c);
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,first));
        assertTrue(EngineStartupRecovery.allowAutomaticStart(c,second));
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,second));
    }
    @Test public void ownerOrAuthenticatedAgentCanExplicitlyRetryAfterFailure(){
        Context c=RuntimeEnvironment.getApplication();
        EngineStartupRecovery.markPending(c);
        String retry=EngineStartupRecovery.request(c);
        assertTrue(EngineStartupRecovery.allowAutomaticStart(c,retry));
        EngineStartupRecovery.markPending(c);
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,retry));
    }
    @Test public void actualReadinessClearsTheGateWithoutChangingProjectData()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        File project=new File(c.getFilesDir(),"saved-project.blend");
        byte[] original=new byte[]{66,76,69,78,68,69,82};Files.write(project.toPath(),original);
        EngineStartupRecovery.markPending(c);
        assertFalse(EngineStartupRecovery.allowAutomaticStart(c,null));
        EngineStartupRecovery.markReady(c);
        assertTrue(EngineStartupRecovery.allowAutomaticStart(c,null));
        assertArrayEquals(original,Files.readAllBytes(project.toPath()));
    }
}
