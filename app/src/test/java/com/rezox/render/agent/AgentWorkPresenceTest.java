package com.rezox.render.agent;
import org.junit.Test;
import static org.junit.Assert.*;

/** Only native terminal states may be described as completed work. */
public class AgentWorkPresenceTest {
    @Test public void runningShowsAnHonestNativeAction(){
        AgentWorkPresence.Snapshot state=new AgentWorkPresence.Snapshot(
                "running","blender.scene.render_video","Rendering frame 8 of 192",
                "VideoStudio MCP v3 Binder",100,200,4);
        assertTrue(state.isWorking());
        assertFalse(state.needsRecovery());
        assertTrue(state.description().contains("render_video"));
        assertTrue(state.description().contains("4%"));
    }
    @Test public void unconfirmedOrInterruptedNeverShowsSuccess(){
        AgentWorkPresence.Snapshot lost=new AgentWorkPresence.Snapshot(
                "recovery_required","blender.project.save_copy","", "",100,200,-1);
        assertFalse(lost.isWorking());
        assertTrue(lost.needsRecovery());
        assertTrue(lost.description().contains("interrupted"));
        AgentWorkPresence.Snapshot idle=new AgentWorkPresence.Snapshot(
                "idle","","","",0,0,-1);
        assertFalse(idle.isWorking());
        assertFalse(idle.description().contains("Working in Blender"));
    }
}
