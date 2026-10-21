add_library(blender_upstream_blo_core STATIC
  upstream/intern/blo_core_blend_header.cc
  upstream/intern/blo_core_bhead.cc
  native/blender_reader_adapter.cc
  native/blender_assert_port.cc
)
target_include_directories(blender_upstream_blo_core PUBLIC upstream upstream/blenlib native)
target_compile_features(blender_upstream_blo_core PUBLIC cxx_std_20)
if(CMAKE_CXX_BYTE_ORDER STREQUAL "BIG_ENDIAN")
  target_compile_definitions(blender_upstream_blo_core PUBLIC __BIG_ENDIAN__=1)
else()
  target_compile_definitions(blender_upstream_blo_core PUBLIC __LITTLE_ENDIAN__=1)
endif()
