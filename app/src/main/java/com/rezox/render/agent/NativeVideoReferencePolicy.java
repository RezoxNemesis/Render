package com.rezox.render.agent;

/** Bounded Android admission before original-owner video is opened by native bpy. */
public final class NativeVideoReferencePolicy {
    static final long MIN_HEADROOM_BYTES=192L*1024*1024;
    private NativeVideoReferencePolicy(){}
    public static void requireAllowed(String extension,boolean thermalAllowed,
                                      boolean lowMemory,long availableBytes,long reserveBytes){
        if(!"mp4".equals(extension))
            throw new IllegalArgumentException("NATIVE_TIMELINE_REFERENCE_MP4_REQUIRED");
        if(!thermalAllowed||lowMemory||
            (availableBytes>=0&&(reserveBytes>availableBytes||
                availableBytes-reserveBytes<MIN_HEADROOM_BYTES)))
            throw new IllegalStateException(
                "NATIVE_VIDEO_REFERENCE_MEMORY_OR_THERMAL_PRESSURE_ORIGINAL_RETAINED");
    }
    public static void requirePreviewFits(int width,int height,long availableBytes,long reserveBytes){
        if(width<1||height<1)throw new IllegalArgumentException("INVALID_NATIVE_REFERENCE_DIMENSIONS");
        long expectedBytes=(long)width*height*16L;
        if(availableBytes>=0 && (reserveBytes>availableBytes||
                expectedBytes>availableBytes-reserveBytes))
            throw new IllegalStateException("NATIVE_REFERENCE_PREVIEW_MEMORY_PRESSURE_ORIGINAL_RETAINED");
    }
}
