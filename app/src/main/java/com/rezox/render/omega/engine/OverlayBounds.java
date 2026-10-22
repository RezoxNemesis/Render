package com.rezox.render.omega.engine;

/** Pure viewport-control geometry; no Blender render settings or mesh data. */
public final class OverlayBounds {
    private OverlayBounds(){}
    public static int clampTop(int requested,int screenHeight,int overlayHeight,int margin){
        if(screenHeight<=0||overlayHeight<0||margin<0)
            throw new IllegalArgumentException("INVALID_OVERLAY_GEOMETRY");
        int max=Math.max(margin,screenHeight-overlayHeight-margin);
        return Math.max(margin,Math.min(max,requested));
    }
    public static int scrollHeight(int availableHeight,int desired,int minimum){
        if(availableHeight<=0||minimum<=0||desired<=0)
            throw new IllegalArgumentException("INVALID_SCROLL_BOUND");
        return Math.min(Math.max(minimum,desired),Math.max(minimum,availableHeight));
    }
    public static boolean isTap(float startX,float startY,float endX,float endY,float slop){
        if(!Float.isFinite(startX)||!Float.isFinite(startY)||
           !Float.isFinite(endX)||!Float.isFinite(endY)||
           !Float.isFinite(slop)||slop<0)throw new IllegalArgumentException("INVALID_GESTURE");
        float dx=endX-startX,dy=endY-startY;
        return dx*dx+dy*dy<=slop*slop;
    }
}
