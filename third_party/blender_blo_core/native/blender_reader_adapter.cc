// SPDX-License-Identifier: GPL-2.0-or-later
#include "blender_reader_adapter.hh"
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <sstream>
#include <variant>
#include "BLO_core_blend_header.hh"
#include "BLO_core_bhead.hh"

namespace render {
LocalBlendReader::LocalBlendReader(const std::string &path)
    : file_(path, std::ios::binary | std::ios::ate)
{
  if (!file_.is_open()) return;
  const std::streampos end = file_.tellg();
  if (end < std::streampos(0)) { file_.close(); return; }
  byte_size_ = static_cast<uint64_t>(static_cast<std::streamoff>(end));
  file_.seekg(0, std::ios::beg);
  read = &Read;
  seek = &Seek;
  close = &Close;
  offset = 0;
}

int64_t LocalBlendReader::Read(blender::FileReader *base, void *buffer, size_t length)
{
  auto *self = static_cast<LocalBlendReader *>(base);
  if (!self->IsOpen() || base->offset < 0) return 0;
  const uint64_t position = static_cast<uint64_t>(base->offset);
  if (position > self->byte_size_) return 0;
  const uint64_t requested = std::min<uint64_t>(length, self->byte_size_ - position);
  if (requested > static_cast<uint64_t>(std::numeric_limits<std::streamsize>::max())) return 0;
  self->file_.read(static_cast<char *>(buffer), static_cast<std::streamsize>(requested));
  const std::streamsize got = self->file_.gcount();
  if (got > 0) base->offset += static_cast<off64_t>(got);
  return static_cast<int64_t>(got);
}

off64_t LocalBlendReader::Seek(blender::FileReader *base, off64_t requested, int whence)
{
  auto *self = static_cast<LocalBlendReader *>(base);
  if (!self->IsOpen()) return -1;
  int64_t origin = 0;
  if (whence == SEEK_CUR) origin = base->offset;
  else if (whence == SEEK_END) {
    if (self->byte_size_ > static_cast<uint64_t>(INT64_MAX)) return -1;
    origin = static_cast<int64_t>(self->byte_size_);
  }
  else if (whence != SEEK_SET) return -1;
  // Check negative relative seeks without negating INT64_MIN (which is UB).
  if (requested < 0 && requested < -origin) return -1;
  if (requested > 0 && origin > INT64_MAX - requested) return -1;
  const int64_t destination = origin + requested;
  if (destination < 0 || static_cast<uint64_t>(destination) > self->byte_size_) return -1;
  self->file_.clear();
  self->file_.seekg(static_cast<std::streamoff>(destination), std::ios::beg);
  if (!self->file_.good()) return -1;
  base->offset = static_cast<off64_t>(destination);
  return base->offset;
}

void LocalBlendReader::Close(blender::FileReader *base)
{
  static_cast<LocalBlendReader *>(base)->file_.close();
}

std::string ProbeRealBlenderCoreHeader(const std::string &path)
{
  LocalBlendReader reader(path);
  if (!reader.IsOpen()) return "UPSTREAM_BLO_IO_ERROR";
  const auto header_variant = blender::BLO_readfile_blender_header_decode(reader.Raw());
  const auto *header = std::get_if<blender::BlenderHeader>(&header_variant);
  if (!header) return std::holds_alternative<blender::BlenderHeaderUnknown>(header_variant)
      ? "UPSTREAM_BLO_FUTURE_FORMAT"
      : "UPSTREAM_BLO_INVALID_HEADER";
  std::ostringstream result;
  result << "UPSTREAM_BLO_HEADER: format=" << header->file_format_version
         << " version=" << header->file_version
         << " pointerBytes=" << header->pointer_size
         << " endian=" << (header->endian == 1 ? "little" : "big");
  // Upstream BHead reader does not convert cross-endian raw block fields.
  if (header->endian != 1) {
    result << " BHead=NOT_PARSED_ENDIAN_PORT_PENDING";
    return result.str();
  }
  const auto block = blender::BLO_readfile_read_bhead(reader.Raw(), header->bhead_type());
  if (!block) {
    result << " firstBlock=TRUNCATED";
    return result.str();
  }
  std::array<char,5> code{};
  std::memcpy(code.data(), &block->code, 4);
  for (int i = 0; i < 4; ++i) {
    if (code[i] != '\0' && (code[i] < 32 || code[i] > 126)) code[i] = '?';
  }
  result << " firstBlock=" << code.data() << " payloadBytes=" << block->len
         << " (NOT a loaded Blender scene)";
  return result.str();
}
}  // namespace render
