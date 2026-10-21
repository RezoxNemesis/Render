// SPDX-License-Identifier: GPL-2.0-or-later
#include "BLI_math_half.hh"
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>
#define CHECK(x) do { if (!(x)) throw std::runtime_error("Blender math check failed"); } while(false)
int main() {
  using namespace blender::math;
  CHECK(float_to_half(1.0f) == 0x3c00);
  CHECK(float_to_half(-2.0f) == 0xc000);
  CHECK(half_to_float(0x3c00) == 1.0f);
  CHECK(half_to_float(0xc000) == -2.0f);
  CHECK(float_to_half(std::numeric_limits<float>::infinity()) == 0x7c00);
  CHECK(std::isnan(half_to_float(0x7e00)));
  float inputs[4] = {1.0f, -2.0f, 0.0f, 0.1f};
  uint16_t encoded[4] = {};
  float decoded[4] = {};
  float_to_half_array(inputs, encoded, 4);
  half_to_float_array(encoded, decoded, 4);
  for (int i=0;i<4;++i) {
    CHECK(encoded[i] == float_to_half(inputs[i]));
    CHECK(decoded[i] == half_to_float(encoded[i]));
  }
  std::puts("PASS upstream Blender BLI FP16 math");
  return 0;
}
