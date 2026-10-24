package com.rezox.render.omega.engine;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.List;

/** Bounded selection of known Blender logs; historical failures are not current evidence. */
public final class EngineStartupLog {
    private EngineStartupLog(){}
    /** Classify only an observed assertion in the current launch's bounded log. */
    public static String failureCode(String tail,boolean current){
        if(current&&tail!=null&&tail.contains("CHECK failed: host_platform::kHasF16C")
                &&tail.contains("ndk_translation/"))return "ANDROID_TRANSLATOR_F16C_UNAVAILABLE";
        return "";
    }
    public static String failureMessage(String code){
        if("ANDROID_TRANSLATOR_F16C_UNAVAILABLE".equals(code))
            return "The Android ARM translation layer lacks required F16C support for this native Blender path. "
                +"Use a compatible native ARM64 Android device or supported emulation. Preserve the checkpoint "
                +"and inspect the original command result before retrying; changing quality or thermal settings does not fix this CPU compatibility failure.";
        return "";
    }
    public static final class Selection {
        public final File file;
        public final boolean current;
        private Selection(File file,boolean current){this.file=file;this.current=current;}
    }
    private static boolean same(File a,File b){
        if(a==null||b==null)return false;
        try{return a.getCanonicalFile().equals(b.getCanonicalFile());}
        catch(IOException error){return false;}
    }
    private static boolean fresh(File file,long launchStarted){
        return launchStarted>0&&file.lastModified()>=launchStarted;
    }
    public static Selection select(File preferred,List<File> candidates,long launchStarted){
        File newest=null;
        for(File file:candidates){
            if(file==null||!file.isFile()||!file.canRead())continue;
            if(same(file,preferred)&&fresh(file,launchStarted))return new Selection(file,true);
            if(newest==null||file.lastModified()>newest.lastModified())newest=file;
        }
        return new Selection(newest,newest!=null&&fresh(newest,launchStarted));
    }
    public static String readTail(File file,int maximumBytes)throws IOException{
        if(maximumBytes<1||maximumBytes>65536)throw new IllegalArgumentException("INVALID_LOG_TAIL_LIMIT");
        try(RandomAccessFile input=new RandomAccessFile(file,"r")){
            long length=input.length();
            int count=(int)Math.min(length,maximumBytes);
            input.seek(length-count);byte[] data=new byte[count];input.readFully(data);
            return new String(data,StandardCharsets.UTF_8);
        }
    }
}
