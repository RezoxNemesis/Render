package com.rezox.render.ui;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.view.View;

/** Native Canvas-built 3D torus wireframe and perspective grid, not a mockup image. */
public final class StudioViewportArt extends View {
    private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
    public StudioViewportArt(Context context) {super(context);setLayerType(View.LAYER_TYPE_SOFTWARE,null);}
    private float[] project(float x,float y,float z,float midx,float midy,float radius) {
        // Rotate model around X and Z to reveal 3D depth.
        double az=.52, ax=.78;
        float xp=(float)(x*Math.cos(az)-y*Math.sin(az));
        float yp=(float)(x*Math.sin(az)+y*Math.cos(az));
        float y2=(float)(yp*Math.cos(ax)-z*Math.sin(ax));
        float z2=(float)(yp*Math.sin(ax)+z*Math.cos(ax));
        float perspective=4.8f/(4.8f+z2);
        return new float[]{midx+radius*xp*perspective,midy-radius*y2*perspective,z2};
    }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int width=getWidth(),height=getHeight();
        if(width<=0||height<=0)return;
        paint.setShader(new LinearGradient(0,0,width,height,
            new int[]{0xFF272330,0xFF121922,0xFF0D1018},null,Shader.TileMode.CLAMP));
        paint.setStyle(Paint.Style.FILL);
        canvas.drawRoundRect(0,0,width,height,22,22,paint);
        paint.setShader(new RadialGradient(width*.67f,height*.52f,width*.53f,
            new int[]{0x33FF995B,0x10FF9968,0x00FF995B},null,Shader.TileMode.CLAMP));
        canvas.drawCircle(width*.67f,height*.52f,width*.53f,paint);
        paint.setShader(null);
        paint.setStrokeWidth(1);
        // Perspective viewport grid.
        paint.setColor(0x305C7C99);
        for(int i=-9;i<=9;i++){
            float origin=width*.5f+i*width*.095f;
            canvas.drawLine(origin,height*.89f,width*.5f+i*width*.017f,height*.56f,paint);
        }
        for(int i=0;i<7;i++){
            float y=height*(.57f+.047f*i*i/6f);
            canvas.drawLine(0,y,width,y,paint);
        }
        paint.setStrokeWidth(1.2f);
        float cx=width*.63f, cy=height*.51f;
        float scale=Math.min(width*.24f,height*.40f);
        // Native projected torus, with depth-weighted wireframe strokes.
        for(int i=0;i<22;i++){
            float v=(float)(2*Math.PI*i/22);
            Path line=new Path();
            float avgZ=0f;
            for(int j=0;j<=96;j++){
                float u=(float)(2*Math.PI*j/96);
                float x=(float)((1.02+.37*Math.cos(v))*Math.cos(u));
                float y=(float)((1.02+.37*Math.cos(v))*Math.sin(u));
                float z=(float)(.37*Math.sin(v));
                float[] p=project(x,y,z,cx,cy,scale);
                if(j==0)line.moveTo(p[0],p[1]); else line.lineTo(p[0],p[1]);
                avgZ+=p[2]/97f;
            }
            int alpha=(int)Math.min(225,Math.max(45,125-avgZ*60));
            paint.setColor(Color.argb(alpha,255,159,101));
            paint.setStrokeWidth(1.0f);
            paint.setStyle(Paint.Style.STROKE);
            canvas.drawPath(line,paint);
        }
        for(int i=0;i<34;i++){
            float u=(float)(2*Math.PI*i/34);
            Path line=new Path();float avgZ=0;
            for(int j=0;j<=48;j++){
                float v=(float)(2*Math.PI*j/48);
                float x=(float)((1.02+.37*Math.cos(v))*Math.cos(u));
                float y=(float)((1.02+.37*Math.cos(v))*Math.sin(u));
                float z=(float)(.37*Math.sin(v));
                float[] p=project(x,y,z,cx,cy,scale);
                if(j==0)line.moveTo(p[0],p[1]); else line.lineTo(p[0],p[1]);
                avgZ+=p[2]/49f;
            }
            paint.setColor(Color.argb((int)Math.min(235,Math.max(40,120-avgZ*65)),255,176,113));
            paint.setStrokeWidth(.75f);
            canvas.drawPath(line,paint);
        }
        // Center locator.
        paint.setStyle(Paint.Style.FILL);paint.setColor(0xFF63D8FF);
        canvas.drawCircle(cx,cy,3f,paint);
        paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(1.5f);
        paint.setColor(0xAA63D8FF);
        canvas.drawCircle(cx,cy,11f,paint);
        paint.setStyle(Paint.Style.FILL);
        paint.setShader(null);
        paint.setColor(0xFFA2ACBE);
        paint.setTextSize(StudioUi.dp(getContext(),9));
        canvas.drawText("PERSPECTIVE   /   SOLID + WIREFRAME",StudioUi.dp(getContext(),16),
            height-StudioUi.dp(getContext(),17),paint);
    }
}
