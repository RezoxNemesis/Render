package com.rezox.render.agent;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.Image;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaCodecList;
import android.media.MediaFormat;
import android.media.MediaMetadataRetriever;
import android.media.MediaMuxer;
import android.os.PowerManager;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.concurrent.atomic.AtomicBoolean;

/** On-device fallback independent of Blender FFmpeg. PNG masters are retained. */
public final class ProductionVideoEncoder {
    private ProductionVideoEncoder(){}
    public static boolean available(){
        try{for(MediaCodecInfo info:new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos())
            if(info.isEncoder())for(String type:info.getSupportedTypes())if(type.equalsIgnoreCase("video/avc"))return true;
        }catch(Exception ignored){}return false;
    }
    private static void write(File file,JSONObject data)throws Exception {
        File tmp=new File(file.getParentFile(),file.getName()+".tmp");
        try(FileOutputStream out=new FileOutputStream(tmp)){out.write(data.toString().getBytes(StandardCharsets.UTF_8));out.getFD().sync();}
        Files.move(tmp.toPath(),file.toPath(),StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }
    /** MP4 sample timestamps use Blender fps/fps_base, not rounded fps.
     * MediaCodec KEY_FRAME_RATE is only a rate-control hint; muxed PTS
     * determines actual display timing, which still needs a device test. */
    public static long framePresentationTimeUs(int zeroBasedFrame, int fps, double fpsBase){
        if(zeroBasedFrame<0||fps<1||fps>120||!Double.isFinite(fpsBase)||
           fpsBase<=0.0||fpsBase>100.0)
            throw new IllegalArgumentException("INVALID_FPS_TIMING");
        return Math.round(zeroBasedFrame*(1_000_000.0*fpsBase/fps));
    }
    static int clamp(int value){return Math.max(0,Math.min(255,value));}
    static int[] yuv(int argb){int r=(argb>>16)&255,g=(argb>>8)&255,b=argb&255;
        return new int[]{clamp(((66*r+129*g+25*b+128)>>8)+16),clamp(((-38*r-74*g+112*b+128)>>8)+128),clamp(((112*r-94*g-18*b+128)>>8)+128)};
    }
    private static void put(Image.Plane plane,int x,int y,int value){
        ByteBuffer buffer=plane.getBuffer();int offset=buffer.position()+y*plane.getRowStride()+x*plane.getPixelStride();
        if(offset<0||offset>=buffer.limit())throw new IllegalStateException("ENCODER_PLANE_LAYOUT_UNSUPPORTED");buffer.put(offset,(byte)value);
    }
    private static void fill(Bitmap bitmap,Image image){
        int width=bitmap.getWidth(),height=bitmap.getHeight();
        if(image.getWidth()!=width||image.getHeight()!=height||image.getPlanes().length!=3)throw new IllegalStateException("ENCODER_IMAGE_LAYOUT_UNSUPPORTED");
        int[] pixels=new int[width*height];bitmap.getPixels(pixels,0,width,0,0,width,height);
        Image.Plane[] planes=image.getPlanes();
        for(int y=0;y<height;y+=2)for(int x=0;x<width;x+=2){
            int u=0,v=0;
            for(int dy=0;dy<2;dy++)for(int dx=0;dx<2;dx++){int[] c=yuv(pixels[(y+dy)*width+x+dx]);put(planes[0],x+dx,y+dy,c[0]);u+=c[1];v+=c[2];}
            put(planes[1],x/2,y/2,(u+2)/4);put(planes[2],x/2,y/2,(v+2)/4);
        }
    }
    public static JSONObject encode(Context context,String jobId,AtomicBoolean cancelled)throws Exception{
        JSONObject manifest=RenderManualJobs.readManifest(context,jobId);
        if(ProductionSegmentPlan.segmented(manifest.getJSONObject("spec")))
            return ProductionSegmentedEncoder.encode(context,jobId,cancelled);
        return encodeRange(context,jobId,cancelled,null,-1,-1,true);
    }

    /** Encode an exact absolute frame interval; parent manifest remains the
     * source of truth. Segments never consume duplicate JPEG/PNG source frames.
     * The original frame range and requested codec settings are preserved. */
    static JSONObject encodeRange(Context context,String jobId,AtomicBoolean cancelled,
                                  String targetName,int rangeStart,int rangeEnd,
                                  boolean finalizeJob)throws Exception {
        File manifestFile=ProductionFiles.file(context,jobId,"manifest.json");
        if(!manifestFile.isFile()||manifestFile.length()>16*1024*1024)throw new IllegalArgumentException("RENDER_MANIFEST_UNAVAILABLE");
        JSONObject manifest=new JSONObject(new String(Files.readAllBytes(manifestFile.toPath()),StandardCharsets.UTF_8));
        JSONObject spec=manifest.getJSONObject("spec"),frames=manifest.getJSONObject("frames");
        int width=(int)ProductionBridge.integer(spec,"width",16,8192,-1),height=(int)ProductionBridge.integer(spec,"height",16,8192,-1);
        int fps=(int)ProductionBridge.integer(spec,"fps",1,120,-1),start=(int)ProductionBridge.integer(spec,"start",1,100000,-1),end=(int)ProductionBridge.integer(spec,"end",start,100000,-1);
        int total=end-start+1,bitrate=(int)ProductionBridge.integer(spec,"bitrate",100000,200000000,16000000);
        if(rangeStart<0)rangeStart=start;
        if(rangeEnd<0)rangeEnd=end;
        if(rangeStart<start||rangeEnd>end||rangeEnd<rangeStart)
            throw new IllegalArgumentException("ENCODE_RANGE_OUTSIDE_FROZEN_PROJECT");
        int count=rangeEnd-rangeStart+1;
        double fpsBase=spec.optDouble("fps_base",1.0);
        if(!Double.isFinite(fpsBase)||fpsBase<=0||fpsBase>100)
            throw new IllegalArgumentException("INVALID_FPS_BASE");
        double requestedFps=fps/fpsBase;
        if(requestedFps<1||requestedFps>120)
            throw new IllegalArgumentException("REQUESTED_FPS_UNSUPPORTED_BY_MEDIACODEC");
        if((width&1)!=0||(height&1)!=0||frames.length()!=total)
            throw new IllegalArgumentException("RENDER_FRAMES_INCOMPLETE");
        String filename=targetName==null?"Production_"+jobId+".mp4":targetName;
        File output=ProductionFiles.file(context,jobId,filename);
        JSONObject prior=manifest.optJSONObject("video");
        // Hash equality alone is insufficient after a crash: require an
        // intact MP4 container and an exact receipt for the frozen frame span.
        if(finalizeJob&&"encoded".equals(manifest.optString("state"))&&prior!=null&&
           output.isFile()&&prior.optInt("frames",-1)==count&&
           prior.optInt("start_frame",-1)==rangeStart&&
           prior.optInt("end_frame",-1)==rangeEnd&&
           filename.equals(prior.optString("filename"))&&
           ProductionSegmentedEncoder.hasCompleteMp4Container(output)&&
           ProductionFiles.sha(output).equals(prior.optString("sha256")))
            return prior;
        if(output.exists())throw new IllegalStateException("VIDEO_OUTPUT_CONFLICT");
        MediaFormat format=MediaFormat.createVideoFormat("video/avc",width,height);
        format.setInteger(MediaFormat.KEY_BIT_RATE,bitrate);
        // Integer codec rate is a configuration hint. Fractional cadence is
        // carried precisely in the PTS assigned to each actual PNG frame.
        format.setInteger(MediaFormat.KEY_FRAME_RATE,(int)Math.round(requestedFps));format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL,1);
        format.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible);
        format.setInteger(MediaFormat.KEY_COLOR_STANDARD,MediaFormat.COLOR_STANDARD_BT601_NTSC);
        format.setInteger(MediaFormat.KEY_COLOR_RANGE,MediaFormat.COLOR_RANGE_LIMITED);
        String codecName=new MediaCodecList(MediaCodecList.REGULAR_CODECS).findEncoderForFormat(format);
        if(codecName==null)throw new IllegalStateException("REQUESTED_H264_FORMAT_UNAVAILABLE");
        JSONObject device=ProductionBridge.profile(context);
        long required=(long)width*height*16+128L*1024*1024;
        if(device.optBoolean("low_memory")||device.getLong("available_memory_bytes")<required)throw new IllegalStateException("PAUSED_MEMORY_PRESSURE");
        File partial=ProductionFiles.file(context,jobId,
            filename.substring(0,filename.length()-4)+".partial.mp4");if(partial.exists()&&!partial.delete())throw new IllegalStateException("PARTIAL_VIDEO_RECOVERY_FAILED");
        MediaCodec codec=null;MediaMuxer muxer=null;boolean codecStarted=false,muxerStarted=false,success=false;
        int track=-1,inputFrame=0,outputSamples=0;boolean inputEnded=false,outputEnded=false;
        long lastProgress=SystemClock.elapsedRealtime();
        manifest.put("state","encoding");write(manifestFile,manifest);
        try{
            codec=MediaCodec.createByCodecName(codecName);codec.configure(format,null,null,MediaCodec.CONFIGURE_FLAG_ENCODE);codec.start();codecStarted=true;
            muxer=new MediaMuxer(partial.getAbsolutePath(),MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
            MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
            while(!outputEnded){
                if(cancelled.get())throw new IllegalStateException("NATIVE_ENCODING_CANCELLED");
                PowerManager pm=context.getSystemService(PowerManager.class);
                if(pm!=null&&pm.getCurrentThermalStatus()>=PowerManager.THERMAL_STATUS_SEVERE)throw new IllegalStateException("PAUSED_THERMAL_PRESSURE");
                if(SystemClock.elapsedRealtime()-lastProgress>60000)throw new IllegalStateException("NATIVE_ENCODER_STALLED");
                if(!inputEnded){
                    int index=codec.dequeueInputBuffer(10000);
                    if(index>=0){
                        long pts=framePresentationTimeUs(inputFrame,fps,fpsBase);
                        if(inputFrame==count){codec.queueInputBuffer(index,0,0,pts,MediaCodec.BUFFER_FLAG_END_OF_STREAM);inputEnded=true;}
                        else{
                            JSONObject receipt=frames.getJSONObject(Integer.toString(rangeStart+inputFrame));File frame=ProductionFiles.file(context,jobId,receipt.getString("filename"));
                            if(!frame.isFile()||frame.length()!=receipt.getLong("bytes")||!ProductionFiles.sha(frame).equals(receipt.getString("sha256")))throw new IllegalStateException("FRAME_HASH_MISMATCH");
                            BitmapFactory.Options options=new BitmapFactory.Options();options.inPreferredConfig=Bitmap.Config.ARGB_8888;
                            Bitmap bitmap=BitmapFactory.decodeFile(frame.getAbsolutePath(),options);
                            if(bitmap==null)throw new IllegalStateException("FRAME_DECODE_FAILED");
                            try{
                                if(bitmap.getWidth()!=width||bitmap.getHeight()!=height)throw new IllegalStateException("FRAME_DIMENSIONS_MISMATCH");
                                Image image=codec.getInputImage(index);if(image==null)throw new IllegalStateException("ENCODER_FLEXIBLE_IMAGE_UNAVAILABLE");
                                try{ProductionYuv.fill(bitmap,image);}finally{image.close();}
                            }finally{bitmap.recycle();}
                            codec.queueInputBuffer(index,0,width*height*3/2,pts,0);inputFrame++;lastProgress=SystemClock.elapsedRealtime();
                        }
                    }
                }
                int out=codec.dequeueOutputBuffer(info,10000);
                if(out==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){
                    if(muxerStarted)throw new IllegalStateException("ENCODER_FORMAT_CHANGED_TWICE");track=muxer.addTrack(codec.getOutputFormat());muxer.start();muxerStarted=true;
                }else if(out>=0){
                    ByteBuffer buffer=codec.getOutputBuffer(out);
                    if((info.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)!=0)info.size=0;
                    if(info.size>0){
                        if(!muxerStarted||buffer==null)throw new IllegalStateException("ENCODER_OUTPUT_UNAVAILABLE");
                        buffer.position(info.offset);buffer.limit(info.offset+info.size);muxer.writeSampleData(track,buffer,info);outputSamples++;lastProgress=SystemClock.elapsedRealtime();
                    }
                    outputEnded=(info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0;codec.releaseOutputBuffer(out,false);
                }
            }
            if(inputFrame!=count||outputSamples!=count||!muxerStarted)throw new IllegalStateException("ENCODER_FRAME_COUNT_MISMATCH");
            codec.stop();codecStarted=false;codec.release();codec=null;muxer.stop();muxerStarted=false;muxer.release();muxer=null;
            MediaMetadataRetriever verify=new MediaMetadataRetriever();
            try{
                verify.setDataSource(partial.getAbsolutePath());
                if(Integer.parseInt(verify.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH))!=width||Integer.parseInt(verify.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT))!=height)throw new IllegalStateException("VIDEO_DIMENSIONS_MISMATCH");
            }finally{verify.release();}
            if(partial.length()<512||
               !ProductionSegmentedEncoder.hasCompleteMp4Container(partial))
                throw new IllegalStateException("VIDEO_CONTAINER_INCOMPLETE");
            Files.move(partial.toPath(),output.toPath(),StandardCopyOption.ATOMIC_MOVE);
            JSONObject result=ProductionFiles.receipt(output,jobId).put("mime_type","video/mp4").put("frames",count).put("fps",fps).put("width",width).put("height",height).put("bitrate",bitrate)
                .put("fps_base",fpsBase).put("requested_effective_fps",requestedFps)
                .put("device_fractional_fps_verified",false)
                .put("encoder",codecName).put("executed_by","Android MediaCodec from native Blender PNG masters")
                .put("png_masters_retained",true).put("resolution_reduced",false)
                .put("mp4_container_verified",true)
                .put("start_frame",rangeStart).put("end_frame",rangeEnd);
            if(finalizeJob){
                manifest.put("video",result).put("state","encoded");
            }else manifest.put("state","frames_complete");
            write(manifestFile,manifest);success=true;return result;
        }finally{
            if(codec!=null){try{if(codecStarted)codec.stop();}catch(Exception ignored){}codec.release();}
            if(muxer!=null){try{if(muxerStarted)muxer.stop();}catch(Exception ignored){}muxer.release();}
            if(!success){partial.delete();manifest.put("state","frames_complete");write(manifestFile,manifest);}
        }
    }
}
