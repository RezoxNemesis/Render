package com.rezox.render.omega.engine;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import static org.junit.Assert.*;

public class EngineStartupLogTest {
    @Rule public TemporaryFolder temp=new TemporaryFolder();
    private File log(String name,long time,String text)throws Exception{
        File file=temp.newFile(name);
        Files.write(file.toPath(),text.getBytes(StandardCharsets.UTF_8));
        assertTrue(file.setLastModified(time));return file;
    }
    @Test public void currentAppLogWinsOverAnOlderDownloadsFailure()throws Exception{
        File old=log("downloads.log",10000,"Old SwiftShader failure");
        File current=log("app.log",30000,"Current Lavapipe startup");
        EngineStartupLog.Selection result=EngineStartupLog.select(null,Arrays.asList(old,current),20000);
        assertEquals(current,result.file);assertTrue(result.current);
    }
    @Test public void activitySelectedLogWinsOverAnUnrelatedNewerLog()throws Exception{
        File current=log("app.log",30000,"Selected by NativeActivity");
        File other=log("downloads.log",40000,"Different launch");
        EngineStartupLog.Selection result=EngineStartupLog.select(current,Arrays.asList(other,current),20000);
        assertEquals(current,result.file);assertTrue(result.current);
    }
    @Test public void oldLogsAndUnrecordedLaunchesCannotCountAsCurrent()throws Exception{
        File old=log("old.log",10000,"Previous failure");
        assertFalse(EngineStartupLog.select(old,Arrays.asList(old),20000).current);
        assertFalse(EngineStartupLog.select(old,Arrays.asList(old),0).current);
    }
    @Test public void selectedPathCannotReadOutsideKnownLogLocations()throws Exception{
        File known=log("known.log",30000,"Blender startup");
        File unrelated=log("private-other-file",40000,"Not a startup log");
        EngineStartupLog.Selection result=EngineStartupLog.select(unrelated,Arrays.asList(known),20000);
        assertEquals(known,result.file);assertTrue(result.current);
    }
    @Test public void emptyAndDirectoryCandidatesDoNotProduceEvidence()throws Exception{
        File directory=temp.newFolder("not-log");
        EngineStartupLog.Selection result=EngineStartupLog.select(directory,Arrays.asList(directory),10000);
        assertNull(result.file);assertFalse(result.current);
    }
    @Test public void readsOnlyTheBoundedTailIncludingTheLatestFailure()throws Exception{
        File file=log("large.log",30000,"Old header\n"+"x".repeat(100000)+"\nLatest GPU failure\n");
        String text=EngineStartupLog.readTail(file,32000);
        assertTrue(text.endsWith("Latest GPU failure\n"));
        assertFalse(text.contains("Old header"));assertEquals(32000,text.length());
    }
}
