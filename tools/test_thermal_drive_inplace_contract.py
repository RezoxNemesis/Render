import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

BASE=Path(__file__).resolve().parents[1]
def source(p):return (BASE/p).read_text()

class ThermalDriveInplaceTests(unittest.TestCase):
    def test_no_release_signer_rotation_or_force_uninstall(self):
        ci=source('.github/workflows/full-native-apk.yml')
        self.assertIn('fail-on-cache-miss: true',ci)
        self.assertIn('f3d63fb20be25ca0be8aa6a161d5cf13cd98ba2fa300c7a604cce35131b9eb30',ci.lower())
        self.assertNotIn('keytool -genkeypair',ci)
        self.assertNotIn('adb uninstall',ci)
        self.assertIn("versionCode='28'",ci)
        prep=source('tools/prepare_production_toolkit.py')
        self.assertIn('versionCode = 24',prep)
        self.assertIn('versionCode = 25',(ROOT/'tools/prepare_v23_reference.py').read_text())
        self.assertIn('0.21.0-native-thermal-batch-drive',prep)
    def test_batch_uses_native_bpy_and_never_cloud_renders(self):
        s=source('app/src/main/java/com/rezox/render/agent/ProductionBatch.java')
        self.assertIn('new BlenderSpool(context).execute("blender.production.execute"',s)
        self.assertIn('AtomicBoolean',s)
        self.assertIn('max_frames',s)
        self.assertIn('expected_fingerprint',s)
        self.assertIn('Thread.sleep(5000)',s)
        self.assertNotIn('ProcessBuilder',s)
        self.assertNotIn('Realize Instances',s)
    def test_thermal_sensor_is_never_misinterpreted_as_surface_touch(self):
        s=source('app/src/main/java/com/rezox/render/agent/ProductionThermalPolicy.java')
        self.assertIn('thermalStatus>=3',s)
        self.assertIn('PAUSED_THERMAL_PRESSURE',s)
        self.assertIn('lowerSamples=false',s)
        self.assertIn('newResolution=0',s)
        d=source('app/src/main/java/com/rezox/render/agent/ProductionThermalTelemetry.java')
        self.assertIn('getCurrentThermalStatus()',d)
        self.assertIn('getThermalHeadroom(10)',d)
        self.assertIn('battery_temperature_is_cpu_temperature',d)
    def test_drive_is_owner_granted_storage_not_compute(self):
        s=source('app/src/main/java/com/rezox/render/agent/ProductionDriveStorage.java')
        self.assertIn('Intent.ACTION_OPEN_DOCUMENT_TREE',s)
        self.assertIn('takePersistableUriPermission',s)
        self.assertIn('DocumentsContract.createDocument',s)
        self.assertIn('provider_write_completed',s)
        self.assertIn('remote_sync_verified',s)
        self.assertIn('cloud_rendering',s)
        self.assertNotIn('AccountManager',s)
        self.assertNotIn('drive.files.list',s)
    def test_connection_keeps_same_app_identity(self):
        s=source('app/src/main/java/com/rezox/render/agent/ProductionBridge.java')
        self.assertIn('render.batch',s)
        self.assertIn('drive.status',s)
        self.assertIn('drive.backup',s)
        self.assertIn('RENDER_TARGET_ID_REQUIRED_OR_MISMATCH',s)
        self.assertIn('ProductionBatch.advance',s)
        self.assertIn('ProductionDriveStorage.backup',s)

if __name__=='__main__':unittest.main()
