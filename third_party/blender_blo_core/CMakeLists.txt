add_subdirectory(../render_zstd render_zstd)
add_subdirectory(../blender_allocator blender_allocator)
find_package(Python3 COMPONENTS Interpreter REQUIRED)
set(RENDER_ZSTD_READER "${CMAKE_CURRENT_BINARY_DIR}/blender-filereader-zstd.cc")
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../../tools/prepare_blender_zstd.py"
  "${RENDER_BLENDER_SOURCE_DIR}/source/blender/blenlib/intern/filereader_zstd.cc" "${RENDER_ZSTD_READER}"
  RESULT_VARIABLE ZSTD_PORT_RESULT)
if(NOT ZSTD_PORT_RESULT EQUAL 0)
  message(FATAL_ERROR "Pinned Blender Zstd port preparation failed")
endif()
add_library(blender_upstream_blo_core STATIC
  upstream/intern/blo_core_blend_header.cc
  upstream/intern/blo_core_bhead.cc
  "${RENDER_BLENDER_SOURCE_DIR}/source/blender/blenlib/intern/filereader_gzip.cc"
  "${RENDER_ZSTD_READER}"
  native/blender_reader_adapter.cc
  native/blender_assert_port.cc)
# No MEM_guardedalloc shim: the original public API comes from blender_upstream_allocator.
target_include_directories(blender_upstream_blo_core PUBLIC upstream upstream/blenlib native PRIVATE native/compat)
find_package(ZLIB REQUIRED)
target_link_libraries(blender_upstream_blo_core PUBLIC ZLIB::ZLIB libzstd_static blender_upstream_allocator)
target_compile_features(blender_upstream_blo_core PUBLIC cxx_std_20)
if(CMAKE_CXX_BYTE_ORDER STREQUAL "BIG_ENDIAN")
  target_compile_definitions(blender_upstream_blo_core PUBLIC __BIG_ENDIAN__=1)
else()
  target_compile_definitions(blender_upstream_blo_core PUBLIC __LITTLE_ENDIAN__=1)
endif()
