// SPDX-License-Identifier: GPL-2.0-or-later
// Read-only, bounded SDNA schema catalog using genuine upstream Blender BLO BHead decoders.
// Based on Blender makesdna/intern/dna_genfile.cc's NAME/TYPE/TLEN/STRC format.
// Do NOT claim this is Blender's full SDNA decode, .blend scene loader, or depsgraph.
#include "dna_catalog.h"

#include "blender_reader_adapter.hh"
#include "BLO_core_bhead.hh"
#include "BLO_core_blend_header.hh"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <utility>
#include <variant>
#include <vector>

namespace render {
namespace {
constexpr uint64_t kMaxDiagnosticBlocks = 1000000;
constexpr uint64_t kMaxSchemaBytes = 128ull * 1024ull * 1024ull;
constexpr uint32_t kMaxSchemaEntries = 1000000; // Diagnostic-only, not an engine project limit.
constexpr size_t kMaxPreviewTypes = 8;

const char *StatusName(DnaCatalogStatus status)
{
  switch (status) {
    case DnaCatalogStatus::Indexed: return "SCHEMA_INDEXED";
    case DnaCatalogStatus::NoSchema: return "NO_DNA1_BLOCK";
    case DnaCatalogStatus::CompressedNeedsUpstreamReader: return "COMPRESSED_NEEDS_UPSTREAM_READER";
    case DnaCatalogStatus::UnsupportedEndian: return "CROSS_ENDIAN_BHEAD_PENDING";
    case DnaCatalogStatus::UnrecognizedHeader: return "UNRECOGNIZED_HEADER";
    case DnaCatalogStatus::InvalidBlock: return "INVALID_BLOCK_STREAM";
    case DnaCatalogStatus::InvalidSchema: return "INVALID_DNA_SCHEMA";
    case DnaCatalogStatus::DiagnosticLimit: return "DIAGNOSTIC_LIMIT";
    case DnaCatalogStatus::IoError: return "IO_ERROR";
  }
  return "UNKNOWN";
}

DnaCatalogResult Fail(DnaCatalogResult r, DnaCatalogStatus status, const char *reason)
{
  r.status = status;
  r.message = reason;
  return r;
}

std::string EscapeJson(const std::string &s)
{
  std::ostringstream o;
  for (unsigned char c : s) {
    if (c == '"') o << "\\\"";
    else if (c == '\\') o << "\\\\";
    else if (c == '\n') o << "\\n";
    else if (c == '\r') o << "\\r";
    else if (c == '\t') o << "\\t";
    else if (c < 32) {
      const char digits[] = "0123456789abcdef";
      o << "\\u00" << digits[c >> 4] << digits[c & 15];
    }
    else o << static_cast<char>(c);
  }
  return o.str();
}

// This cursor never creates a pointer outside its allocated buffer.
class Cursor {
 public:
  explicit Cursor(const std::vector<uint8_t> &bytes) : bytes_(bytes) {}
  bool Tag(const char *tag)
  {
    if (!Fits(4)) return false;
    if (std::memcmp(bytes_.data() + pos_, tag, 4) != 0) return false;
    pos_ += 4;
    return true;
  }
  bool U16(uint16_t &out)
  {
    if (!Fits(2)) return false;
    out = uint16_t(bytes_[pos_]) | (uint16_t(bytes_[pos_ + 1]) << 8);
    pos_ += 2;
    return true;
  }
  bool U32(uint32_t &out)
  {
    if (!Fits(4)) return false;
    out = uint32_t(bytes_[pos_]) | (uint32_t(bytes_[pos_ + 1]) << 8) |
          (uint32_t(bytes_[pos_ + 2]) << 16) | (uint32_t(bytes_[pos_ + 3]) << 24);
    pos_ += 4;
    return true;
  }
  bool String(std::string &out)
  {
    if (pos_ >= bytes_.size()) return false;
    const size_t begin = pos_;
    while (pos_ < bytes_.size() && bytes_[pos_] != 0) pos_++;
    if (pos_ == bytes_.size() || pos_ == begin) return false;
    out.assign(reinterpret_cast<const char *>(bytes_.data() + begin), pos_ - begin);
    pos_++;
    return true;
  }
  bool Align4()
  {
    const size_t padding = (4 - (pos_ % 4)) % 4;
    if (!Fits(padding)) return false;
    pos_ += padding;
    return true;
  }
  bool Fits(size_t size) const
  {
    return size <= bytes_.size() - pos_;
  }
  bool Finished() const { return pos_ == bytes_.size(); }
 private:
  const std::vector<uint8_t> &bytes_;
  size_t pos_ = 0;
};

bool ReadCount(Cursor &cursor, uint32_t &count)
{
  if (!cursor.U32(count) || count == 0 || count > kMaxSchemaEntries) return false;
  return true;
}

bool DecodeSchema(const std::vector<uint8_t> &dna, DnaCatalogResult &result)
{
  Cursor in(dna);
  if (!in.Tag("SDNA") || !in.Tag("NAME")) return false;

  uint32_t count = 0;
  if (!ReadCount(in, count)) return false;
  // At least a NUL-terminated single-byte name per entry.
  if (!in.Fits(static_cast<size_t>(count) * 2)) return false;
  std::vector<std::string> names;
  names.reserve(count);
  for (uint32_t i = 0; i < count; ++i) {
    std::string name;
    if (!in.String(name)) return false;
    names.push_back(std::move(name));
  }
  if (!in.Align4() || !in.Tag("TYPE")) return false;
  if (!ReadCount(in, count)) return false;
  if (!in.Fits(static_cast<size_t>(count) * 2)) return false;
  std::vector<std::string> types;
  types.reserve(count);
  for (uint32_t i = 0; i < count; ++i) {
    std::string type;
    if (!in.String(type)) return false;
    types.push_back(std::move(type));
  }
  if (!in.Align4() || !in.Tag("TLEN")) return false;

  std::vector<uint16_t> lengths;
  lengths.reserve(types.size());
  for (size_t i = 0; i < types.size(); ++i) {
    uint16_t size = 0;
    if (!in.U16(size)) return false;
    lengths.push_back(size);
  }
  if (!in.Align4() || !in.Tag("STRC")) return false;
  if (!ReadCount(in, count)) return false;
  if (!in.Fits(static_cast<size_t>(count) * 4)) return false;

  std::vector<bool> seen_struct_type(types.size(), false);
  std::vector<std::string> preview;
  uint64_t total_fields = 0;
  for (uint32_t i = 0; i < count; ++i) {
    uint16_t type_index = 0;
    uint16_t member_count = 0;
    if (!in.U16(type_index) || !in.U16(member_count)) return false;
    if (type_index >= types.size() || member_count == 0 || member_count > 32767 ||
        seen_struct_type[type_index]) return false;
    seen_struct_type[type_index] = true;
    if (!in.Fits(static_cast<size_t>(member_count) * 4)) return false;
    if (preview.size() < kMaxPreviewTypes) preview.push_back(types[type_index]);
    // Real Blender validates struct sizes and arrays during its full DNA decode.
    // Here we only validate bounded field indices; never reconstruct scene memory.
    for (uint16_t m = 0; m < member_count; ++m) {
      uint16_t field_type = 0;
      uint16_t name_index = 0;
      if (!in.U16(field_type) || !in.U16(name_index) ||
          field_type >= types.size() || name_index >= names.size()) return false;
      ++total_fields;
    }
    (void)lengths[type_index];
  }
  if (!in.Finished()) return false;
  result.member_names = static_cast<uint32_t>(names.size());
  result.types = static_cast<uint32_t>(types.size());
  result.structures = count;
  result.structure_fields = total_fields;
  result.sample_structures = std::move(preview);
  result.message = "Indexed SDNA type and struct metadata only; Blender BKE scene is NOT loaded";
  return true;
}
}  // namespace

DnaCatalogResult InspectDnaCatalog(const std::string &path)
{
  DnaCatalogResult r;
  {
    std::ifstream magic(path, std::ios::binary);
    if (!magic) return Fail(r, DnaCatalogStatus::IoError, "Cannot open local file");
    std::array<unsigned char, 4> prefix{};
    magic.read(reinterpret_cast<char *>(prefix.data()), prefix.size());
    if (magic.gcount() >= 2 && prefix[0] == 0x1F && prefix[1] == 0x8B)
      return Fail(r, DnaCatalogStatus::CompressedNeedsUpstreamReader,
                  "Gzip file requires genuine Blender decompressing FileReader");
    if (magic.gcount() == 4 && prefix[0] == 0x28 && prefix[1] == 0xB5 &&
        prefix[2] == 0x2F && prefix[3] == 0xFD)
      return Fail(r, DnaCatalogStatus::CompressedNeedsUpstreamReader,
                  "Zstd file requires genuine Blender decompressing FileReader");
  }

  LocalBlendReader local(path);
  if (!local.IsOpen()) return Fail(r, DnaCatalogStatus::IoError, "Cannot open local .blend");
  blender::FileReader *reader = local.Raw();
  const auto decoded = blender::BLO_readfile_blender_header_decode(reader);
  const auto *header = std::get_if<blender::BlenderHeader>(&decoded);
  if (!header)
    return Fail(r, DnaCatalogStatus::UnrecognizedHeader,
                "Blender header invalid or unknown; do not guess future formats");
  r.blender_version = header->file_version;
  if (header->endian != 1)
    return Fail(r, DnaCatalogStatus::UnsupportedEndian,
                "Upstream BHead reader cannot decode cross-endian raw blocks yet");

  bool found_dna = false;
  for (uint64_t i = 0; i < kMaxDiagnosticBlocks; ++i) {
    const auto next = blender::BLO_readfile_read_bhead(reader, header->bhead_type());
    if (!next)
      return Fail(r, DnaCatalogStatus::InvalidBlock, "Truncated BHead or missing ENDB");
    const blender::BHead &b = *next;
    if (b.len < 0 || b.nr < 0)
      return Fail(r, DnaCatalogStatus::InvalidBlock, "Negative block size or count");
    ++r.blocks;
    if (b.code == blender::BLO_CODE_ENDB) {
      if (b.len != 0)
        return Fail(r, DnaCatalogStatus::InvalidBlock, "ENDB with a payload");
      if (!found_dna)
        return Fail(r, DnaCatalogStatus::NoSchema, "No DNA1 schema block");
      r.status = DnaCatalogStatus::Indexed;
      return r;
    }
    std::array<char, 4> code{};
    std::memcpy(code.data(), &b.code, 4);
    if (code[0] == 'O' && code[1] == 'B') ++r.object_blocks;
    if (code[0] == 'S' && code[1] == 'C') ++r.scene_blocks;
    if (code[0] == 'M' && code[1] == 'E') ++r.mesh_blocks;

    if (b.code == blender::BLO_CODE_DNA1) {
      if (found_dna) return Fail(r, DnaCatalogStatus::InvalidSchema, "Duplicate DNA1 block");
      if (static_cast<uint64_t>(b.len) > kMaxSchemaBytes)
        return Fail(r, DnaCatalogStatus::DiagnosticLimit,
                    "DNA1 exceeds diagnostic memory budget; full Blender engine must handle it");
      std::vector<uint8_t> dna(static_cast<size_t>(b.len));
      if (dna.empty() || reader->read(reader, dna.data(), dna.size()) !=
                             static_cast<int64_t>(dna.size()))
        return Fail(r, DnaCatalogStatus::InvalidBlock, "Truncated DNA1 payload");
      if (!DecodeSchema(dna, r))
        return Fail(r, DnaCatalogStatus::InvalidSchema, "Invalid SDNA NAME/TYPE/TLEN/STRC");
      found_dna = true;
    }
    else if (reader->seek(reader, static_cast<off64_t>(b.len), SEEK_CUR) < 0) {
      return Fail(r, DnaCatalogStatus::InvalidBlock, "Block length beyond local file bounds");
    }
  }
  return Fail(r, DnaCatalogStatus::DiagnosticLimit,
              "Block count exceeds diagnostic budget; not an engine scene-size limit");
}

std::string DnaCatalogJson(const DnaCatalogResult &r)
{
  std::ostringstream o;
  o << "{\"status\":\"" << StatusName(r.status)
    << "\",\"blenderVersion\":" << r.blender_version
    << ",\"blocks\":" << r.blocks
    << ",\"objectBlocks\":" << r.object_blocks
    << ",\"sceneBlocks\":" << r.scene_blocks
    << ",\"meshBlocks\":" << r.mesh_blocks
    << ",\"memberNames\":" << r.member_names
    << ",\"types\":" << r.types
    << ",\"structures\":" << r.structures
    << ",\"structureFields\":" << r.structure_fields
    << ",\"sampleStructures\":[";
  for (size_t i = 0; i < r.sample_structures.size(); ++i) {
    if (i) o << ",";
    o << "\"" << EscapeJson(r.sample_structures[i]) << "\"";
  }
  o << "],\"sceneLoaded\":false,\"engineIntegrated\":false,\"message\":\""
    << EscapeJson(r.message) << "\"}";
  return o.str();
}
}  // namespace render
