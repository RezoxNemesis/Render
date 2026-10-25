package com.rezox.render.agent;

import android.content.Context;
import android.content.Intent;
import android.os.BatteryManager;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=33,manifest=Config.NONE)
public class ProductionThermalTelemetryTest {
    @Test public void absentTemperatureIsUnavailableNotMinusPointOneDegrees()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        context.sendStickyBroadcast(new Intent(Intent.ACTION_BATTERY_CHANGED));
        assertTrue(ProductionThermalTelemetry.sample(context).isNull("battery_temperature_celsius"));
    }
    @Test public void actualNegativeTemperatureIsStillValidTelemetry()throws Exception{
        Context context=RuntimeEnvironment.getApplication();
        context.sendStickyBroadcast(new Intent(Intent.ACTION_BATTERY_CHANGED)
            .putExtra(BatteryManager.EXTRA_TEMPERATURE,-1));
        JSONObject reading=ProductionThermalTelemetry.sample(context);
        assertEquals(-0.1,reading.getDouble("battery_temperature_celsius"),0.001);
        assertFalse(reading.getBoolean("battery_temperature_is_cpu_temperature"));
    }
}
