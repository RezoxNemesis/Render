package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import java.io.File;
import java.nio.file.Files;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class NativeStudioPlanStatusTest {
    @Test public void statusIsAvailableWithoutBpyAndDisclosesNoPayload()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        String id="e".repeat(32);
        File record=new File(NativeStudioPlanStatus.folder(app),id+".json");
        JSONObject first=new JSONObject().put("operation","mesh.create")
            .put("payload",new JSONObject().put("secret_asset_name","private-work"));
        JSONObject other=new JSONObject().put("operation","animation.keys").put("payload",new JSONObject());
        JSONObject saved=new JSONObject().put("plan_id",id).put("name","Actor animation")
            .put("fingerprint","1".repeat(64)).put("state","queued")
            .put("steps",new JSONArray().put(first).put(other))
            .put("next",1).put("updated_epoch_ms",System.currentTimeMillis())
            .put("receipts",new JSONArray().put(new JSONObject()
                .put("operation","mesh.create").put("index",0).put("state","succeeded")));
        try{
            Files.write(record.toPath(),saved.toString().getBytes(StandardCharsets.UTF_8));
            JSONObject args=new JSONObject().put("operation","studio.plan.status")
                .put("payload",new JSONObject().put("plan_id",id))
                .put("target_id",new AgentSecrets(app).renderPublicId());
            assertTrue(ProductionBridge.outOfBand(args));
            JSONObject status=ProductionBridge.execute(app,args,new AtomicBoolean(false));
            assertEquals("queued",status.getString("state"));
            assertEquals(1,status.getInt("completed_steps"));
            assertEquals(2,status.getInt("total_steps"));
            assertFalse(status.toString().contains("private-work"));
            assertFalse(status.has("steps"));
            assertFalse(status.getBoolean("native_executor_live_verified"));
            args.put("target_id","00000000-0000-0000-0000-000000000000");
            try{ProductionBridge.execute(app,args,new AtomicBoolean(false));fail();}
            catch(IllegalArgumentException expected){
                assertEquals("RENDER_TARGET_ID_REQUIRED_OR_MISMATCH",expected.getMessage());
            }
            JSONObject list=new JSONObject().put("operation","studio.plan.list")
                .put("payload",new JSONObject())
                .put("target_id",new AgentSecrets(app).renderPublicId());
            assertTrue(ProductionBridge.outOfBand(list));
            assertTrue(ProductionBridge.execute(app,list,new AtomicBoolean(false))
                .getJSONArray("jobs").length()>=1);
            saved.put("state","running").put("updated_epoch_ms",
                System.currentTimeMillis()-200000);
            Files.write(record.toPath(),saved.toString().getBytes(StandardCharsets.UTF_8));
            assertEquals("running_status_unconfirmed",
                NativeStudioPlanStatus.status(app,new JSONObject().put("plan_id",id))
                    .getString("state"));
        }finally{Files.deleteIfExists(record.toPath());}
    }
    @Test public void rejectsTraversalAndMalformedReceipts()throws Exception{
        Context app=RuntimeEnvironment.getApplication();
        try{NativeStudioPlanStatus.status(app,new JSONObject().put("plan_id","../../.."));fail();}
        catch(IllegalArgumentException expected){assertEquals("STUDIO_PLAN_ID_INVALID",expected.getMessage());}
        String id="f".repeat(32);
        File corrupt=new File(NativeStudioPlanStatus.folder(app),id+".json");
        try{
            Files.write(corrupt.toPath(),new byte[]{0,1,2,3});
            try{NativeStudioPlanStatus.status(app,new JSONObject().put("plan_id",id));fail();}
            catch(Exception expected){assertNotNull(expected);}
        }finally{Files.deleteIfExists(corrupt.toPath());}
    }
}
