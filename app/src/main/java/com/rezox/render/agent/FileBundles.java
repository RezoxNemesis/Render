package com.rezox.render.agent;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Original ZIPs remain untouched; bounded dependency bundles are extracted on the file worker, never bpy's UI thread. */
final class FileBundles {
    static final String MANIFEST="_render_bundle_manifest.json";
    private FileBundles(){}
    static String relative(String value){
        if(value==null||value.length()>240||value.isEmpty()||value.startsWith("/")||value.contains("\\")||value.contains(":"))
            throw new IllegalArgumentException("UNSAFE_BUNDLE_ENTRY");
        for(String part:value.split("/",-1)){
            if(part.isEmpty()||part.equals(".")||part.equals("..")||part.equals(MANIFEST))throw new IllegalArgumentException("UNSAFE_BUNDLE_ENTRY");
            StorageDocuments.name(part);
        }
        return value;
    }
    private static File child(File root,String name)throws Exception{
        relative(name);File file=new File(root,name);
        Path base=root.getCanonicalFile().toPath();Path current=root.toPath();
        for(String part:name.split("/")){current=current.resolve(part);if(Files.isSymbolicLink(current))throw new IOException("BUNDLE_SYMLINK");}
        if(!file.getCanonicalFile().toPath().startsWith(base))throw new IOException("BUNDLE_PATH_ESCAPE");return file;
    }
    private static void save(File folder,JSONObject manifest)throws Exception{
        AtomicFile state=new AtomicFile(new File(folder,MANIFEST));FileOutputStream out=state.startWrite();
        try{out.write(manifest.toString().getBytes(StandardCharsets.UTF_8));state.finishWrite(out);FileTransfers.syncDirectory(folder);}
        catch(Exception e){state.failWrite(out);throw e;}
    }
    private static JSONObject load(File root)throws Exception{
        File file=new File(root,MANIFEST);
        if(Files.isSymbolicLink(file.toPath())||file.length()>2*1024*1024)throw new IOException("BUNDLE_STATE_INVALID");
        try(InputStream in=new AtomicFile(file).openRead();ByteArrayOutputStream data=new ByteArrayOutputStream()){
            byte[] block=new byte[8192];int n;while((n=in.read(block))!=-1){if(data.size()+n>2*1024*1024)throw new IOException("BUNDLE_STATE_INVALID");data.write(block,0,n);}
            return new JSONObject(new String(data.toByteArray(),StandardCharsets.UTF_8));
        }
    }
    static JSONObject run(Context c,String id,JSONObject p,AtomicBoolean stop)throws Exception{
        String sourceName=p.getString("filename"),sha=p.getString("expected_sha256");
        File source=ProductionFiles.file(c,"Imports",sourceName);
        if(!sourceName.endsWith(".zip")||!sha.equals(FileTransfers.hash(id,Files.newInputStream(source.toPath()),stop)))
            throw new IOException("BUNDLE_ORIGINAL_SHA256_MISMATCH");
        File root=new File(ProductionFiles.folder(c,"Imports"),"Bundles");
        if(Files.isSymbolicLink(root.toPath())||(!root.isDirectory()&&!root.mkdir()))throw new IOException("BUNDLE_STORAGE_UNAVAILABLE");
        File destination=new File(root,sha),working=new File(root,".partial-"+id);
        if(Files.isSymbolicLink(destination.toPath())||Files.isSymbolicLink(working.toPath()))throw new IOException("BUNDLE_SYMLINK");
        if(destination.isDirectory()){
            JSONObject manifest=load(destination);
            if(!sha.equals(manifest.getString("original_sha256")))throw new IOException("BUNDLE_CONFLICT");
            JSONArray entries=manifest.getJSONArray("entries");
            for(int i=0;i<entries.length();i++){
                JSONObject entry=entries.getJSONObject(i);File file=child(destination,entry.getString("path"));
                if(!file.isFile()||file.length()!=entry.getLong("bytes")||!entry.getString("sha256").equals(FileTransfers.hash(id,Files.newInputStream(file.toPath()),stop)))
                    throw new IOException("BUNDLE_INTEGRITY_FAILED_ORIGINAL_RETAINED");
            }
            return result(destination,sourceName,sha,entries.length(),manifest.getLong("total_bytes"));
        }
        if(!working.isDirectory()&&!working.mkdir())throw new IOException("BUNDLE_STORAGE_UNAVAILABLE");
        JSONObject manifest=new File(working,MANIFEST).isFile()?load(working):new JSONObject().put("original_sha256",sha).put("entries",new JSONArray());
        if(!sha.equals(manifest.getString("original_sha256")))throw new IOException("BUNDLE_CONFLICT");
        JSONArray completed=manifest.getJSONArray("entries");Map<String,JSONObject> prior=new HashMap<>();
        for(int i=0;i<completed.length();i++)prior.put(completed.getJSONObject(i).getString("path"),completed.getJSONObject(i));
        try(ZipFile zip=new ZipFile(source)){
            ArrayList<ZipEntry> entries=new ArrayList<>();Set<String> names=new HashSet<>();long total=0,done=0;
            Enumeration<? extends ZipEntry> iterator=zip.entries();int count=0;
            while(iterator.hasMoreElements()){
                ZipEntry entry=iterator.nextElement();if(++count>2048)throw new IOException("BUNDLE_TOO_MANY_ENTRIES");
                String path=entry.getName();if(entry.isDirectory()){relative(path.substring(0,path.length()-1));continue;}
                relative(path);if(!names.add(path))throw new IOException("BUNDLE_DUPLICATE_ENTRY");
                if(entry.getSize()<0||entry.getSize()>FileTransfers.MAX_BYTES||entry.getSize()>FileTransfers.MAX_BYTES-total)
                    throw new IOException("BUNDLE_UNPACKED_SIZE_LIMIT");
                total+=entry.getSize();entries.add(entry);
            }
            for(ZipEntry entry:entries){
                FileTransfers.check(id,stop);File file=child(working,entry.getName());JSONObject previous=prior.get(entry.getName());
                if(previous!=null&&file.isFile()&&file.length()==entry.getSize()&&previous.getLong("crc32")==entry.getCrc()
                        &&previous.getString("sha256").equals(FileTransfers.hash(id,Files.newInputStream(file.toPath()),stop))){
                    done+=entry.getSize();FileTransfers.progress(c,id,done,total);continue;
                }
                if(root.getUsableSpace()<entry.getSize()+128L*1024*1024)throw new IOException("BUNDLE_NEEDS_MORE_STORAGE");
                if(!file.getParentFile().isDirectory()&&!file.getParentFile().mkdirs())throw new IOException("BUNDLE_DIRECTORY_CREATE_FAILED");
                File temporary=File.createTempFile(".unpack-",".partial",file.getParentFile());long bytes=0;
                java.util.zip.CRC32 crc=new java.util.zip.CRC32();
                try(InputStream input=zip.getInputStream(entry);FileOutputStream output=new FileOutputStream(temporary)){
                    byte[] block=new byte[256*1024];int n;long last=0;
                    while((n=input.read(block))!=-1){FileTransfers.check(id,stop);if(n==0)continue;bytes+=n;
                        if(bytes>entry.getSize())throw new IOException("BUNDLE_ENTRY_SIZE_MISMATCH");
                        output.write(block,0,n);crc.update(block,0,n);
                        if(System.currentTimeMillis()-last>1000){FileTransfers.progress(c,id,done+bytes,total);last=System.currentTimeMillis();}}
                    output.getFD().sync();
                    if(bytes!=entry.getSize()||crc.getValue()!=entry.getCrc())throw new IOException("BUNDLE_ENTRY_CRC_MISMATCH");
                    String digest=FileTransfers.hash(id,Files.newInputStream(temporary.toPath()),stop);
                    Files.move(temporary.toPath(),file.toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);FileTransfers.syncDirectory(file.getParentFile());
                    JSONObject row=new JSONObject().put("path",entry.getName()).put("bytes",bytes).put("crc32",crc.getValue()).put("sha256",digest);
                    if(previous!=null){for(int i=0;i<completed.length();i++)if(completed.getJSONObject(i).getString("path").equals(entry.getName())){completed.put(i,row);break;}}
                    else completed.put(row);
                    manifest.put("total_bytes",total);save(working,manifest);done+=bytes;
                }finally{Files.deleteIfExists(temporary.toPath());}
            }
            manifest.put("total_bytes",total);save(working,manifest);FileTransfers.check(id,stop);
            Files.move(working.toPath(),destination.toPath(),StandardCopyOption.ATOMIC_MOVE);FileTransfers.syncDirectory(root);
            FileTransfers.progress(c,id,total,total);return result(destination,sourceName,sha,entries.size(),total);
        }
    }
    private static JSONObject result(File bundle,String original,String sha,int entries,long total)throws Exception{
        return new JSONObject().put("category","Imports").put("filename",original).put("sha256",sha)
            .put("bundle_id",sha).put("entries",entries).put("unpacked_bytes",total)
            .put("manifest_sha256",ProductionFiles.sha(new File(bundle,MANIFEST))).put("original_bytes_preserved",true)
            .put("native_import_completed",false).put("native_import_operation","file.import");
    }
}
