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

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.io.File;

import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class ProductionBatchDriveTest {
    @Test public void noBackupFolderMeansNoDriveClaim()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        JSONObject status=ProductionDriveStorage.status(c);
        assertFalse(status.getBoolean("folder_granted"));
        assertFalse(status.getBoolean("cloud_rendering"));
        assertFalse(status.getBoolean("remote_sync_verified"));
        try{
            ProductionDriveStorage.backup(c,new JSONObject()
                .put("category","Projects").put("filename","scene.blend")
                .put("expected_sha256","a".repeat(64)));
            fail("No consent");
        }catch(IllegalStateException expected){
            assertEquals("BACKUP_DOCUMENT_FOLDER_NOT_GRANTED",expected.getMessage());
        }
    }
    @Test public void invalidDocumentTreeCannotPersist()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        assertFalse(ProductionDriveStorage.acceptFolderSelection(c,0,null));
        try{ProductionDriveStorage.acceptFolderSelection(c,-1,
            new Intent().setData(Uri.parse("https://drive.google.com/")));fail("External untrusted URL");}
        catch(IllegalArgumentException expected){}
    }
    @Test public void renderStatusIsReadOnlyAndResumeAligned()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        String jobId="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        File manifest=ProductionFiles.file(c,jobId,"manifest.json");
        JSONObject spec=new JSONObject().put("frame_count",250);
        JSONObject frames=new JSONObject();
        frames.put("1",new JSONObject().put("sha256","x"));
        JSONObject data=new JSONObject().put("state","ready")
            .put("fingerprint","revision-1").put("next_frame",2)
            .put("spec",spec).put("frames",frames);
        Files.write(manifest.toPath(),data.toString().getBytes(StandardCharsets.UTF_8));
        JSONObject status=ProductionBatch.jobStatus(c,jobId);
        assertEquals(1,status.getInt("completed_frames"));
        assertEquals(2,status.getInt("next_frame"));
        assertFalse(status.getBoolean("quality_reduced"));
        assertEquals("revision-1",status.getString("fingerprint"));
        manifest.delete();
    }
    @Test public void invalidBatchParametersFailBeforeNativeEdit()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        String jobId="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        File manifest=ProductionFiles.file(c,jobId,"manifest.json");
        JSONObject m=new JSONObject().put("spec",new JSONObject().put("frame_count",4))
            .put("frames",new JSONObject()).put("state","ready")
            .put("next_frame",1).put("fingerprint","a");
        Files.write(manifest.toPath(),m.toString().getBytes(StandardCharsets.UTF_8));
        try{
            try{ProductionBatch.advance(c,new JSONObject().put("job_id",jobId).put("max_frames",13),
                new java.util.concurrent.atomic.AtomicBoolean(false));
                fail("Batch must be bounded");
            }catch(IllegalArgumentException expected){}
            try{ProductionBatch.advance(c,new JSONObject().put("job_id",jobId)
                .put("expected_fingerprint","different"),new java.util.concurrent.atomic.AtomicBoolean(false));
                fail("Wrong render snapshot");
            }catch(IllegalArgumentException expected){
                assertEquals("RENDER_REVISION_CONFLICT",expected.getMessage());
            }
        }finally{manifest.delete();}
    }
}