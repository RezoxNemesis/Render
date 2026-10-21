// SPDX-License-Identifier: GPL-2.0-or-later
#include <jni.h>
// Delegate to the very same native handlers used by MainActivity.
extern "C" jstring Java_com_rezox_render_MainActivity_nativeEngineStatus(JNIEnv *, jobject);
extern "C" jstring Java_com_rezox_render_MainActivity_nativeDnaCatalog(JNIEnv *, jobject, jstring);
extern "C" jstring Java_com_rezox_render_MainActivity_nativeGpuReport(JNIEnv *, jobject);
extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_agent_RenderNative_engineStatus(JNIEnv *env, jclass /*type*/) {
  return Java_com_rezox_render_MainActivity_nativeEngineStatus(env, nullptr);
}
extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_agent_RenderNative_inspectProject(JNIEnv *env, jclass /*type*/, jstring path) {
  return Java_com_rezox_render_MainActivity_nativeDnaCatalog(env, nullptr, path);
}
extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_agent_RenderNative_gpuInfo(JNIEnv *env, jclass /*type*/) {
  return Java_com_rezox_render_MainActivity_nativeGpuReport(env, nullptr);
}
