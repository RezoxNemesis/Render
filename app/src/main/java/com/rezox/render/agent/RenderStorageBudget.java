package com.rezox.render.agent;

import android.content.Context;
import android.os.StatFs;
import org.json.JSONObject;

/**
 * Non-destructive disk admission for long full-quality Blender renders.
 * PNG masters + a future MP4 can exceed 10 GB; all arithmetic is long/double,
 * never an int or a full-animation in-memory byte array.
 * Estimates are NOT an unsupported guarantee that a 10 GB single MP4 muxes.
 */
public final class RenderStorageBudget {
    private static final long MiB=1024L*1024L;
    private static final long RESERVE=256L*MiB;
    private static final long SEGMENT_TARGET=768L*MiB;
    private RenderStorageBudget(){}

    public static JSONObject estimate(JSONObject spec,long availableBytes)throws Exception{
        int width=(int)ProductionBridge.integer(spec,"width",16,8192,-1);
        int height=(int)ProductionBridge.integer(spec,"height",16,8192,-1);
        int count=(int)ProductionBridge.integer(spec,"frame_count",1,100000,-1);
        int fps=(int)ProductionBridge.integer(spec,"fps",1,120,-1);
        long bitrate=ProductionBridge.integer(spec,"bitrate",100000,200000000,16000000);
        double fpsBase=spec.optDouble("fps_base",1.0);
        if((width&1)!=0||(height&1)!=0||!Double.isFinite(fpsBase)||
                fpsBase<=0||fpsBase>100||availableBytes<0)
            throw new IllegalArgumentException("INVALID_RENDER_STORAGE_SPEC");

        long frameRgba=Math.multiplyExact(Math.multiplyExact((long)width,height),4L);
        long nominalRaw=Math.multiplyExact(frameRgba,(long)count);
        double videoBytes=(bitrate/8.0)*(count*fpsBase/fps);
        if(!Double.isFinite(videoBytes)||videoBytes>Long.MAX_VALUE/2)
            throw new IllegalArgumentException("INVALID_RENDER_STORAGE_ESTIMATE");
        long videoEstimate=(long)Math.ceil(videoBytes);
        // A PNG can be smaller OR larger than raw RGBA due to compression
        // or metadata. This is a planning number, not a disk quota cap.
        long requiredForNextFrame=Math.addExact(
            Math.multiplyExact(frameRgba,2L),RESERVE);
        long projectedTotal=Math.addExact(Math.addExact(nominalRaw,videoEstimate),RESERVE);
        // Estimate a small enough set of MP4 chunks to avoid large-offset
        // assumptions and make encoder restarts cheap; this does not
        // advertise a segmented muxer as installed.
        long nominalSegments=Math.max(1,(videoEstimate+SEGMENT_TARGET-1)/SEGMENT_TARGET);
        return new JSONObject()
            .put("available_bytes",availableBytes)
            .put("minimum_for_next_frame_bytes",requiredForNextFrame)
            .put("can_render_next_frame",availableBytes>=requiredForNextFrame)
            .put("nominal_raw_frame_bytes",frameRgba)
            .put("nominal_uncompressed_animation_bytes",nominalRaw)
            .put("nominal_video_bytes",videoEstimate)
            .put("estimated_total_with_reserve_bytes",projectedTotal)
            .put("estimated_segment_count",nominalSegments)
            .put("segmenting_required_for_reliability",nominalSegments>1)
            .put("streaming_not_whole_animation_in_memory",true)
            .put("large_single_mp4_muxer_verified",false)
            .put("admission_is_not_capacity_guarantee",true)
            .put("storage_bytes_are_not_thermal_readings",true)
            .put("render_quality_reduced",false);
    }

    public static JSONObject forJob(Context context,String jobId)throws Exception{
        JSONObject manifest=RenderManualJobs.readManifest(context,jobId);
        return estimate(manifest.getJSONObject("spec"),freeBytes(context));
    }

    public static long freeBytes(Context context){
        return new StatFs(context.getFilesDir().getAbsolutePath()).getAvailableBytes();
    }

    public static boolean frameSpaceAvailable(Context context,String jobId)throws Exception{
        return forJob(context,jobId).getBoolean("can_render_next_frame");
    }
}
