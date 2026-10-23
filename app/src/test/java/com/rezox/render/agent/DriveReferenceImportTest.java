package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class DriveReferenceImportTest {
    private static JSONObject request(String name,String sha)throws Exception {
        return new JSONObject().put("files",new JSONArray().put(
            new JSONObject().put("filename",name).put("expected_sha256",sha)));
    }
    private static final String HASH="b2fb9103f8d451c1e5a6aebacb9b0c7e44e74c6c6f85f675226e413a705cf585";

    @Test public void onlyBasenamesAndSupportedImageExtensionsAreAllowed(){
        assertTrue(DriveReferenceImport.safeName("01_Ren_Front_Sides_Back.png"));
        assertTrue(DriveReferenceImport.safeName("05_Sakura_Duel_Environment.jpg"));
        for(String name:new String[]{"../secret.png","dir/image.png","C:\\secret.png",
                "evil..png","character.blend","reference.svg",".hidden.jpg",
                "overlong"+ "a".repeat(150) +".png"}) {
            assertFalse(name,DriveReferenceImport.safeName(name));
        }
    }
    @Test public void detectActualEncodingNotMislabeledFileExtension(){
        assertEquals("jpg",DriveReferenceImport.detectImageExt(
            new byte[]{(byte)0xff,(byte)0xd8,(byte)0xff,(byte)0xe0,0,0,0,0}));
        assertEquals("png",DriveReferenceImport.detectImageExt(
            new byte[]{(byte)0x89,80,78,71,13,10,26,10}));
        try{
            DriveReferenceImport.detectImageExt(new byte[]{'B','L','E','N','D','E','R',0});
            fail("Wrong content is not an image");
        }catch(IllegalArgumentException expected){
            assertEquals("DRIVE_REFERENCE_INVALID_IMAGE_MAGIC",expected.getMessage());
        }
    }
    @Test public void invalidRequestsRejectedBeforeAnyProviderRead()throws Exception{
        try{
            DriveReferenceImport.validateRequested(request("../other.png",HASH));
            fail("Traversal");
        }catch(IllegalArgumentException expected){}
        try{
            DriveReferenceImport.validateRequested(request("Ren.png","0".repeat(63)));
            fail("Bad hash");
        }catch(IllegalArgumentException expected){}
        try{
            DriveReferenceImport.validateRequested(new JSONObject().put("files",new JSONArray()));
            fail("Empty");
        }catch(IllegalArgumentException expected){}
    }
    @Test public void importingNeedsExistingPersistedAndroidFolderGrant()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        try{
            DriveReferenceImport.importFromApprovedTree(c,request("01_Ren_Front_Sides_Back.png",HASH));
            fail("No Google Drive permission from Android system picker");
        }catch(IllegalStateException expected){
            assertEquals("DRIVE_REFERENCE_FOLDER_NOT_GRANTED",expected.getMessage());
        }
    }
    @Test public void repeatedNamesDoNotCauseDoubleImport()throws Exception{
        JSONObject twice=new JSONObject().put("files",new JSONArray()
            .put(new JSONObject().put("filename","Ren.png").put("expected_sha256",HASH))
            .put(new JSONObject().put("filename","Ren.png").put("expected_sha256",HASH)));
        try{
            DriveReferenceImport.validateRequested(twice);
            fail("Ambiguous file identities");
        }catch(IllegalArgumentException expected){
            assertEquals("DUPLICATE_DRIVE_REFERENCE_NAME",expected.getMessage());
        }
    }
}
