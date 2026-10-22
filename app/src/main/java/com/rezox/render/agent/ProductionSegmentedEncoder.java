package com.rezox.render.agent;

import android.content.Context;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.File;
import java.io.FileOutputStream;
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
    static JSONObject readVerified(Context context,String job,JSONObject receipt){
        try{
            if(receipt==null||!receipt.getString("filename").matches(
                    "Production_[a-f0-9]{32}_part_[0-9]{5}\\.mp4"))
                return null;
            File file=ProductionFiles.file(context,job,receipt.getString("filename"));
            if(file.isFile()&&file.length()==receipt.getLong("bytes")&&
                ProductionFiles.sha(file).equals(receipt.getString("sha256")))
                return receipt;
        }catch(Exception ignored){}
        return null;
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
        JSONObject previousVideo=manifest.optJSONObject("video");
        if("encoded".equals(manifest.optString("state"))&&
                previousVideo!=null&&previousVideo.optBoolean("segmented")){
            File index=ProductionFiles.file(context,job,previousVideo.getString("filename"));
            if(index.isFile()&&index.length()==previousVideo.optLong("bytes")&&
                ProductionFiles.sha(index).equals(previousVideo.getString("sha256")))
                return previousVideo;
        }

        List<ProductionSegmentPlan.Span> spans=ProductionSegmentPlan.plan(spec);
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
            JSONObject receipt=readVerified(context,job,receipts.optJSONObject(key));
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
                Integer.toString(span.index)));
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
            .put("source_png_masters_retained",true)
            .put("quality_reduced",false);
        manifest=RenderManualJobs.readManifest(context,job);
        manifest.put("video",result).put("state","encoded");
        save(sourceFile,manifest);
        return result;
    }
}
