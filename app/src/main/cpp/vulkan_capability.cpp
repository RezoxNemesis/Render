// SPDX-License-Identifier: GPL-2.0-or-later
// Dynamically query the on-phone Vulkan loader, never require a Vulkan-capable GPU to launch.
#include "vulkan_capability.h"

#include <dlfcn.h>
#include <vulkan/vulkan.h>
#include <algorithm>
#include <cstdint>
#include <sstream>
#include <string>
#include <vector>

namespace render {
namespace {

class SharedLibrary {
 public:
  explicit SharedLibrary(const char *path) : handle_(dlopen(path, RTLD_NOW | RTLD_LOCAL)) {}
  ~SharedLibrary() { if (handle_) dlclose(handle_); }
  void *Symbol(const char *name) const { return handle_ ? dlsym(handle_, name) : nullptr; }
  bool Loaded() const { return handle_ != nullptr; }
  SharedLibrary(const SharedLibrary &) = delete;
  SharedLibrary &operator=(const SharedLibrary &) = delete;

 private:
  void *handle_;
};

std::string Printable(const char *name)
{
  std::string value;
  for (size_t i = 0; i < VK_MAX_PHYSICAL_DEVICE_NAME_SIZE && name[i] != '\0'; ++i) {
    const unsigned char ch = static_cast<unsigned char>(name[i]);
    value.push_back(ch >= 32 && ch <= 126 ? static_cast<char>(ch) : '_');
  }
  return value;
}
}  // namespace

std::string QueryVulkanCapabilities()
{
  SharedLibrary loader("libvulkan.so");
  if (!loader.Loaded()) {
    return "Android Vulkan loader not available. This does not disable CPU-side Blender targets.";
  }
  auto get_proc = reinterpret_cast<PFN_vkGetInstanceProcAddr>(
      loader.Symbol("vkGetInstanceProcAddr"));
  if (!get_proc) return "Vulkan loader exists but vkGetInstanceProcAddr is unavailable.";

  auto create = reinterpret_cast<PFN_vkCreateInstance>(
      get_proc(VK_NULL_HANDLE, "vkCreateInstance"));
  if (!create) return "Vulkan instance creation entry point unavailable.";

  VkApplicationInfo app_info{};
  app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
  app_info.pApplicationName = "Render Android hardware probe";
  app_info.applicationVersion = VK_MAKE_VERSION(0, 2, 0);
  app_info.pEngineName = "Blender port capability inventory (not a renderer)";
  app_info.engineVersion = VK_MAKE_VERSION(0, 0, 0);
  app_info.apiVersion = VK_API_VERSION_1_0;
  VkInstanceCreateInfo create_info{};
  create_info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
  create_info.pApplicationInfo = &app_info;
  VkInstance instance = VK_NULL_HANDLE;
  const VkResult create_result = create(&create_info, nullptr, &instance);
  if (create_result != VK_SUCCESS || instance == VK_NULL_HANDLE) {
    return "Vulkan instance not supported on this device (VkResult " +
           std::to_string(static_cast<int>(create_result)) + ").";
  }

  auto destroy = reinterpret_cast<PFN_vkDestroyInstance>(
      get_proc(instance, "vkDestroyInstance"));
  auto enumerate = reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(
      get_proc(instance, "vkEnumeratePhysicalDevices"));
  auto get_properties = reinterpret_cast<PFN_vkGetPhysicalDeviceProperties>(
      get_proc(instance, "vkGetPhysicalDeviceProperties"));
  auto get_features = reinterpret_cast<PFN_vkGetPhysicalDeviceFeatures>(
      get_proc(instance, "vkGetPhysicalDeviceFeatures"));
  auto get_memory = reinterpret_cast<PFN_vkGetPhysicalDeviceMemoryProperties>(
      get_proc(instance, "vkGetPhysicalDeviceMemoryProperties"));
  if (!destroy || !enumerate || !get_properties || !get_features || !get_memory) {
    if (destroy) destroy(instance, nullptr);
    return "Vulkan loader is missing required physical device query functions.";
  }
  uint32_t count = 0;
  VkResult result = enumerate(instance, &count, nullptr);
  if (result != VK_SUCCESS || count == 0) {
    destroy(instance, nullptr);
    return "No Vulkan-compatible physical GPU reported by the Android Vulkan loader.";
  }
  // Safety bound applies to diagnostics only, not Blender scene or object limits.
  count = std::min(count, 32u);
  std::vector<VkPhysicalDevice> devices(count, VK_NULL_HANDLE);
  result = enumerate(instance, &count, devices.data());
  if (result != VK_SUCCESS && result != VK_INCOMPLETE) {
    destroy(instance, nullptr);
    return "Vulkan physical GPU enumeration failed (VkResult " +
           std::to_string(static_cast<int>(result)) + ").";
  }

  std::ostringstream report;
  report << "On-device Vulkan probe (NO scene renderer): ";
  for (uint32_t i = 0; i < count; ++i) {
    VkPhysicalDeviceProperties props{};
    VkPhysicalDeviceFeatures features{};
    VkPhysicalDeviceMemoryProperties memory{};
    get_properties(devices[i], &props);
    get_features(devices[i], &features);
    get_memory(devices[i], &memory);
    uint64_t device_local_bytes = 0;
    for (uint32_t h = 0; h < memory.memoryHeapCount; ++h) {
      if ((memory.memoryHeaps[h].flags & VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) != 0) {
        device_local_bytes += memory.memoryHeaps[h].size;
      }
    }
    if (i != 0) report << " | ";
    report << Printable(props.deviceName)
           << " Vulkan " << VK_VERSION_MAJOR(props.apiVersion)
           << "." << VK_VERSION_MINOR(props.apiVersion)
           << " max2D=" << props.limits.maxImageDimension2D
           << " geometryShader=" << (features.geometryShader ? "yes" : "no")
           << " tessellationShader=" << (features.tessellationShader ? "yes" : "no")
           << " shaderInt64=" << (features.shaderInt64 ? "yes" : "no")
           << " deviceLocalHeapMiB=" << (device_local_bytes / (1024u * 1024u));
  }
  destroy(instance, nullptr);
  return report.str();
}
}  // namespace render
