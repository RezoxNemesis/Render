package com.rezox.render.agent;
import org.junit.Test;
import java.util.Collections;
import java.util.HashSet;
import java.util.Arrays;
import static org.junit.Assert.*;

public class AgentPolicyTest {
    @Test public void validHttpsOrigin(){assertEquals("https://relay.example",AgentPolicy.relayUrl("https://relay.example/"));}
    @Test public void rejectsCleartextCredentialsAndPath(){
        for(String value:new String[]{"http://relay.example","https://user:pass@relay.example","https://relay.example/path","https://relay.example?token=x","https://relay.example#x","https://relay.example:0"}) {
            try{AgentPolicy.relayUrl(value);fail(value);}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void registryExposesOnlyRealHandlers(){
        assertEquals(9,AgentPolicy.ACTIONS.size());
        assertFalse(AgentPolicy.ACTIONS.containsKey("cycles.render"));
        assertFalse(AgentPolicy.ACTIONS.containsKey("shell.exec"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.summary"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.add_cube"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.scene.set_frame"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.set_transform"));
        assertTrue(AgentPolicy.ACTIONS.containsKey("blender.object.keyframe"));
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
