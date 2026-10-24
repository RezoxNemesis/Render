package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.File;
import java.io.FileOutputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * >10GB on-device animations: encode independently playable MP4 parts from
 * original checksum-proven PNG frames. Complete parts survive process/thermal
 * crashes; only the current incomplete part may need re-encoding.
 *
 * This does NOT claim a single 10GB MP4, or transcode/compress meshes to a
 * lower visual quality. A lossless JSON part-index and individual MP4s are
 * exported to Downloads. No cloud renderer or arbitrary path access.
 */
public final class ProductionSegmentedEncoder {
    private ProductionSegmentedEncoder(){}

    private static void save(File file,JSONObject data)throws Exception{
        File tmp=new File(file.getParentFile(),file.getName()+".tmp");
        try(FileOutputStream out=new FileOutputStream(tmp)){
            out.write(data.toString().getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        }
        Files.move(tmp.toPath(),file.toPath(),
            StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
    }

    static String partName(String job,int index){
        if(job==null||!job.matches("[a-f0-9]{32}")||index<0||index>100000)
            throw new IllegalArgumentException("INVALID_SEGMENT_IDENTIFIER");
        return String.format(java.util.Locale.ROOT,
            "Production_%s_part_%05d.mp4",job,index);
    }
    /**
     * Detect interrupted/truncated MP4 containers without decoding pixels or
     * scanning the Gallery. This is a structural check, NOT proof that the
     * phone's hardware decoder can play the video; encodeRange separately
     * verifies native metadata before recording the output receipt.
     */
    static boolean hasCompleteMp4Container(File file){
        if(file==null||!file.isFile()||file.length()<64)return false;
        try(RandomAccessFile input=new RandomAccessFile(file,"r")){
            long length=input.length(),offset=0;
            boolean ftyp=false,mdat=false,moovWithTrack=false;
            int boxes=0;
            while(offset<length){
                if(length-offset<8||++boxes>4096)return false;
                input.seek(offset);
                long bytes=Integer.toUnsignedLong(input.readInt());
                int type=input.readInt();
                long header=8;
                if(bytes==1){
                    if(length-offset<16)return false;
                    bytes=input.readLong();
                    header=16;
                }else if(bytes==0)bytes=length-offset;
                if(bytes<header||bytes>length-offset)return false;
                if(offset==0&&type!=0x66747970)return false; // ftyp
                if(type==0x66747970){ // ftyp, required as first box
                    if(offset!=0||bytes<16||bytes>4096)return false;
                    ftyp=true;
                }else if(type==0x6d646174){ // mdat
                    mdat|=bytes>header;
                }else if(type==0x6d6f6f76){ // moov
                    moovWithTrack|=containsTrack(input,offset+header,offset+bytes);
                }
                offset+=bytes;
            }
            return ftyp&&mdat&&moovWithTrack&&offset==length;
        }catch(Exception ignored){return false;}
    }

    private static boolean containsTrack(RandomAccessFile input,long start,long end)throws Exception{
        boolean track=false;
        int boxes=0;
        for(long offset=start;offset<end;){
            if(end-offset<8||++boxes>4096)return false;
            input.seek(offset);
            long bytes=Integer.toUnsignedLong(input.readInt());
            int type=input.readInt();
            long header=8;
            if(bytes==1){
                if(end-offset<16)return false;
                bytes=input.readLong();
                header=16;
            }else if(bytes==0)bytes=end-offset;
            if(bytes<header||bytes>end-offset)return false;
            if(type==0x7472616b&&bytes>header)track=true; // trak
            offset+=bytes;
        }
        return track;
    }

    static JSONObject readVerified(Context context,String job,JSONObject receipt){
        try{
            if(!job.matches("[a-f0-9]{32}")||receipt==null||
                !receipt.getString("filename").matches(
                    "Production_"+job+"_part_[0-9]{5}\\.mp4"))
                return null;
            File file=ProductionFiles.file(context,job,receipt.getString("filename"));
            if(file.isFile()&&file.length()==receipt.getLong("bytes")&&
                hasCompleteMp4Container(file)&&
                ProductionFiles.sha(file).equals(receipt.getString("sha256")))
                return receipt;
        }catch(Exception ignored){}
        return null;
    }

    /** Bind a prior receipt to the immutable segment plan as well as bytes. */
    static JSONObject readVerified(Context context,String job,JSONObject receipt,
                                   ProductionSegmentPlan.Span expected){
        if(expected==null||receipt==null||
            !partName(job,expected.index).equals(receipt.optString("filename"))||
            receipt.optInt("start_frame",-1)!=expected.start||
            receipt.optInt("end_frame",-1)!=expected.end||
            receipt.optInt("frames",-1)!=expected.count())
            return null;
        return readVerified(context,job,receipt);
    }

    private static void quarantineUnverified(Context context,String job,String filename)throws Exception{
        File output=ProductionFiles.file(context,job,filename);
        if(!output.isFile())return;
        String orphan=filename.substring(0,filename.length()-4)+".unverified.mp4";
        File backup=ProductionFiles.file(context,job,orphan);
        if(backup.exists())throw new IllegalStateException("UNVERIFIED_VIDEO_NEEDS_MANUAL_INSPECTION");
        Files.move(output.toPath(),backup.toPath(),StandardCopyOption.ATOMIC_MOVE);
    }

    public static JSONObject encode(Context context,String job,AtomicBoolean cancelled)throws Exception{
        File sourceFile=ProductionFiles.file(context,job,"manifest.json");
        JSONObject manifest=RenderManualJobs.readManifest(context,job);
        JSONObject spec=manifest.getJSONObject("spec");
        List<ProductionSegmentPlan.Span> spans=ProductionSegmentPlan.plan(spec);
        JSONObject previousVideo=manifest.optJSONObject("video");
        if("encoded".equals(manifest.optString("state"))&&
                previousVideo!=null&&previousVideo.optBoolean("segmented")){
            File index=ProductionFiles.file(context,job,previousVideo.getString("filename"));
            boolean indexValid=index.isFile()&&
                index.length()==previousVideo.optLong("bytes")&&
                ProductionFiles.sha(index).equals(previousVideo.getString("sha256"));
            JSONArray previousParts=previousVideo.optJSONArray("segments");
            boolean partsValid=indexValid&&previousParts!=null&&
                previousParts.length()==spans.size();
            if(partsValid)for(int i=0;i<previousParts.length();i++){
                if(readVerified(context,job,previousParts.optJSONObject(i),
                        spans.get(i))==null){
                    partsValid=false;break;
                }
            }
            if(partsValid)return previousVideo;
            // A valid index alone is not sufficient proof that its MP4 parts
            // survive a power cut or external storage corruption. Keep every
            // good part and selectively re-encode only absent/bad ones.
            manifest.put("state","frames_complete");
            save(sourceFile,manifest);
        }

        if(spans.size()<=1)throw new IllegalArgumentException("SEGMENTATION_NOT_REQUIRED");
        JSONObject receipts=manifest.optJSONObject("encoded_segments");
        if(receipts==null)receipts=new JSONObject();
        for(ProductionSegmentPlan.Span span:spans){
            if(cancelled.get())throw new IllegalStateException("NATIVE_ENCODING_CANCELLED");
            JSONObject telemetry=ProductionThermalTelemetry.sample(context);
            ProductionThermalPolicy.Decision gate=ProductionThermalPolicy.evaluate(
                telemetry.getInt("thermal_status"),telemetry.getBoolean("low_memory"),
                telemetry.getLong("available_memory_bytes"),false);
            if(!gate.renderAllowed)throw new IllegalStateException(gate.reason);
            if(RenderStorageBudget.freeBytes(context)<256L*1024*1024)
                throw new IllegalStateException("PAUSED_STORAGE_PRESSURE");

            String key=Integer.toString(span.index);
            String filename=partName(job,span.index);
            JSONObject receipt=readVerified(context,job,receipts.optJSONObject(key),span);
            if(receipt==null){
                quarantineUnverified(context,job,filename);
                receipt=ProductionVideoEncoder.encodeRange(context,job,cancelled,
                    filename,span.start,span.end,false);
                if(!filename.equals(receipt.getString("filename"))||
                    receipt.getInt("start_frame")!=span.start||
                    receipt.getInt("end_frame")!=span.end)
                    throw new IllegalStateException("SEGMENT_FRAME_RECEIPT_MISMATCH");
                manifest=RenderManualJobs.readManifest(context,job);
                receipts=manifest.optJSONObject("encoded_segments");
                if(receipts==null)receipts=new JSONObject();
                receipts.put(key,receipt);
                manifest.put("encoded_segments",receipts)
                    .put("state","frames_complete");
                save(sourceFile,manifest);
            }
        }
        JSONArray parts=new JSONArray();
        long totalBytes=0;
        for(ProductionSegmentPlan.Span span:spans){
            JSONObject receipt=readVerified(context,job,receipts.getJSONObject(
                Integer.toString(span.index)),span);
            if(receipt==null)throw new IllegalStateException("ENCODED_SEGMENT_HASH_MISMATCH");
            totalBytes=Math.addExact(totalBytes,receipt.getLong("bytes"));
            parts.put(receipt);
        }
        String indexName="Production_"+job+"_segments.json";
        File index=ProductionFiles.file(context,job,indexName);
        JSONObject contents=new JSONObject().put("format","RENDER_OMEGA_SEGMENTED_MP4_V1")
            .put("source_fingerprint",manifest.getString("fingerprint"))
            .put("spec",spec).put("segments",parts)
            .put("all_frames_encoded",true)
            .put("quality_reduced",false)
            .put("independent_mp4_parts",true)
            .put("single_monolithic_video",false);
        save(index,contents);
        JSONObject result=ProductionFiles.receipt(index,job)
            .put("mime_type","application/json")
            .put("segmented",true).put("segments",parts)
            .put("frames",spec.getInt("frame_count"))
            .put("parts_count",parts.length())
            .put("all_mp4_bytes",totalBytes)
            .put("all_mp4_containers_verified",true)
            .put("segment_frame_ranges_verified",true)
            .put("source_png_masters_retained",true)
            .put("quality_reduced",false);
        manifest=RenderManualJobs.readManifest(context,job);
        manifest.put("video",result).put("state","encoded");
        save(sourceFile,manifest);
        return result;
    }
}
