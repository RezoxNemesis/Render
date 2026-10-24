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
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class ProductionBridgeTest {
    @Test public void folderWorkIsDiscoverableAndTargetScopedWhileBlenderIsUnavailable()throws Exception{
        Context c=RuntimeEnvironment.getApplication();JSONObject args=new JSONObject().put("operation","storage.folder.create")
            .put("payload",new JSONObject().put("location_id","workspace").put("name","ArtistProject"));
        assertTrue(ProductionBridge.outOfBand(args));
        try{ProductionBridge.execute(c,args,new AtomicBoolean(false));fail();}
        catch(IllegalArgumentException expected){assertEquals("RENDER_TARGET_ID_REQUIRED_OR_MISMATCH",expected.getMessage());}
        JSONObject caps=ProductionBridge.execute(c,new JSONObject().put("operation","capabilities"),new AtomicBoolean(false));
        assertTrue(caps.getJSONArray("operations").toString().contains("storage.task.refresh"));
        assertTrue(caps.getJSONArray("operations").toString().contains("file.importers"));
        args.put("target_id",caps.getString("render_public_id"));
        JSONObject discovery=ProductionBridge.execute(c,new JSONObject().put("operation","storage.capabilities")
            .put("target_id",caps.getString("render_public_id")),new AtomicBoolean(false));
        assertEquals(StorageOperations.NAMES.length,discovery.getJSONArray("operations").length());
        JSONObject result=ProductionBridge.execute(c,args,new AtomicBoolean(false));assertTrue(result.getBoolean("directory"));
        assertFalse(result.getBoolean("native_editor_required"));
    }
    @Test public void compatibilityDiagnosisBypassesBusyNativeWorkAndNeedsNoEditor()throws Exception{
        JSONObject args=new JSONObject().put("operation","connection.diagnose").put("payload",new JSONObject());
        assertTrue(ProductionBridge.outOfBand(args));
        Context c=RuntimeEnvironment.getApplication();
        JSONObject caps=ProductionBridge.execute(c,new JSONObject().put("operation","capabilities"),new AtomicBoolean(false));
        args.put("target_id",caps.getString("render_public_id"));
        Files.write(new File(c.getFilesDir(),"blender-startup.log").toPath(),
            "ndk_translation/intrinsics CHECK failed: host_platform::kHasF16C".getBytes(java.nio.charset.StandardCharsets.UTF_8));
        c.getSharedPreferences("render_editor_launch",Context.MODE_PRIVATE).edit()
            .putLong("launch_started_wall_ms",1).commit();
        JSONObject result=ProductionBridge.execute(c,args,new AtomicBoolean(false))
            .getJSONObject("native_runtime_diagnostics");
        assertTrue(result.getBoolean("failure_classified"));
        assertEquals("ANDROID_TRANSLATOR_F16C_UNAVAILABLE",result.getString("failure_code"));
        assertFalse(result.getBoolean("automatic_retry_safe"));
    }
    @Test public void acceptsTypedEnvelopeButNeverPythonOrGallery()throws Exception{
        ProductionBridge.validate(new JSONObject().put("operation","mesh.create").put("payload",new JSONObject()));
        for(String name:new String[]{"python.eval","shell.exec","gallery.list","read_arbitrary_file"}){
            try{ProductionBridge.validate(new JSONObject().put("operation",name));fail(name);}catch(IllegalArgumentException expected){}
        }
        try{ProductionBridge.validate(new JSONObject().put("operation","project.create").put("code","x"));fail();}catch(IllegalArgumentException expected){}
        try{ProductionBridge.validate(new JSONObject().put("operation","project.create").put("payload","x"));fail();}catch(IllegalArgumentException expected){}
    }
    @Test public void mutationsRequireCurrentRenderIdentity()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        try{ProductionBridge.execute(c,new JSONObject().put("operation","project.create").put("payload",new JSONObject().put("name","NewScene")),new AtomicBoolean(false));fail();}
        catch(IllegalArgumentException expected){assertEquals("RENDER_TARGET_ID_REQUIRED_OR_MISMATCH",expected.getMessage());}
    }
    @Test public void pathsAreOwnedAndSymlinksRefused()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        for(String name:new String[]{"../secret","/secret","a/b","a\\b",""}){
            try{ProductionFiles.file(c,"Assets",name);fail(name);}catch(IllegalArgumentException expected){}
        }
        try{ProductionFiles.file(c,"../../","x.png");fail();}catch(IllegalArgumentException expected){}
        File outside=File.createTempFile("outside",".png");File link=new File(ProductionFiles.folder(c,"Captures"),"test-link.png");
        try{Files.createSymbolicLink(link.toPath(),outside.toPath());try{ProductionFiles.file(c,"Captures",link.getName());fail();}catch(java.io.IOException expected){}}
        finally{Files.deleteIfExists(link.toPath());outside.delete();}
    }
    @Test public void strictIntegersRejectCoercions()throws Exception{
        assertEquals(24,ProductionBridge.integer(new JSONObject(),"fps",1,120,24));
        for(Object value:new Object[]{true,"24",24.5}){
            try{ProductionBridge.integer(new JSONObject().put("fps",value),"fps",1,120,24);fail();}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void colorConversionKeepsNeutralBlackAndWhite(){
        assertArrayEquals(new int[]{16,128,128},ProductionVideoEncoder.yuv(0xff000000));
        assertArrayEquals(new int[]{235,128,128},ProductionVideoEncoder.yuv(0xffffffff));
        assertEquals(255,ProductionVideoEncoder.clamp(500));assertEquals(0,ProductionVideoEncoder.clamp(-100));
    }
    @Test public void referenceChunksAreChecksummedAndReplaySafe()throws Exception{
        Context c=RuntimeEnvironment.getApplication();
        java.io.ByteArrayOutputStream image=new java.io.ByteArrayOutputStream();
        android.graphics.Bitmap bitmap=android.graphics.Bitmap.createBitmap(2,2,android.graphics.Bitmap.Config.ARGB_8888);
        bitmap.compress(android.graphics.Bitmap.CompressFormat.PNG,100,image);bitmap.recycle();
        byte[] content=image.toByteArray();
        java.security.MessageDigest md=java.security.MessageDigest.getInstance("SHA-256");String digest=AgentPolicy.hex(md.digest(content));
        JSONObject p=new JSONObject().put("sha256",digest).put("extension","png").put("offset",0).put("total_bytes",content.length)
            .put("base64",android.util.Base64.encodeToString(content,android.util.Base64.NO_WRAP)).put("finish",true);
        JSONObject one=ProductionFiles.writeReference(c,p),two=ProductionFiles.writeReference(c,p);
        assertTrue(one.getBoolean("complete"));assertEquals(one.getString("sha256"),two.getString("sha256"));
        JSONObject metadata=StudioReferenceInbox.details(c,new JSONObject().put("asset",digest+".png"));
        assertEquals(2,metadata.getInt("width"));assertEquals(2,metadata.getInt("height"));
        ProductionFiles.file(c,"Assets",one.getString("filename")).delete();
        ProductionFiles.file(c,"Assets",digest+".meta.json").delete();
    }
}
