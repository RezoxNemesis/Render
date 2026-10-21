package com.rezox.render;

import com.rezox.render.agent.ProjectScope;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.zip.ZipFile;
import java.util.zip.ZipInputStream;
import org.junit.Test;
import static org.junit.Assert.*;

public final class ProjectBackupTest {
    @Test public void backupStreamsSavedProjectsAndManifest() throws Exception {
        File root=Files.createTempDirectory("render-backup-test").toFile();
        File a=new File(root,"scene.blend"),b=new File(root,"character.blend");
        Files.write(a.toPath(),"BLENDER-TEST-SCENE".getBytes());
        Files.write(b.toPath(),"BLENDER-TEST-CHARACTER".getBytes());
        ProjectScope scope=new ProjectScope(new File[]{root});
        ByteArrayOutputStream output=new ByteArrayOutputStream();
        ProjectBackup.Result report=ProjectBackup.export(scope.entries(),output);
        assertEquals(2,report.projects);
        int scanned=0;boolean manifest=false;
        try(ZipInputStream zip=new ZipInputStream(new java.io.ByteArrayInputStream(output.toByteArray()))){
            java.util.zip.ZipEntry member;
            while((member=zip.getNextEntry())!=null){
                if(member.getName().endsWith(".blend"))scanned++;
                if(member.getName().equals("render-backup-manifest.json")){
                    String data=new String(zip.readAllBytes());
                    assertTrue(data.contains("sha256"));
                    assertTrue(data.contains("externalDependenciesIncluded"));
                    manifest=true;
                }
            }
        }
        assertTrue(manifest);assertEquals(2,scanned);
    }
    @Test public void emptyProjectsDoNotProduceFalseBackup() throws Exception {
        ProjectScope scope=new ProjectScope(new File[]{Files.createTempDirectory("empty-blends").toFile()});
        try{ProjectBackup.export(scope.entries(),new ByteArrayOutputStream());fail();}
        catch(java.io.IOException expected){assertTrue(expected.getMessage().contains("No saved .blend"));}
    }
}
