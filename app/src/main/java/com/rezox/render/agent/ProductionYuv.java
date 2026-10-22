package com.rezox.render.agent;
import android.graphics.Bitmap;
import android.media.Image;
import java.nio.ByteBuffer;

/** Bounded scratch memory: two RGB scanlines, not millions of temporary arrays. */
final class ProductionYuv {
    private ProductionYuv(){}
    static int packed(int argb){
        int r=(argb>>>16)&255,g=(argb>>>8)&255,b=argb&255;
        int y=ProductionVideoEncoder.clamp(((66*r+129*g+25*b+128)>>8)+16);
        int u=ProductionVideoEncoder.clamp(((-38*r-74*g+112*b+128)>>8)+128);
        int v=ProductionVideoEncoder.clamp(((112*r-94*g-18*b+128)>>8)+128);
        return (y<<16)|(u<<8)|v;
    }
    static void fill(Bitmap bitmap,Image image){
        int w=bitmap.getWidth(),h=bitmap.getHeight();
        if((w&1)!=0||(h&1)!=0||image.getWidth()!=w||image.getHeight()!=h||image.getPlanes().length!=3)
            throw new IllegalStateException("ENCODER_IMAGE_LAYOUT_UNSUPPORTED");
        Image.Plane[] planes=image.getPlanes();ByteBuffer[] buffers=new ByteBuffer[3];int[] positions=new int[3],rowStride=new int[3],pixelStride=new int[3];
        for(int i=0;i<3;i++){
            buffers[i]=planes[i].getBuffer();positions[i]=buffers[i].position();rowStride[i]=planes[i].getRowStride();pixelStride[i]=planes[i].getPixelStride();
            int width=i==0?w:w/2,height=i==0?h:h/2;
            long last=(long)positions[i]+(long)(height-1)*rowStride[i]+(long)(width-1)*pixelStride[i];
            if(pixelStride[i]<1||rowStride[i]<1||last>=buffers[i].limit())throw new IllegalStateException("ENCODER_PLANE_LAYOUT_UNSUPPORTED");
        }
        int[] rows=new int[w*2];
        for(int y=0;y<h;y+=2){
            bitmap.getPixels(rows,0,w,0,y,w,2);
            for(int x=0;x<w;x+=2){
                int a=packed(rows[x]),b=packed(rows[x+1]),c=packed(rows[w+x]),d=packed(rows[w+x+1]);
                int y0=positions[0]+y*rowStride[0]+x*pixelStride[0],y1=y0+rowStride[0];
                buffers[0].put(y0,(byte)(a>>>16));buffers[0].put(y0+pixelStride[0],(byte)(b>>>16));
                buffers[0].put(y1,(byte)(c>>>16));buffers[0].put(y1+pixelStride[0],(byte)(d>>>16));
                int u=(((a>>>8)&255)+((b>>>8)&255)+((c>>>8)&255)+((d>>>8)&255)+2)/4;
                int v=((a&255)+(b&255)+(c&255)+(d&255)+2)/4;
                buffers[1].put(positions[1]+(y/2)*rowStride[1]+(x/2)*pixelStride[1],(byte)u);
                buffers[2].put(positions[2]+(y/2)*rowStride[2]+(x/2)*pixelStride[2],(byte)v);
            }
        }
    }
}
