# Source-pinned Zstd 1.5.7. Source is downloaded at build time; Android runtime is offline.
include(FetchContent)
set(ZSTD_BUILD_PROGRAMS OFF CACHE BOOL "No CLI" FORCE)
set(ZSTD_BUILD_TESTS OFF CACHE BOOL "Render owns tests" FORCE)
set(ZSTD_BUILD_CONTRIB OFF CACHE BOOL "No contrib" FORCE)
set(ZSTD_BUILD_SHARED OFF CACHE BOOL "Link static Zstd in Android app" FORCE)
set(ZSTD_BUILD_STATIC ON CACHE BOOL "Static Zstd" FORCE)
set(ZSTD_MULTITHREAD_SUPPORT OFF CACHE BOOL "Portable Android thread model" FORCE)
set(ZSTD_BUILD_DICTBUILDER OFF CACHE BOOL "No dictionary creation" FORCE)
set(ZSTD_BUILD_COMPRESSION ON CACHE BOOL "Native regression test fixtures" FORCE)
set(ZSTD_BUILD_DECOMPRESSION ON CACHE BOOL "Native compressed data" FORCE)

set(RENDER_ZSTD_EXPECTED_COMMIT "f8745da6ff1ad1e7bab384bd1f9d742439278e99")
if(DEFINED RENDER_ZSTD_SOURCE_DIR)
  if(NOT EXISTS "${RENDER_ZSTD_SOURCE_DIR}/build/cmake/CMakeLists.txt")
    message(FATAL_ERROR "RENDER_ZSTD_SOURCE_DIR must be original Zstd tree")
  endif()
  add_subdirectory("${RENDER_ZSTD_SOURCE_DIR}/build/cmake"
                   "${CMAKE_CURRENT_BINARY_DIR}/zstd")
  set(RENDER_ZSTD_CHECKOUT_DIR "${RENDER_ZSTD_SOURCE_DIR}")
else()
  FetchContent_Declare(render_zstd
    GIT_REPOSITORY https://github.com/facebook/zstd.git
    GIT_TAG v1.5.7
    GIT_SHALLOW TRUE
    GIT_PROGRESS FALSE
    SOURCE_SUBDIR build/cmake)
  FetchContent_MakeAvailable(render_zstd)
  set(RENDER_ZSTD_CHECKOUT_DIR "${render_zstd_SOURCE_DIR}")
endif()

execute_process(COMMAND git rev-parse HEAD
  WORKING_DIRECTORY "${RENDER_ZSTD_CHECKOUT_DIR}"
  OUTPUT_VARIABLE RENDER_ZSTD_ACTUAL_COMMIT
  RESULT_VARIABLE RENDER_ZSTD_GIT_STATUS
  OUTPUT_STRIP_TRAILING_WHITESPACE)
if(NOT RENDER_ZSTD_GIT_STATUS EQUAL 0 OR
   NOT RENDER_ZSTD_ACTUAL_COMMIT STREQUAL RENDER_ZSTD_EXPECTED_COMMIT)
  message(FATAL_ERROR "Zstd checkout SHA mismatch; expected ${RENDER_ZSTD_EXPECTED_COMMIT}, got ${RENDER_ZSTD_ACTUAL_COMMIT}")
endif()
if(NOT TARGET libzstd_static)
  message(FATAL_ERROR "Pinned Zstd source did not supply libzstd_static")
endif()
set_target_properties(libzstd_static PROPERTIES POSITION_INDEPENDENT_CODE ON)
# Upstream libzstd_static already exports its build-directory include path.
