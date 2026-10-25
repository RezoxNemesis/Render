package com.rezox.render.agent;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.File;
import java.io.FileOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

/** Durable original-byte transfers, independent of Blender readiness. No account tokens or Gallery enumeration. */
public final class FileTransfers {
    public static final long MAX_BYTES=4L*1024*1024*1024;
    private static final Object LOCK=new Object();
    private static final ConcurrentHashMap<String,String> CONTROL=new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String,Boolean> ACTIVE=new ConcurrentHashMap<>();
    private FileTransfers(){}
    private static File folder(Context c)throws Exception{
        File f=new File(c.getFilesDir(),"FileTransfers");
        if(Files.isSymbolicLink(f.toPath())||(!f.isDirectory()&&!f.mkdirs()))throw new IOException("TRANSFER_STORAGE_UNAVAILABLE");
        return f;
    }
    private static File task(Context c,String id)throws Exception{
        if(id==null||!id.matches("[a-f0-9]{32}"))throw new IllegalArgumentException("INVALID_TRANSFER_ID");
        return new File(folder(c),id+".json");
    }
    static void syncDirectory(File f)throws Exception{
        try(FileChannel channel=FileChannel.open(f.toPath(),StandardOpenOption.READ)){channel.force(true);}
    }
    private static JSONObject load(Context c,String id)throws Exception{
        AtomicFile f=new AtomicFile(task(c,id));
        try(InputStream input=f.openRead()){
            ByteArrayOutputStream data=new ByteArrayOutputStream();byte[] buffer=new byte[4096];int n;
            while((n=input.read(buffer))!=-1){if(data.size()+n>32768)throw new IOException("TRANSFER_STATE_CORRUPT");data.write(buffer,0,n);}
            byte[] bytes=data.toByteArray();
            return new JSONObject(new String(bytes,StandardCharsets.UTF_8));
        }
    }
    private static void save(Context c,JSONObject value)throws Exception{
        AtomicFile atomic=new AtomicFile(task(c,value.getString("transfer_id")));
        FileOutputStream out=atomic.startWrite();
        try{out.write(value.toString().getBytes(StandardCharsets.UTF_8));atomic.finishWrite(out);syncDirectory(folder(c));}
        catch(Exception error){atomic.failWrite(out);throw error;}
    }
    private static String canonical(JSONObject p)throws Exception{
        ArrayList<String> keys=new ArrayList<>();p.keys().forEachRemaining(keys::add);Collections.sort(keys);
        StringBuilder out=new StringBuilder();
        for(String key:keys){
            Object value=p.get(key);
            if(!(value instanceof String)&&!(value instanceof Number)&&!(value instanceof Boolean)&&value!=JSONObject.NULL)
                throw new IllegalArgumentException("TRANSFER_ARGUMENT_REQUIRES_SCALAR");
            out.append(JSONObject.quote(key)).append(':').append(value instanceof String?JSONObject.quote((String)value):String.valueOf(value)).append(';');
        }
        return out.toString();
    }
    private static void validate(String kind,JSONObject p)throws Exception{
        String fields=kind.equals("import")?"request_id,location_id,document_id,expected_sha256,expected_bytes":
            kind.equals("export")?"request_id,location_id,parent_id,name,category,filename,expected_sha256":
            kind.equals("fetch")?"request_id,url,name,expected_sha256,expected_bytes,license,license_url":
            kind.equals("unpack")?"request_id,filename,expected_sha256":null;
        if(fields==null)throw new IllegalArgumentException("TRANSFER_KIND_UNAVAILABLE");
        ProductionBridge.fields(p,fields);
        if(p.toString().getBytes(StandardCharsets.UTF_8).length>20000)throw new IllegalArgumentException("TRANSFER_METADATA_TOO_LARGE");
        if(!(p.opt("request_id") instanceof String))throw new IllegalArgumentException("INVALID_TRANSFER_REQUEST_ID");
        if(!p.getString("request_id").matches("[A-Za-z0-9_-]{8,128}"))throw new IllegalArgumentException("INVALID_TRANSFER_REQUEST_ID");
        if(p.has("expected_sha256")&&!p.getString("expected_sha256").matches("[a-f0-9]{64}"))throw new IllegalArgumentException("INVALID_TRANSFER_SHA256");
        if(p.has("expected_bytes"))ProductionBridge.integer(p,"expected_bytes",1,MAX_BYTES,-1);
        if(kind.equals("fetch")){
            url(p.getString("url"));StorageDocuments.name(p.getString("name"));
            p.getString("expected_sha256");ProductionBridge.integer(p,"expected_bytes",1,MAX_BYTES,-1);
            if(p.has("license")&&(!(p.opt("license") instanceof String)||p.getString("license").length()>160))throw new IllegalArgumentException("INVALID_SOURCE_LICENSE");
            if(p.has("license_url")){if(p.getString("license_url").length()>2048)throw new IllegalArgumentException("INVALID_SOURCE_LICENSE_URL");url(p.getString("license_url"));}
        }
        if(kind.equals("export")){StorageDocuments.name(p.getString("name"));p.getString("expected_sha256");}
        if(kind.equals("unpack")){p.getString("expected_sha256");p.getString("filename");}
        if(kind.equals("import")||kind.equals("export"))p.getString("location_id");
    }
    private static URL url(String raw)throws Exception{
        URL result=new URL(raw);
        if(!result.getProtocol().equals("https")||result.getHost().isEmpty()||result.getUserInfo()!=null||raw.length()>8192)
            throw new IllegalArgumentException("TRANSFER_REQUIRES_HTTPS_FILE_REFERENCE");
        String host=result.getHost().toLowerCase(java.util.Locale.ROOT);
        if(host.equals("localhost")||host.endsWith(".localhost")||host.equals("::1")||host.startsWith("127.")||host.equals("0.0.0.0"))
            throw new IllegalArgumentException("LOCAL_NETWORK_SOURCE_UNAVAILABLE");
        return result;
    }
    public static JSONObject enqueue(Context c,String kind,JSONObject p)throws Exception{
        validate(kind,p);
        String id=AgentPolicy.sha256(p.getString("request_id")).substring(0,32);
        String fingerprint=AgentPolicy.sha256(kind+"|"+canonical(p));
        synchronized(LOCK){
            if(task(c,id).isFile()){
                JSONObject prior=load(c,id);
                if(!fingerprint.equals(prior.getString("fingerprint")))throw new IllegalArgumentException("TRANSFER_REQUEST_CONFLICT");
                return status(c,id).put("already_requested",true);
            }
            File[] existing=folder(c).listFiles((d,n)->n.endsWith(".json"));
            if(existing!=null&&existing.length>=512)throw new IOException("TRANSFER_HISTORY_FULL_ORIGINALS_PRESERVED");
            JSONObject row=new JSONObject().put("transfer_id",id).put("request_id",p.getString("request_id"))
                .put("kind",kind).put("payload",new JSONObject(p.toString())).put("fingerprint",fingerprint)
                .put("state","queued").put("bytes_transferred",0).put("started_at_ms",System.currentTimeMillis())
                .put("updated_at_ms",System.currentTimeMillis());
            save(c,row);return status(c,id).put("already_requested",false);
        }
    }
    public static JSONObject status(Context c,String id)throws Exception{
        synchronized(LOCK){
            JSONObject row=load(c,id);
            if(row.getString("state").equals("running")&&!ACTIVE.containsKey(id)){
                row.put("state","interrupted").put("requires_explicit_resume",true);save(c,row);
            }
            JSONObject reply=new JSONObject();
            for(String key:new String[]{"transfer_id","request_id","kind","state","bytes_transferred","total_bytes","started_at_ms",
                    "updated_at_ms","error_code","error_type","result","requires_explicit_resume","resume_mode","requires_owner_open","android_restriction"})
                if(row.has(key))reply.put(key,row.get(key));
            if(reply.has("error_code")){
                String code=reply.getString("error_code");
                if(code.equals("STORAGE_TRANSFER_FAILED"))code=errorCode(reply.optString("error_type"),null);
                reply.put("error_code",code).put("error_hint",errorHint(code));
            }
            JSONObject payload=row.optJSONObject("payload"),result=row.optJSONObject("result");
            String label=result==null?"":result.optString("original_name",result.optString("name",""));
            if(label.isEmpty()&&payload!=null)label=payload.optString("name","");
            reply.put("display_name",label);
            return reply.put("native_editor_required",false).put("execution_after_force_stop_promised",false);
        }
    }
    static String errorCode(String type,String message){
        if(message!=null&&message.matches("[A-Z][A-Z0-9_]{2,100}"))return message;
        switch(type){
            case "SSLHandshakeException":return "TLS_HANDSHAKE_OR_TRUST_FAILED";
            case "SSLPeerUnverifiedException":return "TLS_PEER_VERIFICATION_FAILED";
            case "SSLException":return "TLS_CONNECTION_FAILED";
            case "ConnectException":return "NETWORK_CONNECTION_FAILED_CHECK_CONNECTION_OR_PROXY";
            case "UnknownHostException":return "NETWORK_DNS_UNAVAILABLE";
            case "SocketTimeoutException":return "NETWORK_TRANSFER_TIMEOUT";
            case "SecurityException":return "STORAGE_PERMISSION_MISSING_OR_REVOKED";
            case "FileNotFoundException":return "SOURCE_OR_DESTINATION_DOCUMENT_UNAVAILABLE";
            default:return "STORAGE_TRANSFER_FAILED";
        }
    }
    static String errorHint(String code){
        if(code.startsWith("TLS_"))return "Android could not complete verified TLS. Check device date, network certificate trust and proxy configuration, or use the Android document provider. Certificate checks remain enabled; originals are retained.";
        if(code.startsWith("NETWORK_"))return "Check the device connection, DNS and any required network proxy. Inspect this exact transfer, refresh an expired file reference if needed, then explicitly Resume.";
        if(code.equals("SOURCE_URL_EXPIRED_OR_UNAUTHORIZED"))return "Obtain a fresh authorized original-file URL. Use storage.task.refresh on this transfer, keeping its expected size and SHA-256, then Resume.";
        if(code.startsWith("DESTINATION_"))return "The destination conflicts with this copy or changed after interruption. Preserve that artist file and choose a new destination name/request.";
        if(code.contains("PERMISSION")||code.contains("GRANT"))return "Reopen Render and select the folder or file in Android's system picker. Import needs read access; export and folder creation need write access.";
        if(code.contains("SHA256")||code.contains("SOURCE_CHANGED"))return "No verified native import was completed by this transfer. Check the source and digest; use a new request ID for changed or corrupt source bytes. Originals remain intact.";
        return "Original projects are retained. Inspect this exact transfer and resolve its reported file, format or storage limit before an explicit Resume; do not replay an uncertain Blender edit.";
    }
    public static JSONObject list(Context c)throws Exception{
        JSONArray rows=new JSONArray();File[] files=folder(c).listFiles((d,n)->n.matches("[a-f0-9]{32}\\.json"));
        if(files!=null)for(File f:files){
            String id=f.getName().substring(0,32);
            try{rows.put(status(c,id));}
            catch(Exception corrupt){rows.put(new JSONObject().put("transfer_id",id).put("state","corrupt")
                .put("error_code","TRANSFER_STATE_UNREADABLE_ORIGINALS_PRESERVED").put("requires_explicit_recovery",true));}
        }
        return new JSONObject().put("transfers",rows);
    }
    public static JSONObject control(Context c,String id,String action)throws Exception{
        if(!action.equals("pause")&&!action.equals("resume")&&!action.equals("cancel"))throw new IllegalArgumentException("TRANSFER_CONTROL_UNAVAILABLE");
        synchronized(LOCK){
            JSONObject row=load(c,id);if(row.getString("state").equals("completed"))return status(c,id);
            boolean running=ACTIVE.containsKey(id);
            if(action.equals("resume")&&running)throw new IllegalStateException("TRANSFER_STILL_ACTIVE_POLL_BEFORE_RESUME");
            CONTROL.put(id,action);
            row.put("state",action.equals("resume")?"queued":action.equals("pause")?(running?"pause_requested":"paused"):(running?"cancel_requested":"cancelled"))
                .put("requires_explicit_resume",!action.equals("resume"));
            save(c,row);return status(c,id);
        }
    }
    public static JSONObject refresh(Context c,String id,String replacement)throws Exception{
        url(replacement);
        synchronized(LOCK){
            JSONObject row=load(c,id);
            if(!row.getString("kind").equals("fetch"))throw new IllegalArgumentException("TRANSFER_URL_REFRESH_REQUIRES_FETCH");
            if(ACTIVE.containsKey(id))throw new IllegalStateException("TRANSFER_STILL_ACTIVE_PAUSE_AND_POLL");
            if(row.getString("state").equals("completed"))return status(c,id);
            row.getJSONObject("payload").put("url",replacement);
            row.put("updated_at_ms",System.currentTimeMillis());save(c,row);
            return status(c,id).put("source_reference_refreshed",true).put("digest_and_size_unchanged",true)
                .put("resume_required",true);
        }
    }
    static JSONObject defer(Context c,String id,String reason)throws Exception{
        control(c,id,"pause");
        synchronized(LOCK){JSONObject row=load(c,id);
            row.put("requires_owner_open",true).put("android_restriction",reason);save(c,row);return status(c,id);}
    }
    private static final class Stopped extends IOException{}
    static void check(String id,AtomicBoolean stop)throws Stopped{
        String command=CONTROL.get(id);
        if(stop.get()||"pause".equals(command)||"cancel".equals(command))throw new Stopped();
    }
    static void progress(Context c,String id,long count,long total)throws Exception{
        synchronized(LOCK){
            JSONObject row=load(c,id);row.put("bytes_transferred",count).put("total_bytes",total).put("updated_at_ms",System.currentTimeMillis());save(c,row);
        }
    }
    private static long copy(Context c,String id,InputStream input,OutputStream output,long initial,long total,AtomicBoolean stop,boolean localSync)throws Exception{
        byte[] buffer=new byte[256*1024];long count=initial,last=0;
        int n;
        while((n=input.read(buffer))!=-1){
            check(id,stop);if(n==0)continue;
            if(count+n>MAX_BYTES||(total>=0&&count+n>total))throw new IOException("TRANSFER_SIZE_MISMATCH");
            output.write(buffer,0,n);count+=n;
            if(System.currentTimeMillis()-last>=1000){progress(c,id,count,total);last=System.currentTimeMillis();}
        }
        check(id,stop);output.flush();
        if(localSync&&output instanceof FileOutputStream)((FileOutputStream)output).getFD().sync();
        if(total>=0&&count!=total)throw new IOException("TRANSFER_SIZE_MISMATCH");
        progress(c,id,count,total);return count;
    }
    private static void verifyPrefix(String id,InputStream stream,File partial,AtomicBoolean stop)throws Exception{
        byte[] original=new byte[65536],saved=new byte[65536];
        try(InputStream input=Files.newInputStream(partial.toPath())){
            int n;while((n=input.read(saved))!=-1){
                check(id,stop);int count=0;
                while(count<n){int got=stream.read(original,count,n-count);if(got<0)throw new IOException("TRANSFER_SOURCE_CHANGED");count+=got;}
                for(int i=0;i<n;i++)if(saved[i]!=original[i])throw new IOException("TRANSFER_SOURCE_CHANGED_START_NEW_REQUEST");
            }
        }
    }
    private static JSONObject stored(Context c,String id,File partial,String name,String expected,long bytes,AtomicBoolean stop)throws Exception{
        String sha=hash(id,Files.newInputStream(partial.toPath()),stop);check(id,stop);
        if(expected!=null&&!expected.equals(sha))throw new IOException("TRANSFER_SHA256_MISMATCH");
        int dot=name.lastIndexOf('.');String extension=dot>=0?name.substring(dot+1).toLowerCase(java.util.Locale.ROOT):"bin";
        if(!extension.matches("[a-z0-9]{1,16}"))extension="bin";
        File target=ProductionFiles.file(c,"Imports",sha+"."+extension);
        JSONObject result=new JSONObject().put("file",target.getName()).put("category","Imports").put("sha256",sha)
            .put("bytes",bytes).put("original_name",name).put("original_bytes_preserved",true)
            .put("native_import_completed",false).put("native_import_operation","file.import");
        synchronized(LOCK){JSONObject row=load(c,id);row.put("prepared_result",result);save(c,row);}
        if(target.exists()){
            if(!sha.equals(ProductionFiles.sha(target)))throw new IOException("IMPORTED_ORIGINAL_CONFLICT");
            Files.delete(partial.toPath());
        }else Files.move(partial.toPath(),target.toPath(),StandardCopyOption.ATOMIC_MOVE);
        syncDirectory(target.getParentFile());
        return result;
    }
    private static JSONObject importDocument(Context c,String id,JSONObject p,AtomicBoolean stop)throws Exception{
        StorageDocuments.Node source=StorageDocuments.resolve(c,p.getString("location_id"),p.getString("document_id"),false);
        if(source.directory())throw new IOException("IMPORT_REQUIRES_FILE");
        long total=p.has("expected_bytes")?p.getLong("expected_bytes"):source.bytes;
        if(total>MAX_BYTES)throw new IOException("TRANSFER_FILE_TOO_LARGE");
        File partial=new File(folder(c),id+".partial");
        if(total>=0&&partial.length()>total)throw new IOException("TRANSFER_PARTIAL_CONFLICT");
        if(partial.getParentFile().getUsableSpace()<Math.max(0,total-partial.length())+128L*1024*1024)
            throw new IOException("TRANSFER_NEEDS_MORE_STORAGE");
        long offset=partial.length(),count;
        if(!partial.exists()&&!partial.createNewFile())throw new IOException("TRANSFER_PARTIAL_UNAVAILABLE");
        try(InputStream input=StorageDocuments.read(c,source);FileOutputStream output=new FileOutputStream(partial,true)){
            verifyPrefix(id,input,partial,stop);count=copy(c,id,input,output,offset,total,stop,true);
        }
        StorageDocuments.Node after=StorageDocuments.resolve(c,source.location,source.id,false);
        if((source.modified>0&&after.modified!=source.modified)||(source.bytes>=0&&after.bytes!=source.bytes))
            throw new IOException("TRANSFER_SOURCE_CHANGED_START_NEW_REQUEST");
        return stored(c,id,partial,source.name,p.has("expected_sha256")?p.getString("expected_sha256"):null,count,stop);
    }
    private static JSONObject fetch(Context c,String id,JSONObject p,AtomicBoolean stop)throws Exception{
        File partial=new File(folder(c),id+".partial");long offset=partial.length(),total=p.getLong("expected_bytes");
        if(offset>total)throw new IOException("TRANSFER_PARTIAL_CONFLICT");
        if(folder(c).getUsableSpace()<total-offset+128L*1024*1024)throw new IOException("TRANSFER_NEEDS_MORE_STORAGE");
        URL current=url(p.getString("url"));HttpsURLConnection connection=null;
        try{
            for(int redirects=0;redirects<=5;redirects++){
                connection=(HttpsURLConnection)current.openConnection();connection.setConnectTimeout(20000);connection.setReadTimeout(30000);
                connection.setInstanceFollowRedirects(false);connection.setRequestProperty("Accept-Encoding","identity");
                if(offset>0)connection.setRequestProperty("Range","bytes="+offset+"-");
                int code=connection.getResponseCode();
                if(code==301||code==302||code==303||code==307||code==308){
                    String next=connection.getHeaderField("Location");connection.disconnect();
                    if(next==null||redirects==5)throw new IOException("TRANSFER_REDIRECT_LIMIT");
                    current=url(new URL(current,next).toString());continue;
                }
                if(code==416&&offset==total)return stored(c,id,partial,p.getString("name"),p.getString("expected_sha256"),total,stop);
                if(code!=200&&code!=206)throw new IOException(code==401||code==403?"SOURCE_URL_EXPIRED_OR_UNAUTHORIZED":"SOURCE_HTTP_"+code);
                if(offset>0&&code==206){
                    String range=connection.getHeaderField("Content-Range");
                    if(range==null||!range.startsWith("bytes "+offset+"-"))throw new IOException("TRANSFER_RANGE_CONFLICT");
                }else if(code==200)offset=0;
                long count;
                try(InputStream input=connection.getInputStream();FileOutputStream output=new FileOutputStream(partial,offset>0)){
                    count=copy(c,id,input,output,offset,total,stop,true);
                }
                return stored(c,id,partial,p.getString("name"),p.getString("expected_sha256"),count,stop);
            }
            throw new IOException("TRANSFER_REDIRECT_LIMIT");
        }finally{if(connection!=null)connection.disconnect();}
    }
    private static JSONObject export(Context c,String id,JSONObject p,AtomicBoolean stop)throws Exception{
        File source=ProductionFiles.file(c,p.getString("category"),p.getString("filename"));
        String sha=p.getString("expected_sha256");
        if(source.length()>MAX_BYTES)throw new IOException("TRANSFER_FILE_TOO_LARGE");
        if(!source.isFile()||source.getName().contains(".partial")||!sha.equals(hash(id,Files.newInputStream(source.toPath()),stop)))throw new IOException("ARTIFACT_CHECKSUM_MISMATCH");
        String location=p.getString("location_id"),parent=p.getString("parent_id"),name=p.getString("name");
        if(location.equals("workspace")&&StorageDocuments.workspace(c).getUsableSpace()<source.length()+128L*1024*1024)
            throw new IOException("TRANSFER_NEEDS_MORE_STORAGE");
        JSONObject row;StorageDocuments.Node destination;
        synchronized(LOCK){row=load(c,id);}
            if(row.has("destination_id")){
                destination=StorageDocuments.resolve(c,location,row.getString("destination_id"),true);
                if(destination.bytes==source.length()&&sha.equals(hash(id,StorageDocuments.read(c,destination),stop)))
                    return destination.json().put("sha256",sha).put("provider_readback_sha256_verified",true)
                        .put("already_exported",true).put("source_project_unchanged",true).put("remote_sync_verified",false);
                // A visible partial document may have been edited by the artist
                // after interruption. Only rewrite an unchanged prefix of this
                // source; never treat a retained handle as permission to clobber edits.
                verifyDestinationPrefix(c,id,source,destination,stop);
                synchronized(LOCK){row=load(c,id);row.put("resume_mode","rewrite_only_this_transfer_uncommitted_document");save(c,row);}
            }else{
                destination=StorageDocuments.find(c,location,parent,name);
                if(destination!=null){
                    if(destination.directory()||!sha.equals(hash(id,StorageDocuments.read(c,destination),stop)))throw new IOException("DESTINATION_NAME_CONFLICT");
                    return destination.json().put("sha256",sha).put("provider_readback_sha256_verified",true)
                        .put("already_exported",true).put("source_project_unchanged",true).put("remote_sync_verified",false);
                }
                destination=StorageDocuments.createFile(c,location,parent,name,StorageDocuments.mime(name));
                synchronized(LOCK){row=load(c,id);row.put("destination_id",destination.id);save(c,row);}
            }
        try(InputStream input=Files.newInputStream(source.toPath());OutputStream output=StorageDocuments.write(c,destination)){
            copy(c,id,input,output,0,source.length(),stop,destination.file!=null);
        }
        if(destination.file!=null)syncDirectory(destination.file.getParentFile());
        check(id,stop);
        if(!sha.equals(hash(id,StorageDocuments.read(c,destination),stop)))throw new IOException("PROVIDER_READBACK_SHA256_MISMATCH");
        return destination.json().put("sha256",sha).put("bytes",source.length()).put("provider_readback_sha256_verified",true)
            .put("provider_write_completed",true).put("source_project_unchanged",true).put("remote_sync_verified",false);
    }
    private static void verifyDestinationPrefix(Context c,String id,File source,StorageDocuments.Node destination,AtomicBoolean stop)throws Exception{
        try(InputStream saved=StorageDocuments.read(c,destination);InputStream original=Files.newInputStream(source.toPath())){
            byte[] left=new byte[65536],right=new byte[65536];int n;
            while((n=saved.read(left))!=-1){
                check(id,stop);int count=0;
                while(count<n){int got=original.read(right,count,n-count);if(got<0)throw new IOException("DESTINATION_CHANGED_ORIGINALS_PRESERVED");count+=got;}
                for(int i=0;i<n;i++)if(left[i]!=right[i])throw new IOException("DESTINATION_CHANGED_ORIGINALS_PRESERVED");
            }
        }
    }
    static String hash(String id,InputStream stream,AtomicBoolean stop)throws Exception{
        try(InputStream input=stream){java.security.MessageDigest digest=java.security.MessageDigest.getInstance("SHA-256");
            byte[] buffer=new byte[1024*1024];int n;while((n=input.read(buffer))!=-1){check(id,stop);if(n>0)digest.update(buffer,0,n);}
            return AgentPolicy.hex(digest.digest());}
    }
    public static void run(Context c,String id,AtomicBoolean stop)throws Exception{
        JSONObject row;
        synchronized(LOCK){
            row=load(c,id);if(!row.getString("state").equals("queued")||ACTIVE.putIfAbsent(id,true)!=null)return;
            CONTROL.put(id,"run");row.put("state","running").put("requires_owner_open",false);row.remove("android_restriction");
            try{save(c,row);}catch(Exception e){ACTIVE.remove(id);CONTROL.remove(id);throw e;}
        }
        try{
            JSONObject p=row.getJSONObject("payload");String kind=row.getString("kind");
            JSONObject result=null;
            if(row.has("prepared_result")){
                JSONObject prepared=row.getJSONObject("prepared_result");File artifact=ProductionFiles.file(c,"Imports",prepared.getString("file"));
                if(artifact.isFile()&&prepared.getString("sha256").equals(hash(id,Files.newInputStream(artifact.toPath()),stop)))result=prepared;
            }
            if(result==null)result=kind.equals("import")?importDocument(c,id,p,stop):kind.equals("fetch")?fetch(c,id,p,stop):
                kind.equals("unpack")?FileBundles.run(c,id,p,stop):export(c,id,p,stop);
            if(kind.equals("fetch")){
                result.put("license",p.optString("license","not supplied; verify source rights"));
                if(p.has("license_url"))result.put("license_url",p.getString("license_url"));
                result.put("source_host",url(p.getString("url")).getHost());
            }
            synchronized(LOCK){row=load(c,id);row.remove("error_code");row.remove("error_type");
                row.put("state","completed").put("result",result).put("requires_explicit_resume",false).put("updated_at_ms",System.currentTimeMillis());save(c,row);}
        }catch(Stopped stopped){
            synchronized(LOCK){row=load(c,id);row.put("state","cancel".equals(CONTROL.get(id))?"cancelled":"paused").put("requires_explicit_resume",true);save(c,row);}
        }catch(Exception error){
            synchronized(LOCK){
                row=load(c,id);String message=error.getMessage();
                row.put("state","failed").put("error_type",error.getClass().getSimpleName())
                    .put("error_code",errorCode(error.getClass().getSimpleName(),message)).put("updated_at_ms",System.currentTimeMillis())
                    .put("requires_explicit_resume",true);save(c,row);
            }
        }finally{ACTIVE.remove(id);CONTROL.remove(id);}
    }
}
