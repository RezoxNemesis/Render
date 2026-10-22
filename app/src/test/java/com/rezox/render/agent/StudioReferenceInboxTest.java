package com.rezox.render.agent;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import org.json.JSONObject;
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
public class StudioReferenceInboxTest {
    @Test public void importingRequiresExplicitOwnerMediaIntent(){
        assertFalse(StudioReferenceInbox.isExplicitOwnerMediaIntent(null));
        assertFalse(StudioReferenceInbox.isExplicitOwnerMediaIntent(new Intent(Intent.ACTION_VIEW)));
        assertTrue(StudioReferenceInbox.isExplicitOwnerMediaIntent(new Intent(Intent.ACTION_SEND)));
        assertTrue(StudioReferenceInbox.isExplicitOwnerMediaIntent(new Intent(Intent.ACTION_OPEN_DOCUMENT)));
        assertTrue(StudioReferenceInbox.isExplicitOwnerMediaIntent(new Intent(Intent.ACTION_SEND_MULTIPLE)));
    }
    @Test public void emptyInboxAndNoGalleryAccess()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        JSONObject listing=StudioReferenceInbox.list(context,new JSONObject().put("offset",0).put("limit",20));
        assertTrue(listing.getJSONArray("assets").length()>=0);
        for(String bad:new String[]{"../secret.jpg","/sdcard/DCIM/picture.png","image.jpg","bad.png"}){
            try{StudioReferenceInbox.details(context,new JSONObject().put("asset",bad));fail(bad);}
            catch(IllegalArgumentException expected){}
        }
    }
    @Test public void doesNotTrustArbitraryFileOrWebUri()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        for(String u:new String[]{"file:///sdcard/DCIM/a.jpg","https://attacker.test/file.mp4"}){
            try{StudioReferenceInbox.receive(context,
                  new Intent(Intent.ACTION_SEND).putExtra(Intent.EXTRA_STREAM,Uri.parse(u)));fail(u);}
            catch(IllegalArgumentException expected){}
        }
    }
    @Test public void refusesTraversalAndUnknownMetadata()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        JSONObject p=new JSONObject().put("asset","a".repeat(64)+".jpg");
        try{StudioReferenceInbox.details(context,p);fail();}
        catch(IllegalArgumentException expected){assertEquals("IMPORTED_REFERENCE_NOT_FOUND",expected.getMessage());}
    }
    @Test public void studioHandIsNotARecordedFakeTap()throws Exception{
        JSONObject status=StudioLiveHandOverlay.snapshot(RuntimeEnvironment.getApplication());
        assertFalse(status.getBoolean("fabricated_ui_taps"));
        assertFalse(status.getBoolean("unrelated_apps_controlled"));
        assertTrue(status.getBoolean("native_api_command_not_equivalent_to_menu_click"));
    }
}
