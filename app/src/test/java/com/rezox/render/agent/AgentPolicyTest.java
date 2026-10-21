package com.rezox.render.agent;
import org.junit.Test;
import java.util.Collections;
import java.util.HashSet;
import java.util.Arrays;
import static org.junit.Assert.*;

public class AgentPolicyTest {
    @Test public void validHttpsOrigin(){assertEquals("https://relay.example",AgentPolicy.relayUrl("https://relay.example/"));}
    @Test public void missingRelayGetsExplicitSetupMessage() {
        for(String origin:new String[]{"", "   "}) {
            try{AgentPolicy.relayUrl(origin);fail();}
            catch(IllegalArgumentException expected){assertTrue(expected.getMessage().contains("Relay address required"));}
        }
        try{AgentPolicy.relayUrl(null);fail();}
        catch(IllegalArgumentException expected){assertTrue(expected.getMessage().contains("Relay address required"));}
    }
    @Test public void rejectsCleartextCredentialsAndPath(){
        for(String value:new String[]{"http://relay.example","https://user:pass@relay.example","https://relay.example/path","https://relay.example?token=x","https://relay.example#x","https://relay.example:0"}) {
            try{AgentPolicy.relayUrl(value);fail(value);}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void registryExposesOnlyRealHandlers(){
        assertEquals(20,AgentPolicy.ACTIONS.size());
        assertFalse(AgentPolicy.ACTIONS.containsKey("cycles.render"));
        assertFalse(AgentPolicy.ACTIONS.containsKey("shell.exec"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.summary"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.add_cube"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.set_frame"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.set_transform"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.keyframe"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.project.save_copy"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.add_primitive"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.add_camera"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.add_light"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.modifier_add"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.material.assign"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.render_settings"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.render_still"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.project.restore_scene"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.populate_lively"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.render_video"));
    }
    @Test public void validReadCommand(){AgentPolicy.validate("command-1",1,"engine.status",Collections.emptySet());}
    @Test public void acceptsTypedBpyCommandsButNoPythonShell(){
        AgentPolicy.validate("id-1",1,"blender.scene.summary",Collections.emptySet());
        AgentPolicy.validate("id-2",1,"blender.object.add_cube",new HashSet<>(Arrays.asList("name","location","size")));
        try{AgentPolicy.validate("id-3",1,"blender.object.add_cube",Collections.singleton("code"));fail();}
        catch(IllegalArgumentException expected){}
        AgentPolicy.validate("key-1",1,"blender.object.keyframe",new HashSet<>(Arrays.asList("name","data_path","frame","value")));
        AgentPolicy.validate("move-1",1,"blender.object.set_transform",new HashSet<>(Arrays.asList("name","location","scale")));
        AgentPolicy.validate("frame-1",1,"blender.scene.set_frame",Collections.singleton("frame"));
        AgentPolicy.validate("snapshot-1",1,"blender.project.save_copy",Collections.emptySet());
        AgentPolicy.validate("restore-1",1,"blender.project.restore_scene",
            new HashSet<>(Arrays.asList("project_id","expected_sha256")));
        AgentPolicy.validate("scenery-1",1,"blender.scene.populate_lively",Collections.emptySet());
        AgentPolicy.validate("video-1",1,"blender.scene.render_video",Collections.emptySet());
        try {
            AgentPolicy.validate("restore-2",1,"blender.project.restore_scene",Collections.emptySet());
            fail("Must require an opaque project ID");
        } catch(IllegalArgumentException expected){}
        try {
            AgentPolicy.validate("video-2",1,"blender.scene.render_video",Collections.singleton("shell"));
            fail("No arbitrary paths/commands allowed");
        } catch(IllegalArgumentException expected){} 
        try{AgentPolicy.validate("id-4",1,"python.eval",Collections.emptySet());fail();}
        catch(IllegalArgumentException expected){}
    }
    @Test public void refusesUnsupportedAndExtraFields(){
        try{AgentPolicy.validate("x",1,"cycles.render",Collections.emptySet());fail();}catch(IllegalArgumentException expected){}
        try{AgentPolicy.validate("x",2,"engine.status",Collections.emptySet());fail();}catch(IllegalArgumentException expected){}
        try{AgentPolicy.validate("x",1,"engine.status",Collections.singleton("path"));fail();}catch(IllegalArgumentException expected){}
    }
    @Test public void inspectionRequiresOpaqueProjectId(){
        try{AgentPolicy.validate("x",1,"projects.inspect",Collections.emptySet());fail();}catch(IllegalArgumentException expected){}
        AgentPolicy.validate("x",1,"projects.inspect",new HashSet<>(Arrays.asList("project_id","expected_sha256")));
    }
    @Test public void requestIdCannotContainPaths(){
        for(String id:new String[]{"","../../a","a/b","a b"}){
            try{AgentPolicy.validate(id,1,"engine.status",Collections.emptySet());fail();}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void hashMatchesKnownVector(){assertEquals("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",AgentPolicy.sha256("abc"));}
}
