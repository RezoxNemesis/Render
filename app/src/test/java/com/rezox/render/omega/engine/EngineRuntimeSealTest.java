package com.rezox.render.omega.engine;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import static org.junit.Assert.*;

public class EngineRuntimeSealTest {
    @Rule public TemporaryFolder temp=new TemporaryFolder();
    private static File makeInstalled(File root)throws Exception{
        File dir=new File(root,"scripts/startup");
        assertTrue(dir.mkdirs());
        Files.writeString(new File(dir,"render_agent_startup.py").toPath(),"import bpy");
        return root;
    }
    @Test public void sameArchiveAcrossApkUpdatesDoesNotRequireExtraction()throws Exception{
        File root=makeInstalled(temp.newFolder("engine"));
        byte[] zip="same real Blender archive bytes".getBytes(StandardCharsets.UTF_8);
        String hash=EngineRuntimeSeal.archiveSha256(new ByteArrayInputStream(zip));
        EngineRuntimeSeal.writeSeal(root,"5.3","apk-1",hash);
        assertTrue(EngineRuntimeSeal.hasSamePackageStamp(root,"5.3","apk-1"));
        assertFalse(EngineRuntimeSeal.hasSamePackageStamp(root,"5.3","apk-2"));
        assertTrue(EngineRuntimeSeal.sameArchive(root,"5.3",hash));
        // Simulated installed project is NOT in the runtime resource directory.
        File project=temp.newFile("current-production-project.blend");
        byte[] original=new byte[]{4,8,15,16,23,42};
        Files.write(project.toPath(),original);
        EngineRuntimeSeal.refreshPackageStamp(root,"5.3","apk-2",hash);
        assertTrue(EngineRuntimeSeal.hasSamePackageStamp(root,"5.3","apk-2"));
        assertArrayEquals(original,Files.readAllBytes(project.toPath()));
        assertEquals("import bpy",Files.readString(
            new File(root,"scripts/startup/render_agent_startup.py").toPath()));
    }
    @Test public void changedArchiveAndLostStartupNeverCountAsReusable()throws Exception{
        File root=makeInstalled(temp.newFolder("engine-new"));
        String old=EngineRuntimeSeal.archiveSha256(new ByteArrayInputStream("a".getBytes()));
        String now=EngineRuntimeSeal.archiveSha256(new ByteArrayInputStream("b".getBytes()));
        EngineRuntimeSeal.writeSeal(root,"5.3","apk-1",old);
        assertNotEquals(old,now);
        assertFalse(EngineRuntimeSeal.sameArchive(root,"5.3",now));
        try{
            EngineRuntimeSeal.refreshPackageStamp(root,"5.3","apk-2",now);
            fail("Different Blender payload must not silently reuse old runtime");
        }catch(java.io.IOException expected){
            assertEquals("BLENDER_ASSET_REVISION_MISMATCH",expected.getMessage());
        }
        assertTrue(new File(root,"scripts/startup/render_agent_startup.py").delete());
        assertFalse(EngineRuntimeSeal.hasInstalledRuntime(root,"5.3"));
        assertFalse(EngineRuntimeSeal.hasSamePackageStamp(root,"5.3","apk-1"));
    }
    @Test public void badVersionAndMalformedDigestCannotCreateASeal()throws Exception{
        File root=temp.newFolder("engine-v");
        try{EngineRuntimeSeal.writeSeal(root,"../../outside","stamp","a".repeat(64));fail();}
        catch(IllegalArgumentException expected){}
        try{EngineRuntimeSeal.writeSeal(root,"5.3","stamp","not-a-hash");fail();}
        catch(java.io.IOException expected){}
        assertEquals(0,root.listFiles().length);
    }
}
