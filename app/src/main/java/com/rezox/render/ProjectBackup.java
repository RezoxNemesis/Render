package com.rezox.render;

import com.rezox.render.agent.ProjectScope;
import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * User-chosen Android Storage Access Framework backup. Streams original
 * .blend bytes with SHA-256 manifest, NO cloud upload, NO in-memory ZIP.
 * Save before switching from older debug APKs to the durable release key.
 */
public final class ProjectBackup {
    public static final class Result {
        public final int projects;
        public final long sourceBytes;
        public Result(int count,long bytes){projects=count;sourceBytes=bytes;}
    }
    private ProjectBackup(){}

    public static Result export(List<ProjectScope.Entry> sources,OutputStream destination) throws IOException {
        if(sources==null || sources.isEmpty())
            throw new IOException("No saved .blend projects found to back up.");
        long bytesWritten=0;
        JSONArray manifest=new JSONArray();
        byte[] chunk=new byte[131072];
        try(ZipOutputStream zip=new ZipOutputStream(destination)) {
            for(ProjectScope.Entry entry:sources) {
                java.io.File source=entry.file;
                if(!source.isFile() || Files.isSymbolicLink(source.toPath()))
                    throw new IOException("Project file changed during backup.");
                String safe=source.getName().replaceAll("[^A-Za-z0-9_.-]","_");
                if(!safe.toLowerCase(Locale.ROOT).endsWith(".blend"))
                    throw new IOException("Only .blend files may be backed up.");
                String name="projects/"+entry.id+"/"+safe;
                ZipEntry member=new ZipEntry(name);
                member.setTime(source.lastModified());
                zip.putNextEntry(member);
                final MessageDigest sha;
                try{sha=MessageDigest.getInstance("SHA-256");}
                catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}
                long length=0;
                try(InputStream in=new BufferedInputStream(Files.newInputStream(source.toPath()))) {
                    int n;
                    while((n=in.read(chunk))!=-1){
                        if(n==0)continue;
                        zip.write(chunk,0,n);
                        sha.update(chunk,0,n);
                        length+=n;
                    }
                }
                zip.closeEntry();
                bytesWritten+=length;
                StringBuilder digest=new StringBuilder(64);
                for(byte b:sha.digest())digest.append(String.format(Locale.ROOT,"%02x",b&255));
                JSONObject item=new JSONObject();
                item.put("entry",name).put("size",length).put("sha256",digest.toString());
                manifest.put(item);
            }
            JSONObject index=new JSONObject().put("format","render-studio-blend-backup-1")
                .put("files",manifest).put("externalDependenciesIncluded",false)
                .put("notice","Referenced materials, textures and external linked libraries may need separate backups.");
            ZipEntry info=new ZipEntry("render-backup-manifest.json");
            zip.putNextEntry(info);
            zip.write(index.toString(2).getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
            zip.finish();
        }
        return new Result(sources.size(),bytesWritten);
    }
}
