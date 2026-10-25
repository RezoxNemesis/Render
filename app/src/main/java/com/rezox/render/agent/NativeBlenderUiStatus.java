package com.rezox.render.agent;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

/** App-owned, one-way status for Blender's own viewport HUD. No input commands,
 * owner credentials, project paths or network listener cross this boundary. */
final class NativeBlenderUiStatus {
    private NativeBlenderUiStatus(){}
    static void write(Context context,AgentWorkPresence.Snapshot state){
        FileOutputStream stream=null;AtomicFile atomic=null;
        try{
            File path=new File(ProductionFiles.root(context),"native_ui_status.json");
            if(Files.isSymbolicLink(path.toPath())||Files.isSymbolicLink(new File(path+".new").toPath())||
                    Files.isSymbolicLink(new File(path+".bak").toPath()))return;
            JSONObject data=new JSONObject().put("state",state.state).put("action",state.displayAction())
                .put("stage",state.displayStage()).put("progress",state.progress)
                .put("updated_at_epoch_ms",state.updatedAt).put("source","Render Android native worker");
            byte[] bytes=data.toString().getBytes(StandardCharsets.UTF_8);
            if(bytes.length>4096)return;
            atomic=new AtomicFile(path);stream=atomic.startWrite();stream.write(bytes);
            atomic.finishWrite(stream);stream=null;
        }catch(Exception ignored){
            if(atomic!=null&&stream!=null)atomic.failWrite(stream);
            // Optional UI telemetry must never abort a Blender command.
        }
    }
}
