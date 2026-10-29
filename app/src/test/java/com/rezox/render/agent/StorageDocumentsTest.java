package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.file.Files;
import static org.junit.Assert.*;

/** Real app-workspace filesystem operations; provider behavior is verified separately. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class StorageDocumentsTest {
    @Test public void createsAndReusesNestedFoldersWithoutNeedingBlender()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        JSONObject first=StorageDocuments.createFolder(c,"workspace","root","Art Projects");
        String parent=first.getString("document_id");
        JSONObject again=StorageDocuments.createFolder(c,"workspace","root","Art Projects");
        assertEquals(parent,again.getString("document_id"));assertTrue(again.getBoolean("already_exists"));
        JSONObject child=StorageDocuments.createFolder(c,"workspace",parent,"Character 01");
        JSONObject listing=StorageDocuments.list(c,"workspace",parent,0,20);
        assertEquals(child.getString("document_id"),listing.getJSONArray("documents").getJSONObject(0).getString("document_id"));
        assertFalse(listing.getBoolean("gallery_browsed"));
    }
    @Test public void unsafeNamesAndUnknownHandlesCannotReachOtherStorage()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        for(String name:new String[]{"../secret","/storage","a/b","a\\b","..","", "\u0001bad"}){
            try{StorageDocuments.createFolder(c,"workspace","root",name);fail(name);}
            catch(IllegalArgumentException expected){}
        }
        try{StorageDocuments.list(c,"workspace","unregistered",0,20);fail();}
        catch(IllegalArgumentException expected){}
    }
    @Test public void workspaceSymlinkCannotEscapeTheAuthorizedLocation()throws Exception{
        Context c=RuntimeEnvironment.getApplication();File outside=Files.createTempDirectory("outside-storage").toFile();
        File link=new File(StorageDocuments.workspace(c),"escape");
        try{Files.createSymbolicLink(link.toPath(),outside.toPath());
            try{StorageDocuments.createFolder(c,"workspace","root","escape");fail();}
            catch(java.io.IOException expected){}
        }finally{Files.deleteIfExists(link.toPath());outside.delete();}
    }
}
