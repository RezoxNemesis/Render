// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Scope-limited compile shim; NOT Blender's full BLI_math_base.
#include <algorithm>
#include <cmath>
namespace blender::math {
template<typename T> inline T clamp(const T &v, const T &lo, const T &hi) {
  return std::clamp(v, lo, hi);
}
}
