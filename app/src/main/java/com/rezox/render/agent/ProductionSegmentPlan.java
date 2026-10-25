package com.rezox.render.agent;

import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;

/** Deterministic, no-reencode chunk plan for multi-GB on-device H.264 output.
 * The source remains exact signed PNG masters; only container boundaries
 * differ. Each independently playable MP4 is bounded by bitrate and time.
 */
public final class ProductionSegmentPlan {
    private ProductionSegmentPlan(){}
    public static final long TARGET_BYTES=768L*1024L*1024L;
    public static final int MAX_SECONDS=360;
    public static final class Span {
        public final int start,end,index;
        Span(int start,int end,int index){this.start=start;this.end=end;this.index=index;}
        public int count(){return end-start+1;}
    }
    public static List<Span> plan(JSONObject spec)throws Exception{
        int start=(int)ProductionBridge.integer(spec,"start",1,100000,-1);
        int end=(int)ProductionBridge.integer(spec,"end",start,100000,-1);
        int fps=(int)ProductionBridge.integer(spec,"fps",1,120,-1);
        int bitrate=(int)ProductionBridge.integer(spec,"bitrate",100000,200000000,-1);
        double fpsBase=spec.optDouble("fps_base",1.0);
        if(!Double.isFinite(fpsBase)||fpsBase<=0||fpsBase>100)
            throw new IllegalArgumentException("INVALID_FPS_BASE");
        double rate=fps/fpsBase;
        if(!Double.isFinite(rate)||rate<1||rate>120)
            throw new IllegalArgumentException("VIDEO_FPS_UNSUPPORTED");
        double estimatedPerFrame=Math.max(1.0,bitrate/(8.0*rate));
        long byteLimit=(long)Math.floor(TARGET_BYTES/estimatedPerFrame);
        long timeLimit=(long)Math.floor(MAX_SECONDS*rate);
        int maxFrames=(int)Math.max(1,Math.min(100000,Math.min(byteLimit,timeLimit)));
        ArrayList<Span> spans=new ArrayList<>();
        for(int i=start;i<=end;){
            int last=(int)Math.min((long)end,(long)i+maxFrames-1);
            spans.add(new Span(i,last,spans.size()));
            i=last+1;
        }
        return spans;
    }
    public static boolean segmented(JSONObject spec)throws Exception {
        return plan(spec).size()>1;
    }
}
