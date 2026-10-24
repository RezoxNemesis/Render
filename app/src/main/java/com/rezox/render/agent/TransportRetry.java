package com.rezox.render.agent;

/** Bounded retry pacing, independent of command IDs and durable receipts. */
public final class TransportRetry {
    private int failures;
    private long nextAttempt;
    public boolean ready(long now) { return now>=nextAttempt; }
    public void success() { failures=0; nextAttempt=0; }
    public long failure(long now, double jitter, long serverDelay) {
        failures=Math.min(7,failures+1);
        long base=Math.min(300_000L,5_000L<<(failures-1));
        long delay=Math.max(Math.max(1000L,Math.min(86_400_000L,serverDelay)),
                Math.min(300_000L,(long)(base*(0.8+0.4*Math.max(0,Math.min(1,jitter))))));
        nextAttempt=now+delay;
        return delay;
    }
    public static long retryAfterMillis(String value) {
        if(value==null||!value.matches("[0-9]{1,9}"))return 0;
        return Math.min(86_400_000L,Long.parseLong(value)*1000L);
    }
}
