package com.rezox.render.agent;
import org.junit.Test;
import static org.junit.Assert.*;
/** Thermals are Android sensor reports, not touchscreen warmth. */
public class ProductionThermalPolicyTest {
    @Test public void severeAlwaysPausesWithoutChangingRenderQuality(){
        for(int t=3;t<=6;t++){
            ProductionThermalPolicy.Decision d=ProductionThermalPolicy.evaluate(t,false,4L*1024*1024*1024,false);
            assertFalse(d.renderAllowed);assertEquals("PAUSED_THERMAL_PRESSURE",d.reason);
            assertEquals(0,d.newResolution);assertFalse(d.lowerSamples);
        }
    }
    @Test public void lightAndModerateCanProceedAtOriginalSettings(){
        assertTrue(ProductionThermalPolicy.evaluate(1,false,3L*1024*1024*1024,false).renderAllowed);
        ProductionThermalPolicy.Decision d=ProductionThermalPolicy.evaluate(2,false,3L*1024*1024*1024,false);
        assertTrue(d.renderAllowed);assertTrue(d.cooldownMillis>=0);
    }
    @Test public void lowMemoryAlwaysPausesAndMissingSensorIsExplicit(){
        assertEquals("PAUSED_MEMORY_PRESSURE",ProductionThermalPolicy.evaluate(1,true,100_000_000L,false).reason);
        assertEquals("PAUSED_MEMORY_PRESSURE",ProductionThermalPolicy.evaluate(0,false,200_000_000L,false).reason);
        ProductionThermalPolicy.Decision unknown=ProductionThermalPolicy.evaluate(-1,false,2_000_000_000L,false);
        assertTrue(unknown.renderAllowed);assertTrue(unknown.statusUnavailable);
    }
    @Test public void neverClaimsUnmeasuredHotPhoneOrUnlimitedSpeed(){
        assertEquals("none",ProductionThermalPolicy.label(0));
        assertEquals("severe",ProductionThermalPolicy.label(3));
        assertEquals("unavailable",ProductionThermalPolicy.label(-1));
        assertEquals("critical",ProductionThermalPolicy.label(4));
    }
}