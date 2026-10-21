// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace render {

// Diagnostic SDNA schema catalog, NOT a Blender scene/evaluation engine.
enum class DnaCatalogStatus {
  Indexed,
  NoSchema,
  CompressedNeedsUpstreamReader,
  UnsupportedEndian,
  UnrecognizedHeader,
  InvalidBlock,
  InvalidSchema,
  DiagnosticLimit,
  IoError
};

struct DnaCatalogResult {
  DnaCatalogStatus status = DnaCatalogStatus::IoError;
  int blender_version = 0;
  uint64_t blocks = 0;
  uint64_t object_blocks = 0;
  uint64_t scene_blocks = 0;
  uint64_t mesh_blocks = 0;
  uint32_t member_names = 0;
  uint32_t types = 0;
  uint32_t structures = 0;
  std::vector<std::string> sample_structures;
  std::string message;
};

DnaCatalogResult InspectDnaCatalog(const std::string &absolute_path);
std::string DnaCatalogJson(const DnaCatalogResult &catalog);

}  // namespace render
