package com.rezox.render.agent;
import org.junit.Test;
import org.junit.Rule;
import org.junit.rules.TemporaryFolder;
import java.io.File;
import java.nio.file.Files;
import static org.junit.Assert.*;
public class ProjectScopeTest {
    @Rule public TemporaryFolder temp=new TemporaryFolder();
    @Test public void onlyDirectBlendDocumentsAreVisible()throws Exception{
        File root=temp.newFolder("Projects");
        Files.write(new File(root,"scene.blend").toPath(),new byte[]{1});
        Files.write(new File(root,"private.txt").toPath(),new byte[]{1});
        File nested=new File(root,"nested");assertTrue(nested.mkdir());
        Files.write(new File(nested,"hidden.blend").toPath(),new byte[]{1});
        ProjectScope p=new ProjectScope(new File[]{root});
        assertEquals(1,p.entries().size());assertEquals("scene.blend",p.find(p.entries().get(0).id).getName());
    }
    @Test public void noPathTraversalAndNoSymlink()throws Exception{
        File root=temp.newFolder("Projects"),other=temp.newFile("outside.blend");
        Files.createSymbolicLink(new File(root,"escape.blend").toPath(),other.toPath());
        ProjectScope p=new ProjectScope(new File[]{root});assertTrue(p.entries().isEmpty());
        try{p.find("../outside.blend");fail();}catch(IllegalArgumentException expected){}
    }
    @Test public void sameBasenameInDifferentRootsHasDifferentId()throws Exception{
        File a=temp.newFolder("a"),b=temp.newFolder("b");
        Files.write(new File(a,"x.blend").toPath(),new byte[]{1});Files.write(new File(b,"x.blend").toPath(),new byte[]{2});
        ProjectScope p=new ProjectScope(new File[]{a,b});assertEquals(2,p.entries().size());
        assertNotEquals(p.entries().get(0).id,p.entries().get(1).id);
    }
}
