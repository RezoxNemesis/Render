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
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

/** Simulates spool replies only. Does not claim native rendering or Android runtime execution. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class NativeCommandDurabilityTest {
    @Test public void longFrameBudgetDoesNotExpandUnrelatedCalls()throws Exception{
        JSONObject frame=new JSONObject().put("operation","render.step");
        assertEquals(21600000,NativeCommandBudget.timeout("blender.production.execute",frame,600000));
        assertEquals(600000,NativeCommandBudget.timeout("blender.production.execute",new JSONObject().put("operation","scene.inspect"),600000));
        assertEquals(21630000,NativeWakeGuard.timeoutForAction("blender.production.render_frame"));
        assertTrue(NativeCommandBudget.readOnlyAssetPoll("blender.production.execute",new JSONObject().put("operation","asset.search")));
        assertFalse(NativeCommandBudget.readOnlyAssetPoll("blender.production.execute",new JSONObject().put("operation","asset.download")));
        assertFalse(NativeCommandBudget.readOnlyAssetPoll("blender.production.execute",new JSONObject().put("operation","asset.import")));
    }
    @Test public void pauseWaitsForClaimedFrameAndRetainsItsExactReceipt()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        File root=new File(app.getFilesDir(),"render_bpy_jobs");
        File pending=new File(root,"pending"),working=new File(root,"working"),results=new File(root,"results");
        pending.mkdirs();working.mkdirs();results.mkdirs();new File(root,"ready").createNewFile();
        Files.write(new File(root,"ready").toPath(),Integer.toString(android.os.Process.myPid()).getBytes(StandardCharsets.US_ASCII));
        new File(root,"ready").setLastModified(System.currentTimeMillis());
        AtomicBoolean cancelled=new AtomicBoolean();ExecutorService executor=Executors.newSingleThreadExecutor();
        File claimed=null,receipt=null;
        try{
            Future<JSONObject> future=executor.submit(()->new BlenderSpool(app).execute("blender.production.execute",
                new JSONObject().put("operation","render.step").put("payload",new JSONObject().put("job_id","f".repeat(32))),cancelled));
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);File request=null;
            while(System.nanoTime()<deadline){
                File[] entries=pending.listFiles((d,n)->n.endsWith(".json"));
                if(entries!=null&&entries.length>0){request=entries[0];break;}
                if(future.isDone())future.get();
                Thread.sleep(5);
            }
            assertNotNull("Native request should be queued",request);
            JSONObject command=new JSONObject(new String(Files.readAllBytes(request.toPath()),StandardCharsets.UTF_8));String id=command.getString("id");
            claimed=new File(working,request.getName());Files.move(request.toPath(),claimed.toPath());
            cancelled.set(true);Thread.sleep(200);
            assertFalse("Pause must wait for the outstanding native frame",future.isDone());
            receipt=new File(results,id+".json");
            JSONObject reply=new JSONObject().put("id",id).put("state","succeeded").put("result",new JSONObject().put("frame",101));
            Files.write(receipt.toPath(),reply.toString().getBytes(StandardCharsets.UTF_8));
            assertEquals(101,future.get(5,TimeUnit.SECONDS).getInt("frame"));
            assertTrue("Completion receipt remains available after the caller receives it",receipt.isFile());
            JSONObject status=BlenderSpool.inspect(app,new JSONObject().put("command_id",id));
            assertTrue(status.getBoolean("native_completion_received"));assertFalse(status.getBoolean("replayed"));
        }finally{
            cancelled.set(true);executor.shutdownNow();
            if(claimed!=null)claimed.delete();if(receipt!=null)receipt.delete();
        }
    }
    @Test public void recoveryInspectionCannotTraverseAndDoesNotInventCompletion()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        try{BlenderSpool.inspect(app,new JSONObject().put("command_id","../other"));fail();}
        catch(IllegalArgumentException expected){}
        JSONObject missing=BlenderSpool.inspect(app,new JSONObject().put("command_id","0".repeat(32)));
        assertFalse(missing.getBoolean("native_completion_received"));assertFalse(missing.getBoolean("safe_to_replay"));
    }
    @Test public void busyInitializedEditorAllowsAssetPollButNeverAnAssetMutation()throws Exception{
        Context app=RuntimeEnvironment.getApplication();File root=new File(app.getFilesDir(),"render_bpy_jobs");
        File pending=new File(root,"pending"),results=new File(root,"results");
        pending.mkdirs();results.mkdirs();File ready=new File(root,"ready");
        Files.write(ready.toPath(),Integer.toString(android.os.Process.myPid()).getBytes(StandardCharsets.US_ASCII));
        ready.setLastModified(System.currentTimeMillis()-60000);
        assertFalse(NativeHeartbeat.ready(app));
        try{new BlenderSpool(app).execute("blender.production.execute",new JSONObject().put("operation","asset.download"),new AtomicBoolean());fail();}
        catch(IllegalStateException expected){assertEquals("BLENDER_EDITOR_NOT_RUNNING",expected.getMessage());}
        ExecutorService executor=Executors.newSingleThreadExecutor();File request=null,receipt=null;
        try{
            Future<JSONObject> future=executor.submit(()->new BlenderSpool(app).execute("blender.production.execute",
                new JSONObject().put("operation","asset.download.status").put("payload",new JSONObject().put("download_id","f".repeat(32))),new AtomicBoolean()));
            long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(5);
            while(System.nanoTime()<deadline){
                File[] entries=pending.listFiles((d,n)->n.endsWith(".json"));
                if(entries!=null&&entries.length>0){request=entries[0];break;}
                if(future.isDone())future.get();Thread.sleep(5);
            }
            assertNotNull(request);
            String id=new JSONObject(new String(Files.readAllBytes(request.toPath()),StandardCharsets.UTF_8)).getString("id");
            receipt=new File(results,id+".json");
            Files.write(receipt.toPath(),new JSONObject().put("id",id).put("state","succeeded")
                .put("result",new JSONObject().put("state","downloaded")).toString().getBytes(StandardCharsets.UTF_8));
            assertEquals("downloaded",future.get(5,TimeUnit.SECONDS).getString("state"));
            assertFalse("Queueing/poll completion must not manufacture fresh liveness",NativeHeartbeat.ready(app));
        }finally{
            executor.shutdownNow();if(request!=null)request.delete();if(receipt!=null)receipt.delete();ready.delete();
        }
    }
}
