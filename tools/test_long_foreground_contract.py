#!/usr/bin/env python3
"""Build-time exact Android 14–16 long-render manifest contract.

No phone/render test is implied. The only package that may execute Blender is
still the original Render app; the 0.27 runtime adds a non-exported service.
"""
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tools.assemble_full_native import merge_manifest, ANDROID

class LongForegroundManifestTest(unittest.TestCase):
    def test_original_blender_still_present_service_owner_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"AndroidManifest.xml"
            path.write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android">'
                '<application><activity android:name="org.blender.blender.BlenderActivity"'
                ' android:exported="true">'
                '<intent-filter><action android:name="android.intent.action.MAIN"/></intent-filter>'
                '</activity></application></manifest>')
            doc=merge_manifest(path).getroot()
        app=doc.find("application")
        self.assertIsNotNone(app)
        services={x.get(ANDROID+"name"):x for x in app.findall("service")}
        name="com.rezox.render.agent.RenderLongForegroundService"
        self.assertIn(name,services)
        self.assertEqual(services[name].get(ANDROID+"exported"),"false")
        self.assertEqual(services[name].get(ANDROID+"foregroundServiceType"),
                         "mediaProcessing|specialUse")
        self.assertTrue(any(child.get(ANDROID+"name")==
            "android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE"
            for child in services[name].findall("property")))
        self.assertTrue(any(p.get(ANDROID+"name")==
            "android.permission.FOREGROUND_SERVICE_MEDIA_PROCESSING"
            for p in doc.findall("uses-permission")))
        self.assertTrue(any(p.get(ANDROID+"name")==
            "android.permission.WAKE_LOCK"
            for p in doc.findall("uses-permission")))
        self.assertEqual(len([x for x in services if x==name]),1)
        self.assertIsNotNone(next((a for a in app.findall("activity")
            if a.get(ANDROID+"name")=="org.blender.blender.BlenderActivity"),None))
        self.assertIsNone(doc.find(".//uses-permission[@android:name='android.permission.READ_MEDIA_IMAGES']",
            namespaces={"android":"http://schemas.android.com/apk/res/android"}))

if __name__=="__main__":
    unittest.main()
