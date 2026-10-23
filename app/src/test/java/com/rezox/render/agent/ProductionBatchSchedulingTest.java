package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

/** Host scheduling tests with explicitly fake device readings/receipts.
 * These do not run Blender or establish Android-native render evidence. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class ProductionBatchSchedulingTest {
    private static final String JOB="f".repeat(32);
    private Context context;
    private AtomicBoolean cancelled;
    private JSONObject manifest;
    private FakeRuntime runtime;

    @Before public void setUp()throws Exception{
        context=RuntimeEnvironment.getApplication();
        cancelled=new AtomicBoolean(false);
        manifest=new JSONObject().put("job_id",JOB).put("state","ready")
            .put("fingerprint","unchanged-scene").put("next_frame",101)
            .put("frames",new JSONObject())
            .put("spec",new JSONObject().put("start",101).put("end",103).put("frame_count",3));
        save();runtime=new FakeRuntime();
    }
    private void save()throws Exception{
        Files.write(ProductionFiles.file(context,JOB,"manifest.json").toPath(),
            manifest.toString().getBytes(StandardCharsets.UTF_8));
    }
    private JSONObject run(int cooldown,int maxFrames)throws Exception{
        ExecutorService worker=Executors.newSingleThreadExecutor();
        try{
            return worker.submit(()->ProductionBatch.advance(context,new JSONObject()
                .put("job_id",JOB).put("max_frames",maxFrames).put("cooldown_max_ms",cooldown)
                .put("max_wall_ms",30000).put("expected_fingerprint","unchanged-scene"),
                cancelled,runtime)).get(10,TimeUnit.SECONDS);
        }catch(ExecutionException e){
            if(e.getCause() instanceof Exception)throw (Exception)e.getCause();
            throw e;
        }finally{worker.shutdownNow();}
    }
    private final class FakeRuntime implements ProductionBatch.Runtime {
        long time,renderAt;
        int[] statuses={0};int samples,sleeps,wakes,renders;
        boolean held,space=true,lowMemory,stopDuringSleep,failRender,mismatchReceipt;
        public long now(){return time;}
        public JSONObject sample()throws Exception{
            int status=statuses[Math.min(samples++,statuses.length-1)];
            return new JSONObject().put("thermal_status",status)
                .put("low_memory",lowMemory).put("available_memory_bytes",2_000_000_000L);
        }
        public void sleep(long millis){
            assertFalse("Cooldown/pacing must release CPU wake lock",held);
            assertTrue(millis>0&&millis<=5000);sleeps++;time+=millis;
            if(stopDuringSleep)cancelled.set(true);
        }
        public boolean frameSpaceAvailable(){return space;}
        public AutoCloseable wake(){
            assertFalse(held);wakes++;held=true;
            return ()->{assertTrue(held);held=false;};
        }
        public JSONObject render(JSONObject args)throws Exception{
            assertTrue("Only an outstanding native frame may hold a wake lock",held);
            assertFalse(cancelled.get());renders++;renderAt=time;
            assertEquals("render.step",args.getString("operation"));
            assertEquals(JOB,args.getJSONObject("payload").getString("job_id"));
            if(failRender)throw new IllegalStateException("TEST_NATIVE_OUTCOME_UNCERTAIN");
            int frame=manifest.getInt("next_frame");
            manifest.getJSONObject("frames").put(String.valueOf(frame),new JSONObject());
            manifest.put("next_frame",frame+1);
            if(frame==103)manifest.put("state","frames_complete");
            save();
            return new JSONObject().put("job_id",mismatchReceipt?"wrong-job":JOB)
                .put("state",manifest.getString("state"))
                .put("completed_frames",manifest.getJSONObject("frames").length());
        }
    }
    @Test public void severeThermalCooldownNeverAcquiresWakeLock()throws Exception{
        runtime.statuses=new int[]{3};
        JSONObject result=run(10000,1);
        assertEquals("PAUSED_THERMAL_PRESSURE",result.getString("reason"));
        assertTrue(result.getBoolean("paused"));assertEquals(0,runtime.wakes);
        assertEquals(0,runtime.renders);assertEquals(101,result.getInt("next_frame"));
    }
    @Test public void twoCoolSamplesResumeOnlyMissingFrameWithoutChangingQuality()throws Exception{
        runtime.statuses=new int[]{3,1,1};
        JSONObject result=run(20000,1);
        assertEquals(10000,runtime.renderAt);assertEquals(1,runtime.wakes);
        assertFalse(runtime.held);assertEquals(1,result.getInt("processed_in_batch"));
        assertEquals(102,result.getInt("next_frame"));assertFalse(result.getBoolean("quality_reduced"));
        assertEquals("unchanged-scene",result.getString("fingerprint"));
    }
    @Test public void thermalRelapseResetsConsecutiveCoolSamples()throws Exception{
        runtime.statuses=new int[]{3,0,3,0,0};
        run(25000,1);assertEquals(20000,runtime.renderAt);assertEquals(4,runtime.sleeps);
    }
    @Test public void missingSensorCannotConfirmCooldownAfterSevereReading()throws Exception{
        runtime.statuses=new int[]{3,-1,-1};
        JSONObject result=run(15000,1);
        assertEquals("PAUSED_THERMAL_PRESSURE",result.getString("reason"));
        assertEquals(0,runtime.renders);assertEquals(0,runtime.wakes);
    }
    @Test public void cancellationDuringCooldownStartsNoFrame()throws Exception{
        runtime.statuses=new int[]{3,0};runtime.stopDuringSleep=true;
        JSONObject result=run(20000,1);
        assertEquals("PAUSED_USER_STOP",result.getString("reason"));
        assertEquals(0,runtime.wakes);assertEquals(0,runtime.renders);
    }
    @Test public void memoryAndStorageAdmissionNeverAcquireWakeLock()throws Exception{
        runtime.lowMemory=true;
        assertEquals("PAUSED_MEMORY_PRESSURE",run(0,1).getString("reason"));
        runtime.lowMemory=false;runtime.space=false;
        assertEquals("PAUSED_STORAGE_PRESSURE",run(0,1).getString("reason"));
        assertEquals(0,runtime.wakes);assertEquals(0,runtime.renders);
    }
    @Test public void moderatePacingIsOutsideWakeLock()throws Exception{
        runtime.statuses=new int[]{2};run(0,2);
        assertEquals(2,runtime.renders);assertEquals(2,runtime.wakes);
        assertEquals(2,runtime.sleeps);assertFalse(runtime.held);
    }
    @Test public void uncertainNativeFailureReleasesLockAndIsNotReplayed()throws Exception{
        runtime.failRender=true;
        try{run(0,1);fail();}catch(IllegalStateException expected){
            assertEquals("TEST_NATIVE_OUTCOME_UNCERTAIN",expected.getMessage());
        }
        assertEquals(1,runtime.renders);assertFalse(runtime.held);
        assertEquals(101,manifest.getInt("next_frame"));
        // An explicit later request can claim the scheduler again.
        runtime.failRender=false;run(0,1);assertEquals(2,runtime.renders);
    }
    @Test public void mismatchedNativeReceiptIsRejectedWithoutReplay()throws Exception{
        runtime.mismatchReceipt=true;
        try{run(0,1);fail();}catch(IllegalStateException expected){
            assertEquals("NATIVE_RENDER_JOB_RECEIPT_MISMATCH",expected.getMessage());
        }
        assertEquals(1,runtime.renders);assertFalse(runtime.held);
    }
    @Test public void cooldownStopsAtWallBudgetWithoutStartingFrame()throws Exception{
        runtime.statuses=new int[]{3};
        JSONObject result=run(90000,1);
        assertEquals(30000,result.getLong("wall_elapsed_ms"));
        assertEquals(0,runtime.renders);assertEquals(0,runtime.wakes);
    }
}
