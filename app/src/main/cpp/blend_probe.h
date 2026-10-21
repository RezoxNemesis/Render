// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <string>

namespace render {

// This intentionally does not deserialize a .blend scene or claim to replace Blender BLO.
enum class BlendProbeStatus {
  StructuralIndex,
  IncompleteDNA,
  CompressedGzip,
  CompressedZstd,
  UnknownFutureFormat,
  InvalidStructure,
  IoError,
  InspectionLimit
};

struct BlendProbeResult {
  BlendProbeStatus status = BlendProbeStatus::InvalidStructure;
  int format_version = -1;
  int blender_version = 0;
  int pointer_size = 0;
  bool little_endian = true;
  uint64_t byte_size = 0;
  uint64_t block_count = 0;
  uint64_t dna_blocks = 0;
  uint64_t trailing_bytes = 0;
  std::string detail;
};

BlendProbeResult ProbeBlendFile(const std::string &path);
std::string ProbeToJson(const BlendProbeResult &result);
}  // namespace render
