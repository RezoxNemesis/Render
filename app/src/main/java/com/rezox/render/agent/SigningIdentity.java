package com.rezox.render.agent;

import android.content.Context;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.os.Build;
import java.security.MessageDigest;
import java.util.Locale;

/** Public signing-certificate inspection; never reads or exports a private key. */
public final class SigningIdentity {
    public static final String PERMANENT_SHA256=
        "03:01:F0:84:CB:37:45:7B:E8:23:53:A8:A0:7E:88:14:35:17:5B:FD:5B:F0:CF:EA:FA:2C:3D:D4:B2:5F:CF:57";

    private SigningIdentity(){}

    public static String formatSha256(byte[] sha){
        if(sha==null||sha.length!=32)throw new IllegalArgumentException("INVALID_SIGNER_HASH");
        StringBuilder output=new StringBuilder(95);
        for(int i=0;i<sha.length;i++){
            if(i>0)output.append(':');
            output.append(String.format(Locale.ROOT,"%02X",sha[i]&0xff));
        }
        return output.toString();
    }

    public static String installedSigner(Context context){
        try{
            PackageManager pm=context.getPackageManager();
            PackageInfo pkg;
            if(Build.VERSION.SDK_INT>=33){
                pkg=pm.getPackageInfo(context.getPackageName(),
                    PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES));
            }else{
                pkg=pm.getPackageInfo(context.getPackageName(),
                    PackageManager.GET_SIGNING_CERTIFICATES);
            }
            if(pkg.signingInfo==null)return "UNAVAILABLE";
            Signature[] signers=pkg.signingInfo.getApkContentsSigners();
            if(signers==null||signers.length!=1)return "UNEXPECTED_MULTIPLE_SIGNERS";
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray());
            return formatSha256(digest);
        }catch(Exception error){return "UNAVAILABLE";}
    }

    public static boolean matchesPermanentOwner(Context context){
        return PERMANENT_SHA256.equals(installedSigner(context));
    }
}
