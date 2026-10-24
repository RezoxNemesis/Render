package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;
import java.util.Arrays;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class ProductionSegmentPlanTest {
    private static JSONObject spec(int first,int last,int fps,int bitrate)throws Exception{
        return new JSONObject().put("start",first).put("end",last)
            .put("fps",fps).put("fps_base",1.0).put("bitrate",bitrate)
            .put("width",1920).put("height",1080)
            .put("frame_count",last-first+1);
    }
    // A lightweight box-layout fixture, deliberately NOT a claimed playable
    // video. Android MediaMetadataRetriever checks actual encoder output.
    private static byte[] atom(String fourcc,byte[] payload)throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        DataOutputStream out=new DataOutputStream(bytes);
        out.writeInt(payload.length+8);
        out.writeBytes(fourcc);
        out.write(payload);
        out.flush();
        return bytes.toByteArray();
    }
    private static byte[] mp4ContainerFixture()throws Exception{
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        bytes.write(atom("ftyp",new byte[]{'i','s','o','m',0,0,0,0,'i','s','o','m'}));
        bytes.write(atom("mdat",new byte[64]));
        bytes.write(atom("moov",atom("trak",new byte[16])));
        return bytes.toByteArray();
    }
    @Test public void tenGigabyteVideoHasExactGaplessSegments()throws Exception{
        JSONObject request=spec(101,100000,24,32000000);
        List<ProductionSegmentPlan.Span> spans=ProductionSegmentPlan.plan(request);
        assertTrue(spans.size()>20);
        int next=101,count=0;
        for(ProductionSegmentPlan.Span part:spans){
            assertEquals(next,part.start);
            assertTrue(part.end<=100000);
            assertTrue(part.count()>0);
            assertTrue(part.count()<=ProductionSegmentPlan.MAX_SECONDS*24);
            long nominal=(long)Math.ceil(part.count()*(32000000.0/(8*24)));
            assertTrue(nominal<=ProductionSegmentPlan.TARGET_BYTES+1000);
            count+=part.count();
            next=part.end+1;
        }
        assertEquals(100000,next-1);
        assertEquals(100000-101+1,count);
        assertEquals("CYCLES",request.optString("engine","CYCLES"));
    }
    @Test public void shortExistingRenderRetainsMonolithicPath()throws Exception{
        JSONObject job=spec(140,163,24,16000000);
        assertFalse(ProductionSegmentPlan.segmented(job));
        List<ProductionSegmentPlan.Span> spans=ProductionSegmentPlan.plan(job);
        assertEquals(1,spans.size());
        assertEquals(140,spans.get(0).start);
        assertEquals(163,spans.get(0).end);
    }
    @Test public void deterministicFractionsCannotSkipOrDuplicateFrames()throws Exception{
        JSONObject job=spec(1200,14000,30,24000000).put("fps_base",1.001);
        List<ProductionSegmentPlan.Span> spans=ProductionSegmentPlan.plan(job);
        assertTrue(spans.size()>1);
        int expected=1200;
        for(ProductionSegmentPlan.Span span:spans){
            assertEquals(expected,span.start);
            expected=span.end+1;
        }
        assertEquals(14001,expected);
        assertEquals(1.001,job.getDouble("fps_base"),0.000001);
    }
    @Test public void segmentProofPersistsAndHashMismatchIsRejected()throws Exception{
        Context c=RuntimeEnvironment.getApplication(),app=c;
        String job="7".repeat(32);
        File output=ProductionFiles.file(app,job,ProductionSegmentedEncoder.partName(job,0));
        byte[] original=mp4ContainerFixture();
        try{
            Files.write(output.toPath(),original);
            JSONObject receipt=ProductionFiles.receipt(output,job)
                .put("frames",24).put("start_frame",101).put("end_frame",124);
            ProductionSegmentPlan.Span span=new ProductionSegmentPlan.Span(101,124,0);
            assertTrue(ProductionSegmentedEncoder.hasCompleteMp4Container(output));
            assertNotNull(ProductionSegmentedEncoder.readVerified(app,job,receipt,span));
            receipt.put("end_frame",125);
            assertNull("matching bytes are not proof of the same frame range",
                ProductionSegmentedEncoder.readVerified(app,job,receipt,span));
            receipt.put("end_frame",124);
            assertNull("a different part index must not adopt these frames",
                ProductionSegmentedEncoder.readVerified(app,job,receipt,
                    new ProductionSegmentPlan.Span(101,124,1)));
            Files.write(output.toPath(),Arrays.copyOf(original,original.length-3));
            assertFalse("truncated moov must not be accepted",
                ProductionSegmentedEncoder.hasCompleteMp4Container(output));
            assertNull(ProductionSegmentedEncoder.readVerified(app,job,receipt,span));
            Files.write(output.toPath(),"tampered bytes".getBytes(StandardCharsets.UTF_8));
            assertNull(ProductionSegmentedEncoder.readVerified(app,job,receipt,span));
        }finally{output.delete();}
    }
    @Test public void noTrakAndCorruptAtomSizesCannotBePublished()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String job="e".repeat(32);
        File output=ProductionFiles.file(app,job,ProductionSegmentedEncoder.partName(job,0));
        try{
            byte[] good=mp4ContainerFixture();
            Files.write(output.toPath(),good);
            assertTrue(ProductionSegmentedEncoder.hasCompleteMp4Container(output));
            byte[] corrupted=good.clone();
            // "moov" is the last box: a length larger than the file is invalid.
            int moov=20+72;
            corrupted[moov+0]=(byte)0x7f;
            Files.write(output.toPath(),corrupted);
            assertFalse(ProductionSegmentedEncoder.hasCompleteMp4Container(output));
            ByteArrayOutputStream missingTrack=new ByteArrayOutputStream();
            missingTrack.write(atom("ftyp",new byte[]{'i','s','o','m',0,0,0,0}));
            missingTrack.write(atom("mdat",new byte[64]));
            missingTrack.write(atom("moov",atom("free",new byte[16])));
            Files.write(output.toPath(),missingTrack.toByteArray());
            assertFalse(ProductionSegmentedEncoder.hasCompleteMp4Container(output));
        }finally{output.delete();}
    }
    @Test public void badMonolithicVideoIsPreservedBeforeRetry()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String job="b".repeat(32),filename="Production_"+job+".mp4";
        File output=ProductionFiles.file(app,job,filename);
        File preserved=ProductionFiles.file(app,job,
            "Production_"+job+".unverified.mp4");
        byte[] original="do not overwrite artist bytes".getBytes(StandardCharsets.UTF_8);
        try{
            Files.write(output.toPath(),original);
            ProductionVideoEncoder.quarantineUnverifiedOutput(app,job,filename);
            assertFalse(output.exists());
            assertArrayEquals(original,Files.readAllBytes(preserved.toPath()));
            Files.write(output.toPath(),"second video".getBytes(StandardCharsets.UTF_8));
            try{
                ProductionVideoEncoder.quarantineUnverifiedOutput(app,job,filename);
                fail("must not overwrite existing quarantined output");
            }catch(IllegalStateException expected){
                assertEquals("UNVERIFIED_VIDEO_NEEDS_MANUAL_INSPECTION",
                    expected.getMessage());
            }
            assertEquals("second video",new String(Files.readAllBytes(output.toPath()),
                StandardCharsets.UTF_8));
            assertArrayEquals(original,Files.readAllBytes(preserved.toPath()));
        }finally{output.delete();preserved.delete();}
    }
    @Test public void downloadsRejectQuarantinedOrIncompleteRenderMp4()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String job="c".repeat(32);
        for(String filename:new String[]{
            "Production_"+job+".unverified.mp4",
            "Production_"+job+".mp4"}){
            File output=ProductionFiles.file(app,job,filename);
            try{
                Files.write(output.toPath(),"bad MP4".getBytes(StandardCharsets.UTF_8));
                JSONObject request=new JSONObject().put("category",job)
                    .put("filename",filename)
                    .put("expected_sha256",ProductionFiles.sha(output));
                try{ProductionFiles.export(app,request);fail("invalid MP4 exported");}
                catch(IOException expected){
                    assertEquals(filename.endsWith(".unverified.mp4")?
                        "ARTIFACT_INCOMPLETE":"VIDEO_CONTAINER_INCOMPLETE",
                        expected.getMessage());
                }
            }finally{output.delete();}
        }
    }
    @Test public void exportChecksPlanIndexBeforeReadingFiles()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        String id="a".repeat(32);
        File manifest=ProductionFiles.file(c,id,"manifest.json");
        JSONObject spec=spec(101,124,24,16000000);
        JSONObject job=new JSONObject().put("spec",spec)
            .put("encoded_segments",new JSONObject().put("1",new JSONObject()));
        try{
            Files.write(manifest.toPath(),job.toString().getBytes(StandardCharsets.UTF_8));
            try{RenderManualJobs.exportSegment(c,id,1);fail();}
            catch(IllegalArgumentException expected){
                assertEquals("SEGMENT_OUTSIDE_RENDER_PLAN",expected.getMessage());
            }
        }finally{manifest.delete();}
    }
    @Test public void unsupportedFrameRatesAreRejectedExplicitly()throws Exception{
        JSONObject request=spec(1,1000,24,32000000).put("fps_base",100);
        try{ProductionSegmentPlan.plan(request);fail();}
        catch(IllegalArgumentException expected){}
        assertTrue(ProductionSegmentedEncoder.partName("a".repeat(32),8).endsWith("part_00008.mp4"));
        try{ProductionSegmentedEncoder.partName("../",0);fail();}
        catch(IllegalArgumentException expected){}
    }
}
