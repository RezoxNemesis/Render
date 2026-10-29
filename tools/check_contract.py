#!/usr/bin/env python3
"""Structural release guards; functional relay, Java and native tests are separate."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
manifest=ET.parse(root/'app/src/main/AndroidManifest.xml').getroot()
ns='{http://schemas.android.com/apk/res/android}'
app=manifest.find('application')
permissions={x.get(ns+'name') for x in manifest.findall('uses-permission')}
service=app.find('service')
jni=(root/'app/src/main/cpp/render_bridge.cpp').read_text()
activity=(root/'app/src/main/java/com/rezox/render/MainActivity.java').read_text()
agent_screen=(root/'app/src/main/java/com/rezox/render/agent/AgentActivity.java').read_text()
actions=(root/'app/src/main/java/com/rezox/render/agent/AgentActions.java').read_text()
readme=(root/'README.md').read_text()
store=(root/'docs/ASSETS_AND_STORAGE.md').read_text()
required={
 'HTTPS only':app.get(ns+'usesCleartextTraffic')=='false',
 'no broad filesystem/gallery access':not permissions.intersection({'android.permission.MANAGE_EXTERNAL_STORAGE','android.permission.READ_EXTERNAL_STORAGE','android.permission.READ_MEDIA_IMAGES','android.permission.READ_MEDIA_VIDEO'}),
 'private agent service':service is not None and service.get(ns+'exported')=='false',
 'engine must not pretend ready':'JNI_FALSE' in jni and 'NOT integrated' in jni,
 'SAF import preserved':'ACTION_OPEN_DOCUMENT' in activity,
 'screen recording enabled for owner':'getWindow().addFlags' not in agent_screen and 'FLAG_SECURE' in agent_screen and 'clearFlags' in agent_screen,
 'enrollment credentials still masked':'StudioUi.field(this,"One-use Render Studio enrollment code",true)' in agent_screen,
 'professional native UI primitives':(root/'app/src/main/java/com/rezox/render/ui/StudioUi.java').is_file(),
 'local streaming':'InputStream' in activity and 'OutputStream' in activity,
 'honest engine status':'full ARM64 Android Blender application' in readme and
     '.put("engineIntegrated",editorReady)' in actions and 'NativeHeartbeat.ready(context)' in actions and
     'native results are reported' in readme,
 'Drive optional':'optional' in store and 'NO Blender factory assets have been uploaded' in store,
}
for name,ok in required.items():print(('PASS' if ok else 'FAIL')+' '+name)
sys.exit(0 if all(required.values()) else 1)
