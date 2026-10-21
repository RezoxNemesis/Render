// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Narrow allocation compatibility adapter for Blender's upstream gzip FileReader.
// DO NOT treat this as a replacement for guardedalloc or use it for scene memory.
#include <cstddef>
template<class T> T *MEM_new_zeroed(const char *) { return new T{}; }
template<class T> T *MEM_new_array_uninitialized(std::size_t count, const char *) {
  return new T[count];
}
template<class T> void MEM_delete(T *p) { delete p; }
