cmake_minimum_required(VERSION 3.22.1)
project(render_android LANGUAGES CXX)
add_library(render_bridge SHARED
    render_bridge.cpp
    blend_probe.cpp
    vulkan_capability.cpp)
target_compile_features(render_bridge PRIVATE cxx_std_17)
target_compile_options(render_bridge PRIVATE -Wall -Wextra -Werror)
target_link_libraries(render_bridge PRIVATE dl)
