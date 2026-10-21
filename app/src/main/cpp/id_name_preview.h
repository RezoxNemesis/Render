// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace render {
struct IdNameLayout {
  uint32_t name_offset = 0;
  uint32_t name_capacity = 0;
  int object_struct = -1;
  int mesh_struct = -1;
  int scene_struct = -1;
  bool valid = false;
};

struct SavedIdNames {
  std::vector<std::string> objects;
  std::vector<std::string> meshes;
  std::vector<std::string> scenes;
};

// Parse an SDNA member's array length with overflow checks.
bool DnaArrayCount(const std::string &member, uint64_t &result);

// Advance a particular SDNA struct member, recording ID.name layout when found.
bool AdvanceIdLayout(const std::string &member, const std::string &type,
                     uint16_t declared_type_bytes, uint32_t pointer_bytes,
                     uint64_t &byte_offset, IdNameLayout &layout);

// Re-read a .blend to extract bounded saved ID.name previews.
// Uses real Blender blenloader_core. NEVER evaluates or dereferences a saved pointer.
SavedIdNames PreviewSavedIdNames(const std::string &path, bool gzip,
                                const IdNameLayout &layout);
}  // namespace render
