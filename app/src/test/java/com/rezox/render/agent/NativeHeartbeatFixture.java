package com.rezox.render.agent;

import android.content.Context;
import com.rezox.render.NativeEditorConfiguration;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import org.json.JSONObject;

/** Explicit fake native receipt for host tests; never evidence of bpy execution. */
final class NativeHeartbeatFixture {
    static File ready(Context context)throws Exception{
        File root=new File(context.getFilesDir(),"render_bpy_jobs");root.mkdirs();
        NativeEditorConfiguration.publish(context);
        File ready=new File(root,"ready");
        Files.write(ready.toPath(),Integer.toString(android.os.Process.myPid()).getBytes(StandardCharsets.US_ASCII));
        Files.write(new File(root,"ready-state.json").toPath(),new JSONObject()
            .put("pid",android.os.Process.myPid()).put("launch_id",NativeEditorConfiguration.launchId())
            .toString().getBytes(StandardCharsets.UTF_8));
        return ready;
    }
}
