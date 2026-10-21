// SPDX-License-Identifier: GPL-2.0-or-later
#include <jni.h>
#include <string>

#include "blend_probe.h"
#include "vulkan_capability.h"

extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_MainActivity_nativeEngineStatus(JNIEnv *env, jobject /* self */)
{
  return env->NewStringUTF(
      "Native format inspector available; Blender core NOT integrated; rendering unavailable");
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_rezox_render_MainActivity_nativeBlenderCoreReady(JNIEnv * /*env*/, jobject /*self*/)
{
  return JNI_FALSE;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_MainActivity_nativeInspectBlend(
    JNIEnv *env, jobject /*self*/, jstring java_path)
{
  if (!java_path) {
    return env->NewStringUTF("{\"status\":\"IO_ERROR\",\"engineIntegrated\":false}");
  }
  const char *raw_path = env->GetStringUTFChars(java_path, nullptr);
  if (!raw_path) {
    return env->NewStringUTF("{\"status\":\"IO_ERROR\",\"engineIntegrated\":false}");
  }
  const std::string path(raw_path);
  env->ReleaseStringUTFChars(java_path, raw_path);
  const std::string report = render::ProbeToJson(render::ProbeBlendFile(path));
  return env->NewStringUTF(report.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_MainActivity_nativeGpuReport(JNIEnv *env, jobject /*self*/)
{
  const std::string report = render::QueryVulkanCapabilities();
  return env->NewStringUTF(report.c_str());
}
