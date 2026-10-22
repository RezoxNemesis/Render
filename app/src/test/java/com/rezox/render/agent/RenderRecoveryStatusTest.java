package com.rezox.render.agent;

import android.content.Context;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class RenderRecoveryStatusTest {
    private static byte[] blend(){
        byte[] bytes=new byte[512];
        byte[] header="BLENDER".getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(header,0,bytes,0,header.length);
        for(int i=7;i<bytes.length;i++)bytes[i]=(byte)(i%251);
        return bytes;
    }
    private static String digest(byte[] bytes)throws Exception{
        byte[] hash=MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder b=new StringBuilder();
        for(byte one:hash)b.append(String.format(java.util.Locale.ROOT,"%02x",one&255));
        return b.toString();
    }
    @Test public void checksumProvenNativeSnapshotIsRecoverableWithoutQuitBlend()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        File dir=ProductionFiles.folder(c,"Projects");
        File file=new File(dir,"CurrentSession.blend");
        File record=new File(dir,"CurrentSession.json");
        try{
            byte[] content=blend();
            Files.write(file.toPath(),content);
            JSONObject proof=new JSONObject().put("filename",file.getName())
                .put("bytes",content.length).put("sha256",digest(content));
            Files.write(record.toPath(),proof.toString().getBytes(StandardCharsets.UTF_8));
            JSONObject status=RenderRecoveryStatus.inspect(c);
            assertTrue(status.getBoolean("recoverable"));
            assertTrue(status.getBoolean("latest_session_verified"));
            assertFalse(status.getBoolean("relies_on_quit_blend"));
            assertFalse(status.getBoolean("device_render_crash_root_cause_verified"));
            File event=new File(new File(ProductionFiles.root(c),"Diagnostics"),
                "native_render_event.json");
            event.getParentFile().mkdirs();
            try{
                Files.write(event.toPath(),"{broken json".getBytes(StandardCharsets.UTF_8));
                JSONObject withBadLog=RenderRecoveryStatus.inspect(c);
                assertTrue(withBadLog.getBoolean("recoverable"));
                assertEquals("invalid_native_render_record",
                    withBadLog.getString("last_native_render_state"));
            }finally{event.delete();}
            byte[] corrupt=content.clone();corrupt[300]^=8;Files.write(file.toPath(),corrupt);
            status=RenderRecoveryStatus.inspect(c);
            assertFalse(status.getBoolean("latest_session_verified"));
        }finally{
            file.delete();record.delete();
        }
    }
    @Test public void incompleteF12RenderIsReportedButNotInventedAsGpuFailure()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        File dir=new File(ProductionFiles.root(c),"Diagnostics");dir.mkdirs();
        File event=new File(dir,"native_render_event.json");
        try{
            JSONObject started=new JSONObject().put("state","started")
                .put("timestamp_epoch_seconds",123456)
                .put("render_engine","CYCLES");
            Files.write(event.toPath(),started.toString().getBytes(StandardCharsets.UTF_8));
            JSONObject status=RenderRecoveryStatus.inspect(c);
            assertTrue(status.getBoolean("last_native_render_unconfirmed"));
            assertEquals("CYCLES",status.getString("last_native_render_engine"));
            assertFalse(status.getBoolean("device_render_crash_root_cause_verified"));
            started.put("state","native_callback_completed");
            Files.write(event.toPath(),started.toString().getBytes(StandardCharsets.UTF_8));
            assertFalse(RenderRecoveryStatus.inspect(c).getBoolean("last_native_render_unconfirmed"));
        }finally{event.delete();}
    }
    @Test public void stillJobDoesNotPretendAnAnimationIsOneFrame()throws Exception{
        assertTrue(RenderManualJobs.stillImage(new JSONObject()
            .put("spec",new JSONObject().put("output_kind","STILL"))));
        assertFalse(RenderManualJobs.stillImage(new JSONObject()
            .put("spec",new JSONObject().put("output_kind","ANIMATION"))));
        assertFalse(RenderManualJobs.stillImage(new JSONObject()
            .put("spec",new JSONObject()))); // existing v0.24 manifests remain valid
    }
}
