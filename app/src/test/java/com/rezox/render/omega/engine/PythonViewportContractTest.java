package com.rezox.render.omega.engine;

import org.junit.Test;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.util.concurrent.TimeUnit;
import static org.junit.Assert.*;

/**
 * Verifies the exact committed Python viewport module in the same JVM CI
 * workflow that tests the Android bridge. Does not execute arbitrary user code
 * in the shipped app and does not imply on-device Vulkan has been tested.
 */
public class PythonViewportContractTest {
    @Test public void typedBpyViewportContractRunsWithoutAndroidGui()throws Exception{
        File root=new File(System.getProperty("user.dir",".")).getCanonicalFile();
        for(int i=0;i<6;i++){
            if(new File(root,"tools/omega/test_phase01_contract.py").isFile())break;
            root=root.getParentFile();
            if(root==null)throw new AssertionError("RENDER_SOURCE_CHECKOUT_UNAVAILABLE");
        }
        assertTrue(new File(root,"tools/omega/test_phase01_contract.py").isFile());
        ProcessBuilder command=new ProcessBuilder("python3","-m","unittest",
            "discover","-s","tools/omega","-p","test_phase01_contract.py","-v");
        command.directory(root);command.redirectErrorStream(true);
        Process process=command.start();
        boolean finished=process.waitFor(30,TimeUnit.SECONDS);
        if(!finished){process.destroyForcibly();fail("P01_PYTHON_CONTRACT_TIMEOUT");}
        ByteArrayOutputStream output=new ByteArrayOutputStream();
        try(InputStream input=process.getInputStream()){
            byte[] bytes=new byte[4096];int n;
            while((n=input.read(bytes))!=-1)output.write(bytes,0,n);
        }
        assertEquals("Real Phase 1 viewport contract failed:\n"+output,0,process.exitValue());
        assertTrue(output.toString().contains("Ran 4 tests"));
    }
}
