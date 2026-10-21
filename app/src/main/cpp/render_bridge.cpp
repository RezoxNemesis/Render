// SPDX-License-Identifier: GPL-2.0-or-later
#include <jni.h>
#include <string>
#include "BLI_math_half.hh"
#include "blender_reader_adapter.hh"

#include "blend_probe.h"
#include "vulkan_capability.h"

extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_MainActivity_nativeEngineStatus(JNIEnv *env, jobject /* self */)
{
  const bool fp16 = blender::math::float_to_half(1.0f) == 0x3c00 &&
                    blender::math::half_to_float(0x3c00) == 1.0f;
  return env->NewStringUTF(fp16
      ? "Upstream Blender BLI math linked; Blender scene engine NOT integrated"
      : "Upstream Blender BLI math check failed; Blender engine NOT integrated");
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

extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_MainActivity_nativeRealBlenderHeader(
    JNIEnv *env, jobject /*self*/, jstring java_path)
{
  if (!java_path) return env->NewStringUTF("UPSTREAM_BLO_INVALID_PATH");
  const char *raw = env->GetStringUTFChars(java_path,nullptr);
  if (!raw) return env->NewStringUTF("UPSTREAM_BLO_INVALID_PATH");
  std::string path(raw);
  env->ReleaseStringUTFChars(java_path,raw);
  const std::string status=render::ProbeRealBlenderCoreHeader(path);
  return env->NewStringUTF(status.c_str());
}
