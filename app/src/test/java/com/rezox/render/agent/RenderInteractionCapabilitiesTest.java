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
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import static org.junit.Assert.*;

/** Tests Render's production dispatch against Android host fixtures only. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class RenderInteractionCapabilitiesTest {
    private JSONObject capabilities(Context context)throws Exception{
        return ProductionBridge.execute(context,new JSONObject().put("operation","capabilities")
            .put("payload",new JSONObject()),new AtomicBoolean(false));
    }
    @Test public void advertisesActualInteractionCaptureAndRenderOperations()throws Exception{
        Context c=RuntimeEnvironment.getApplication();JSONObject report=capabilities(c);
        JSONArray ops=report.getJSONArray("operations");Set<String> available=new HashSet<>();
        for(int i=0;i<ops.length();i++)available.add(ops.getString(i));
        for(String op:new String[]{"ui.state","scene.inspect","viewport.inspect","viewport.focus",
            "operator.describe","operator.execute","screenshot.capture","project.checkpoint",
            "reference.workspace.open","reference.workspace.inspect","reference.compare.multiview","reference.fit.landmarks","reference.fit.multiview",
            "animation.clip.create","animation.clip.inspect","animation.motion.audit",
            "studio.capabilities","studio.tool.search","studio.workspace.activate","studio.workspace.inspect",
            "studio.view.orbit","studio.editor.open","studio.sculpt.inspect","studio.sculpt.brush",
            "studio.pose.inspect","studio.pose.key","studio.timeline.scrub",
            "studio.ik.create","studio.ik.inspect","studio.ik.target","studio.ik.blend",
            "studio.reference.timeline.bind","studio.reference.timeline.inspect","studio.reference.timeline.scrub",
            "studio.curve.inspect","studio.curve.adjust",
            "studio.agent.bootstrap","studio.agent.batch.inspect",
            "studio.agent.plan.preview","studio.agent.metrics","studio.agent.status",
            "studio.preview.capabilities","studio.preview.inspect",
            "studio.preview.diagnose","studio.preview.profile.apply",
            "studio.preview.profile.restore","studio.preview.aa.inspect",
            "studio.preview.aa.configure",
            "studio.preview.sampling.inspect","studio.preview.sampling.configure",
            "studio.benchmark.catalog","studio.benchmark.audit","studio.mesh.bridge_loops","studio.procedural.scatter","studio.material.surface","studio.motion.action.create","studio.motion.nla.create","studio.compositor.grade","studio.compositor.inspect","studio.sim.rigidbody","studio.drawing.strokes",
            "studio.plan.submit","studio.plan.status",
            "studio.plan.list","studio.plan.pause","studio.plan.resume","studio.plan.cancel","studio.activity",
            "render.plan","render.batch","render.status","render.encode"})assertTrue(op,available.contains(op));
        assertTrue(report.getBoolean("requires_target_id"));assertFalse(report.getBoolean("cloud_rendering"));
        assertFalse(report.getBoolean("visual_quality_verified"));
    }
    @Test public void fixtureHeartbeatControlsReadinessWithoutProvingEngineExecution()throws Exception{
        Context c=RuntimeEnvironment.getApplication();File ready=new File(c.getFilesDir(),"render_bpy_jobs/ready");
        ready.getParentFile().mkdirs();Files.deleteIfExists(ready.toPath());
        assertFalse(capabilities(c).getBoolean("native_editor_ready"));
        NativeHeartbeatFixture.ready(c);
        Files.write(ready.toPath(),Integer.toString(android.os.Process.myPid()).getBytes(java.nio.charset.StandardCharsets.US_ASCII));
        assertTrue(capabilities(c).getBoolean("native_editor_ready"));
        assertTrue(ready.setLastModified(System.currentTimeMillis()-20000));
        assertFalse(capabilities(c).getBoolean("native_editor_ready"));Files.delete(ready.toPath());
    }
    @Test public void uiStateRequiresCurrentRenderTargetIdentity()throws Exception{
        Context c=RuntimeEnvironment.getApplication();JSONObject args=new JSONObject()
            .put("operation","ui.state").put("payload",new JSONObject())
            .put("target_id","00000000-0000-0000-0000-000000000000");
        try{ProductionBridge.execute(c,args,new AtomicBoolean(false));fail();}
        catch(IllegalArgumentException expected){assertEquals("RENDER_TARGET_ID_REQUIRED_OR_MISMATCH",expected.getMessage());}
        args.put("target_id",new AgentSecrets(c).renderPublicId());
        JSONObject ui=ProductionBridge.execute(c,args,new AtomicBoolean(false));
        assertFalse(ui.getBoolean("fabricated_ui_taps"));assertFalse(ui.getBoolean("unrelated_apps_controlled"));
    }
}
