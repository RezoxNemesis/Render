#include <jni.h>

extern "C" JNIEXPORT jstring JNICALL
Java_com_rezox_render_MainActivity_nativeEngineStatus(JNIEnv* env, jobject /* self */) {
    // No Blender core is linked. Report the true state until Android port passes tests.
    return env->NewStringUTF("JNI loaded; Blender engine NOT integrated; rendering unavailable");
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_rezox_render_MainActivity_nativeBlenderCoreReady(JNIEnv* /* env */, jobject /* self */) {
    return JNI_FALSE;
}
