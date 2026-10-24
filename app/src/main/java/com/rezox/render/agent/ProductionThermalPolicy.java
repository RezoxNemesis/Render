package com.rezox.render.agent;

/** Pure gate shared by human-readable diagnostics and resumable frame runner.
 * Never considers a cool screen an override of the chip's thermal signal.
 */
public final class ProductionThermalPolicy {
    private ProductionThermalPolicy(){}
    public static final class Decision{
        public final boolean renderAllowed,statusUnavailable,lowerSamples;
        public final String reason;
        public final long cooldownMillis;
        public final int newResolution;
        Decision(boolean allow, boolean unavailable, String reason,long pauseMs){
            renderAllowed=allow;statusUnavailable=unavailable;this.reason=reason;cooldownMillis=pauseMs;
            lowerSamples=false;newResolution=0;
        }
    }
    public static String label(int status){
        switch(status){
            case 0:return "none";
            case 1:return "light";
            case 2:return "moderate";
            case 3:return "severe";
            case 4:return "critical";
            case 5:return "emergency";
            case 6:return "shutdown";
            default:return "unavailable";
        }
    }
    public static Decision evaluate(int thermalStatus,boolean memoryLow,long memoryAvailable,boolean cancelled){
        if(cancelled)return new Decision(false,thermalStatus<0,"CANCELLED",0);
        if(memoryLow || (memoryAvailable>=0&&memoryAvailable<256L*1024*1024))return new Decision(false,thermalStatus<0,"PAUSED_MEMORY_PRESSURE",20000);
        if(thermalStatus>=3)return new Decision(false,false,"PAUSED_THERMAL_PRESSURE",15000);
        if(thermalStatus==2)return new Decision(true,false,"MODERATE_THERMAL_LOAD",1500);
        return new Decision(true,thermalStatus<0,thermalStatus<0?"THERMAL_SENSOR_UNAVAILABLE":"READY",0);
    }
}
