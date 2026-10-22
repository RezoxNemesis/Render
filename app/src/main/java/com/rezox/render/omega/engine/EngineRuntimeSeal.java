package com.rezox.render.omega.engine;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.AtomicMoveNotSupportedException;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Stable runtime archive identity across Android APK upgrades.
 *
 * A changed APK timestamp is NOT proof the packaged Blender resource changed.
 * Explicit SHA-256 permits reusing a previously extracted real Blender runtime
 * across in-place upgrades without re-extracting and deleting user preferences.
 * The same-version fast path relies only on the installation seal and essential
 * startup file checks; it makes no claim to have hashed every unpacked file.
 */
public final class EngineRuntimeSeal {
    public static final String DIGEST_FILE=".render-asset-sha256";
    private static final String STARTUP="scripts/startup/render_agent_startup.py";
    private EngineRuntimeSeal(){}
    private static File seal(File root,String version){
        if(!version.matches("[0-9]+(?:\\.[0-9]+){1,3}"))
            throw new IllegalArgumentException("INVALID_BLENDER_RUNTIME_VERSION");
        return new File(root,".installed-"+version);
    }
    private static boolean regularFile(File file)throws IOException{
        return file.isFile()&&!Files.isSymbolicLink(file.toPath());
    }
    public static boolean hasInstalledRuntime(File root,String version)throws IOException{
        if(!root.isDirectory()||Files.isSymbolicLink(root.toPath()))return false;
        File proof=seal(root,version);
        File startup=new File(root,STARTUP);
        return regularFile(proof)&&regularFile(startup)&&startup.length()>0
            &&startup.getCanonicalFile().toPath().startsWith(root.getCanonicalFile().toPath());
    }
    public static boolean hasSamePackageStamp(File root,String version,String stamp)throws IOException{
        return hasInstalledRuntime(root,version)&&stamp.equals(
            Files.readString(seal(root,version).toPath(),StandardCharsets.UTF_8).trim());
    }
    public static boolean sameArchive(File root,String version,String sha256)throws IOException{
        if(!hasInstalledRuntime(root,version)||!sha256.matches("[0-9a-f]{64}"))
            return false;
        File digest=new File(root,DIGEST_FILE);
        return regularFile(digest)&&sha256.equals(
            Files.readString(digest.toPath(),StandardCharsets.UTF_8).trim());
    }
    /** Hash the literal APK asset, not a partially consumed ZipInputStream. */
    public static String archiveSha256(InputStream input)throws IOException{
        try(InputStream src=input){
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            byte[] bytes=new byte[65536];int n;
            while((n=src.read(bytes))!=-1){
                if(n>0)digest.update(bytes,0,n);
            }
            StringBuilder hex=new StringBuilder(64);
            for(byte b:digest.digest())hex.append(Character.forDigit((b>>4)&15,16))
                .append(Character.forDigit(b&15,16));
            return hex.toString();
        }catch(NoSuchAlgorithmException e){throw new IOException("SHA256_UNAVAILABLE",e);}
    }
    public static void writeSeal(File root,String version,String packageStamp,String sha256)
            throws IOException {
        if(!root.isDirectory()||Files.isSymbolicLink(root.toPath()))
            throw new IOException("BLENDER_RUNTIME_ROOT_UNSAFE");
        if(!sha256.matches("[0-9a-f]{64}"))throw new IOException("INVALID_ARCHIVE_DIGEST");
        atomicWrite(new File(root,DIGEST_FILE),sha256);
        atomicWrite(seal(root,version),packageStamp);
    }
    /** Only update the installation timestamp after the saved SHA matches. */
    public static void refreshPackageStamp(File root,String version,String packageStamp,
                                           String checkedSha256)throws IOException {
        if(!sameArchive(root,version,checkedSha256))
            throw new IOException("BLENDER_ASSET_REVISION_MISMATCH");
        atomicWrite(seal(root,version),packageStamp);
    }
    private static void atomicWrite(File destination,String value)throws IOException {
        File temporary=File.createTempFile("runtime-seal-",".part",destination.getParentFile());
        try{
            Files.writeString(temporary.toPath(),value,StandardCharsets.UTF_8);
            try{
                Files.move(temporary.toPath(),destination.toPath(),
                    StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);
            }catch(AtomicMoveNotSupportedException e){
                Files.move(temporary.toPath(),destination.toPath(),
                    StandardCopyOption.REPLACE_EXISTING);
            }
        }finally{Files.deleteIfExists(temporary.toPath());}
    }
}
