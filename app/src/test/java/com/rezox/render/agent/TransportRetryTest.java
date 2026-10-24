package com.rezox.render.agent;
import org.junit.Test;
import static org.junit.Assert.*;
public class TransportRetryTest {
    @Test public void failuresBackOffAndSuccessRestoresImmediatePoll(){
        TransportRetry retry=new TransportRetry();long now=1000;
        assertTrue(retry.ready(now));
        for(int i=0;i<12;i++){
            long delay=retry.failure(now,.5,0);
            assertTrue(delay>=5000&&delay<=300000);
            assertFalse(retry.ready(now+delay-1));assertTrue(retry.ready(now+delay));now+=delay;
        }
        retry.success();assertTrue(retry.ready(now));assertEquals(5000,retry.failure(now,.5,0));
    }
    @Test public void retryAfterIsHonoredAndUntrustedValuesAreBounded(){
        assertEquals(600000,TransportRetry.retryAfterMillis("600"));
        assertEquals(86400000,TransportRetry.retryAfterMillis("999999999"));
        for(String invalid:new String[]{null,"-1","NaN","9223372036854775807"})
            assertEquals(0,TransportRetry.retryAfterMillis(invalid));
        assertEquals(600000,new TransportRetry().failure(0,.1,600000));
    }
}
