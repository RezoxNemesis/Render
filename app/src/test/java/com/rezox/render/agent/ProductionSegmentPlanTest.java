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
import java.util.List;
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
        byte[] original="bounded encoder output bytes".getBytes(StandardCharsets.UTF_8);
        try{
            Files.write(output.toPath(),original);
            JSONObject receipt=ProductionFiles.receipt(output,job);
            assertNotNull(ProductionSegmentedEncoder.readVerified(app,job,receipt));
            Files.write(output.toPath(),"tampered bytes".getBytes(StandardCharsets.UTF_8));
            assertNull(ProductionSegmentedEncoder.readVerified(app,job,receipt));
        }finally{output.delete();}
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
