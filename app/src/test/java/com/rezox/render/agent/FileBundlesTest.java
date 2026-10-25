package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipOutputStream;
import java.util.zip.ZipEntry;
import static org.junit.Assert.*;

/** Archive byte fixtures only, never presented as native model/texture success. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class FileBundlesTest {
    private File zip(Context c,String path)throws Exception{
        File source=ProductionFiles.file(c,"Imports","fixture.zip");
        try(ZipOutputStream out=new ZipOutputStream(Files.newOutputStream(source.toPath()))){
            out.putNextEntry(new ZipEntry(path));out.write("original asset bytes".getBytes(StandardCharsets.UTF_8));out.closeEntry();
        }return source;
    }
    private String enqueue(Context c,File source,String request)throws Exception{
        return FileTransfers.enqueue(c,"unpack",new JSONObject().put("request_id",request).put("filename",source.getName())
            .put("expected_sha256",ProductionFiles.sha(source))).getString("transfer_id");
    }
    @Test public void dependencyPathsSurviveAndCompletedBundleIsVerifiedBeforeReuse()throws Exception{
        Context c=RuntimeEnvironment.getApplication();File original=zip(c,"textures/diffuse.txt");String sha=ProductionFiles.sha(original);
        String id=enqueue(c,original,"bundle-original-01");FileTransfers.run(c,id,new AtomicBoolean(false));
        JSONObject status=FileTransfers.status(c,id);assertEquals("completed",status.getString("state"));
        assertFalse(status.getJSONObject("result").getBoolean("native_import_completed"));
        File extracted=new File(ProductionFiles.folder(c,"Imports"),"Bundles/"+sha+"/textures/diffuse.txt");
        assertEquals("original asset bytes",new String(Files.readAllBytes(extracted.toPath()),StandardCharsets.UTF_8));
        assertEquals(sha,ProductionFiles.sha(original));
        Files.write(extracted.toPath(),"corrupt".getBytes(StandardCharsets.UTF_8));
        String second=enqueue(c,original,"bundle-recheck-02");FileTransfers.run(c,second,new AtomicBoolean(false));
        assertEquals("BUNDLE_INTEGRITY_FAILED_ORIGINAL_RETAINED",FileTransfers.status(c,second).getString("error_code"));
    }
    @Test public void pathTraversalIsRejectedBeforeWritingArtistStorage()throws Exception{
        Context c=RuntimeEnvironment.getApplication();File original=zip(c,"../../outside.txt");String id=enqueue(c,original,"bundle-traversal-01");
        FileTransfers.run(c,id,new AtomicBoolean(false));assertEquals("failed",FileTransfers.status(c,id).getString("state"));
        assertFalse(new File(c.getFilesDir(),"outside.txt").exists());assertTrue(original.isFile());
    }
    @Test public void absoluteWindowsAndReservedMetadataPathsAreNotAssetEntries(){
        for(String path:new String[]{"/absolute","a\\b","C:/asset","a/../b","a//b","_render_bundle_manifest.json","a/./b"}){
            try{FileBundles.relative(path);fail(path);}catch(IllegalArgumentException expected){}
        }
        assertEquals("models/model.obj",FileBundles.relative("models/model.obj"));
    }
}
