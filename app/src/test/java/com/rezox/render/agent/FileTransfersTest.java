package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.OutputStream;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

/** File I/O fixtures only; text data is never represented as a Blender project. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class FileTransfersTest {
    @Test public void explicitDocumentCopyPreservesOriginalAndReturnsVerifiedImmutableHandle()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        StorageDocuments.Node source=StorageDocuments.createFile(c,"workspace","root","source.txt","text/plain");
        try(OutputStream out=StorageDocuments.write(c,source)){out.write("original text".getBytes(StandardCharsets.UTF_8));}
        JSONObject p=new JSONObject().put("request_id","import-text-0001").put("location_id","workspace").put("document_id",source.id);
        JSONObject task=FileTransfers.enqueue(c,"import",p);
        FileTransfers.run(c,task.getString("transfer_id"),new AtomicBoolean(false));
        JSONObject status=FileTransfers.status(c,task.getString("transfer_id"));
        assertEquals("completed",status.getString("state"));
        JSONObject result=status.getJSONObject("result");
        assertFalse(result.getBoolean("native_import_completed"));
        File copy=ProductionFiles.file(c,"Imports",result.getString("file"));
        assertEquals("original text",new String(Files.readAllBytes(copy.toPath()),StandardCharsets.UTF_8));
        assertEquals(ProductionFiles.sha(copy),result.getString("sha256"));
        assertEquals("original text",new String(Files.readAllBytes(source.file.toPath()),StandardCharsets.UTF_8));
        assertEquals(task.getString("transfer_id"),FileTransfers.enqueue(c,"import",p).getString("transfer_id"));
    }
    @Test public void conflictingReuseOfRequestIdCannotOverwriteItsMeaning()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        JSONObject p=new JSONObject().put("request_id","import-conflict-0001").put("location_id","workspace").put("document_id","root");
        FileTransfers.enqueue(c,"import",p);
        try{FileTransfers.enqueue(c,"import",new JSONObject(p.toString()).put("document_id","different"));fail();}
        catch(IllegalArgumentException expected){assertEquals("TRANSFER_REQUEST_CONFLICT",expected.getMessage());}
    }
    @Test public void checksumMismatchCannotPublishOrReplaceAnArtistFile()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        File source=ProductionFiles.file(c,"Exports","test.txt");Files.write(source.toPath(),"real source".getBytes(StandardCharsets.UTF_8));
        JSONObject task=FileTransfers.enqueue(c,"export",new JSONObject().put("request_id","export-wrong-hash-01")
            .put("category","Exports").put("filename","test.txt").put("expected_sha256","0".repeat(64))
            .put("location_id","workspace").put("parent_id","root").put("name","published.txt"));
        FileTransfers.run(c,task.getString("transfer_id"),new AtomicBoolean(false));
        assertEquals("failed",FileTransfers.status(c,task.getString("transfer_id")).getString("state"));
        assertNull(StorageDocuments.find(c,"workspace","root","published.txt"));
        assertEquals("real source",new String(Files.readAllBytes(source.toPath()),StandardCharsets.UTF_8));
    }
    @Test public void cancellationOfQueuedTransferDoesNotWriteADestination()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        JSONObject task=FileTransfers.enqueue(c,"import",new JSONObject().put("request_id","import-cancelled-01")
            .put("location_id","workspace").put("document_id","root"));
        FileTransfers.control(c,task.getString("transfer_id"),"cancel");
        FileTransfers.run(c,task.getString("transfer_id"),new AtomicBoolean(false));
        assertEquals("cancelled",FileTransfers.status(c,task.getString("transfer_id")).getString("state"));
    }
    @Test public void changedSourcePrefixIsRejectedInsteadOfCombiningTwoVersions()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        StorageDocuments.Node source=StorageDocuments.createFile(c,"workspace","root","changing.txt","text/plain");
        try(OutputStream out=StorageDocuments.write(c,source)){out.write("new source bytes".getBytes(StandardCharsets.UTF_8));}
        JSONObject task=FileTransfers.enqueue(c,"import",new JSONObject().put("request_id","changed-prefix-01")
            .put("location_id","workspace").put("document_id",source.id));String id=task.getString("transfer_id");
        Files.write(new File(c.getFilesDir(),"FileTransfers/"+id+".partial").toPath(),"old".getBytes(StandardCharsets.UTF_8));
        FileTransfers.run(c,id,new AtomicBoolean(false));
        JSONObject status=FileTransfers.status(c,id);assertEquals("failed",status.getString("state"));
        assertEquals("TRANSFER_SOURCE_CHANGED_START_NEW_REQUEST",status.getString("error_code"));
        assertFalse(status.has("result"));
    }
    @Test public void completedExportCanBePolledAndRepeatedWithoutOverwritingAnotherFile()throws Exception{
        Context c=RuntimeEnvironment.getApplication();File source=ProductionFiles.file(c,"Exports","verified.txt");
        Files.write(source.toPath(),"artist output".getBytes(StandardCharsets.UTF_8));String sha=ProductionFiles.sha(source);
        JSONObject payload=new JSONObject().put("request_id","export-verified-01").put("category","Exports").put("filename","verified.txt")
            .put("expected_sha256",sha).put("location_id","workspace").put("parent_id","root").put("name","original.txt");
        String id=FileTransfers.enqueue(c,"export",payload).getString("transfer_id");FileTransfers.run(c,id,new AtomicBoolean(false));
        assertTrue(FileTransfers.status(c,id).getJSONObject("result").getBoolean("provider_readback_sha256_verified"));
        StorageDocuments.Node document=StorageDocuments.find(c,"workspace","root","original.txt");
        try(OutputStream out=StorageDocuments.write(c,document)){out.write("artist edited".getBytes(StandardCharsets.UTF_8));}
        JSONObject duplicate=FileTransfers.enqueue(c,"export",payload);assertTrue(duplicate.getBoolean("already_requested"));
        FileTransfers.run(c,id,new AtomicBoolean(false));
        JSONObject conflict=FileTransfers.enqueue(c,"export",new JSONObject(payload.toString()).put("request_id","export-conflict-02"));
        FileTransfers.run(c,conflict.getString("transfer_id"),new AtomicBoolean(false));
        assertEquals("DESTINATION_NAME_CONFLICT",FileTransfers.status(c,conflict.getString("transfer_id")).getString("error_code"));
        assertEquals("artist edited",new String(Files.readAllBytes(document.file.toPath()),StandardCharsets.UTF_8));
    }
    @Test public void refreshingExpiredUrlDoesNotExposeCredentialOrChangeContentIdentity()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        JSONObject payload=new JSONObject().put("request_id","drive-url-refresh-01").put("url","https://example.com/private?token=old")
            .put("name","asset.glb").put("expected_sha256","a".repeat(64)).put("expected_bytes",100);
        String id=FileTransfers.enqueue(c,"fetch",payload).getString("transfer_id");FileTransfers.control(c,id,"pause");
        JSONObject refreshed=FileTransfers.refresh(c,id,"https://example.com/private?token=new");
        assertTrue(refreshed.getBoolean("digest_and_size_unchanged"));assertFalse(refreshed.toString().contains("token="));
        assertTrue(FileTransfers.enqueue(c,"fetch",payload).getBoolean("already_requested"));
    }
}
