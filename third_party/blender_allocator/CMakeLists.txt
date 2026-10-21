# Complete original Blender guardedalloc source module, not an allocator imitation.
find_package(Python3 COMPONENTS Interpreter REQUIRED)
find_package(Threads REQUIRED)
set(RENDER_BLENDER_SOURCE_DIR "${CMAKE_CURRENT_LIST_DIR}/../../.deps/blender-core" CACHE PATH "Pristine pinned Blender source checkout")
execute_process(
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_LIST_DIR}/../../tools/fetch_blender_subset.py" --destination "${RENDER_BLENDER_SOURCE_DIR}"
  RESULT_VARIABLE RENDER_BLENDER_FETCH_RESULT)
if(NOT RENDER_BLENDER_FETCH_RESULT EQUAL 0)
  message(FATAL_ERROR "Cannot verify/fetch the pinned original Blender source subset")
endif()

# Stage only allocator internals to keep the upstream checkout unmodified.
set(RENDER_ALLOCATOR_STAGE "${CMAKE_CURRENT_BINARY_DIR}/allocator-src")
file(MAKE_DIRECTORY "${RENDER_ALLOCATOR_STAGE}")
file(GLOB RENDER_ALLOCATOR_INTERNALS "${RENDER_BLENDER_SOURCE_DIR}/intern/guardedalloc/intern/*.cc" "${RENDER_BLENDER_SOURCE_DIR}/intern/guardedalloc/intern/*.hh")
foreach(source IN LISTS RENDER_ALLOCATOR_INTERNALS)
  get_filename_component(name "${source}" NAME)
  configure_file("${source}" "${RENDER_ALLOCATOR_STAGE}/${name}" COPYONLY)
endforeach()

# Android has malloc_usable_size, but not glibc malloc_stats. Preserve accounting.
file(READ "${RENDER_ALLOCATOR_STAGE}/mallocn_intern.hh" allocator_header)
string(REPLACE "#elif defined(__FreeBSD__)" "#elif defined(__ANDROID__)\n#  include <malloc.h>\n#elif defined(__FreeBSD__)" allocator_header "${allocator_header}")
file(WRITE "${RENDER_ALLOCATOR_STAGE}/mallocn_intern.hh" "${allocator_header}")
add_library(blender_upstream_allocator STATIC
  "${RENDER_ALLOCATOR_STAGE}/leak_detector.cc"
  "${RENDER_ALLOCATOR_STAGE}/mallocn.cc"
  "${RENDER_ALLOCATOR_STAGE}/mallocn_guarded_impl.cc"
  "${RENDER_ALLOCATOR_STAGE}/mallocn_lockfree_impl.cc"
  "${RENDER_ALLOCATOR_STAGE}/memory_usage.cc")
target_include_directories(blender_upstream_allocator PUBLIC "${RENDER_BLENDER_SOURCE_DIR}/intern/guardedalloc"
  PRIVATE "${RENDER_BLENDER_SOURCE_DIR}/intern/atomic" "${RENDER_BLENDER_SOURCE_DIR}/intern/profile")
target_compile_features(blender_upstream_allocator PUBLIC cxx_std_20)
target_link_libraries(blender_upstream_allocator PUBLIC Threads::Threads)
set_target_properties(blender_upstream_allocator PROPERTIES POSITION_INDEPENDENT_CODE ON)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux" AND NOT ANDROID)
  target_compile_definitions(blender_upstream_allocator PRIVATE HAVE_MALLOC_STATS_H=1)
endif()
