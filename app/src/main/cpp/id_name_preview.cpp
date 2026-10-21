// SPDX-License-Identifier: GPL-2.0-or-later
#include "id_name_preview.h"
#include "blender_reader_adapter.hh"
#include "BLO_core_bhead.hh"
#include "BLO_core_blend_header.hh"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <variant>
#include <vector>

namespace render {
bool DnaArrayCount(const std::string &member, uint64_t &result)
{
  result = 1;
  size_t begin = 0;
  while ((begin = member.find('[', begin)) != std::string::npos) {
    const size_t end = member.find(']', begin + 1);
    if (end == std::string::npos || end == begin + 1) return false;
    uint64_t dimension = 0;
    for (size_t i = begin + 1; i < end; ++i) {
      if (member[i] < '0' || member[i] > '9') return false;
      dimension = dimension * 10 + static_cast<unsigned>(member[i] - '0');
      if (dimension > 1000000) return false;
    }
    if (dimension == 0 || result > 1000000 / dimension) return false;
    result *= dimension;
    begin = end + 1;
  }
  return true;
}

bool AdvanceIdLayout(const std::string &member, const std::string &type,
                     uint16_t declared_type_bytes, uint32_t pointer_bytes,
                     uint64_t &byte_offset, IdNameLayout &layout)
{
  uint64_t count = 1;
  if (!DnaArrayCount(member, count)) return false;
  const size_t bracket = member.find('[');
  const size_t asterisk = member.find('*');
  const bool pointer = asterisk != std::string::npos &&
                       (bracket == std::string::npos || asterisk < bracket);
  const uint64_t element_bytes = pointer ? pointer_bytes : declared_type_bytes;
  if (element_bytes > 65536 || count > 65536 ||
      (element_bytes != 0 && count > 65536 / element_bytes))
    return false;
  const uint64_t length = count * element_bytes;
  if (byte_offset > 65536 || length > 65536 - byte_offset) return false;
  if (!pointer && type == "char" && member.rfind("name[", 0) == 0 &&
      count > 2 && count <= 4096) {
    layout.name_offset = static_cast<uint32_t>(byte_offset);
    layout.name_capacity = static_cast<uint32_t>(count);
    layout.valid = true;
  }
  byte_offset += length;
  return true;
}

namespace {
std::string ExtractName(const std::vector<unsigned char> &bytes,
                        const IdNameLayout &layout, const std::array<char, 4> &code)
{
  const size_t offset = layout.name_offset;
  if (!layout.valid || offset + 2 >= bytes.size() ||
      bytes[offset] != static_cast<unsigned char>(code[0]) ||
      bytes[offset + 1] != static_cast<unsigned char>(code[1])) return {};
  const size_t start = offset + 2;
  const size_t count = std::min(static_cast<size_t>(layout.name_capacity - 2),
                                 bytes.size() - start);
  std::string value;
  for (size_t i = 0; i < count; ++i) {
    const unsigned char c = bytes[start + i];
    if (c == 0) break;
    if (c < 32 || c == 127) return {};
    value.push_back(static_cast<char>(c));
  }
  return value;
}
}  // namespace

SavedIdNames PreviewSavedIdNames(const std::string &path, bool gzip,
                                const IdNameLayout &layout)
{
  SavedIdNames out;
  if (!layout.valid) return out;
  LocalBlendReader local(path);
  if (!local.IsOpen()) return out;
  struct ScopedCompressed {
    blender::FileReader *reader = nullptr;
    ~ScopedCompressed() { if (reader) reader->close(reader); }
  } compressed;
  blender::FileReader *reader = local.Raw();
  if (gzip) {
    compressed.reader = blender::BLI_filereader_new_gzip(local.Raw());
    if (!compressed.reader) return out;
    reader = compressed.reader;
  }
  const auto parsed = blender::BLO_readfile_blender_header_decode(reader);
  const auto *header = std::get_if<blender::BlenderHeader>(&parsed);
  if (!header || header->endian != 1) return out;

  constexpr size_t kPreviewCount = 12;  // Only the optional UI preview is bounded.
  constexpr uint64_t kPreviewBytes = 512ull * 1024ull * 1024ull;
  constexpr uint64_t kMaxBlocks = 1000000;
  uint64_t bytes_processed = 0;
  for (uint64_t n = 0; n < kMaxBlocks; ++n) {
    const auto block = blender::BLO_readfile_read_bhead(reader, header->bhead_type());
    if (!block || block->len < 0) return out;
    if (block->code == blender::BLO_CODE_ENDB) return out;
    const uint64_t length = static_cast<uint64_t>(block->len);
    if (bytes_processed > kPreviewBytes || length > kPreviewBytes - bytes_processed)
      return out;
    bytes_processed += length;

    std::array<char, 4> code{};
    std::memcpy(code.data(), &block->code, 4);
    std::vector<std::string> *names = nullptr;
    if (code[0] == 'O' && code[1] == 'B' && block->SDNAnr == layout.object_struct)
      names = &out.objects;
    if (code[0] == 'M' && code[1] == 'E' && block->SDNAnr == layout.mesh_struct)
      names = &out.meshes;
    if (code[0] == 'S' && code[1] == 'C' && block->SDNAnr == layout.scene_struct)
      names = &out.scenes;

    uint64_t remaining = length;
    if (names && names->size() < kPreviewCount && length > layout.name_offset + 2) {
      const uint64_t wanted = std::min<uint64_t>(
          length, static_cast<uint64_t>(layout.name_offset) + layout.name_capacity);
      std::vector<unsigned char> sample(static_cast<size_t>(wanted));
      const int64_t received = reader->read(reader, sample.data(), sample.size());
      if (received != static_cast<int64_t>(wanted)) return out;
      remaining -= wanted;
      auto name = ExtractName(sample, layout, code);
      if (!name.empty()) names->push_back(std::move(name));
    }
    if (remaining == 0) continue;
    if (!gzip) {
      if (reader->seek(reader, static_cast<off64_t>(remaining), SEEK_CUR) < 0) return out;
    }
    else {
      std::array<unsigned char, 65536> scratch{};
      while (remaining > 0) {
        const size_t step = static_cast<size_t>(std::min<uint64_t>(remaining, scratch.size()));
        const int64_t count = reader->read(reader, scratch.data(), step);
        if (count <= 0 || static_cast<uint64_t>(count) > remaining) return out;
        remaining -= static_cast<uint64_t>(count);
      }
    }
  }
  return out;
}
}  // namespace render
