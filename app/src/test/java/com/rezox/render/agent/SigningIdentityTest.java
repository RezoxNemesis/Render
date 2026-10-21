package com.rezox.render.agent;
import org.junit.Test;
import static org.junit.Assert.*;

public final class SigningIdentityTest {
    @Test public void publicFingerprintUsesStableCanonicalFormatting(){
        byte[] digest=new byte[32];
        for(int i=0;i<32;i++)digest[i]=(byte)i;
        String rendered=SigningIdentity.formatSha256(digest);
        assertEquals("00:01:02:03:04:05:06:07:08:09:0A:0B:0C:0D:0E:0F:"+
          "10:11:12:13:14:15:16:17:18:19:1A:1B:1C:1D:1E:1F",rendered);
        assertEquals(95,rendered.length());
        assertEquals(95,SigningIdentity.PERMANENT_SHA256.length());
    }
    @Test public void rejectsInvalidDigestLength(){
        try{SigningIdentity.formatSha256(new byte[31]);fail();}
        catch(IllegalArgumentException expected){}
    }
}
