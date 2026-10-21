// SPDX-License-Identifier: GPL-2.0-or-later
// Bounded, read-only inspector for the real Blender .blend on-disk framing.
// Format reference: blender/blender:
// source/blender/blenloader_core/BLO_core_blend_header.hh and BLO_core_bhead.hh.
#include "blend_probe.h"

#include <array>
#include <cctype>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <string>

namespace render {
namespace {

constexpr uint64_t kMaxIndexedBlocks = 4000000;
constexpr size_t kLegacyHeaderSize = 12;
constexpr size_t kCurrentHeaderSize = 17;

bool ReadAt(std::ifstream &file, uint64_t offset, void *dest, size_t size, uint64_t total)
{
  if (offset > total || size > total - offset ||
      offset > static_cast<uint64_t>(std::numeric_limits<std::streamoff>::max())) {
    return false;
  }
  file.clear();
  file.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
  if (!file.good()) {
    return false;
  }
  file.read(static_cast<char *>(dest), static_cast<std::streamsize>(size));
  return file.gcount() == static_cast<std::streamsize>(size);
}

bool Digits(const unsigned char *bytes, size_t n)
{
  for (size_t i = 0; i < n; i++) {
    if (bytes[i] < '0' || bytes[i] > '9') {
      return false;
    }
  }
  return true;
}

int ParseDigits(const unsigned char *bytes, size_t n)
{
  int value = 0;
  for (size_t i = 0; i < n; i++) {
    value = value * 10 + int(bytes[i] - '0');
  }
  return value;
}

uint64_t ReadInteger(const unsigned char *bytes, int count, bool little)
{
  uint64_t out = 0;
  for (int i = 0; i < count; i++) {
    out = (out << 8u) | static_cast<uint64_t>(bytes[little ? count - i - 1 : i]);
  }
  return out;
}

BlendProbeResult Failure(BlendProbeResult result, BlendProbeStatus status, const char *text)
{
  result.status = status;
  result.detail = text;
  return result;
}

const char *StatusName(BlendProbeStatus status)
{
  switch (status) {
    case BlendProbeStatus::StructuralIndex: return "STRUCTURAL_INDEX";
    case BlendProbeStatus::IncompleteDNA: return "MISSING_DNA";
    case BlendProbeStatus::CompressedGzip: return "GZIP_REQUIRES_BLENDER_READER";
    case BlendProbeStatus::CompressedZstd: return "ZSTD_REQUIRES_BLENDER_READER";
    case BlendProbeStatus::UnknownFutureFormat: return "UNRECOGNIZED_BLENDER_VERSION";
    case BlendProbeStatus::InvalidStructure: return "INVALID_STRUCTURE";
    case BlendProbeStatus::IoError: return "IO_ERROR";
    case BlendProbeStatus::InspectionLimit: return "INSPECTION_LIMIT";
  }
  return "UNKNOWN";
}

std::string EscapeJson(const std::string &text)
{
  std::ostringstream out;
  for (unsigned char ch : text) {
    switch (ch) {
      case '"': out << "\\\""; break;
      case '\\': out << "\\\\"; break;
      case '\n': out << "\\n"; break;
      case '\r': out << "\\r"; break;
      case '\t': out << "\\t"; break;
      default:
        if (ch < 32) {
          out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(ch)
              << std::dec;
        }
        else {
          out << static_cast<char>(ch);
        }
    }
  }
  return out.str();
}

}  // namespace

BlendProbeResult ProbeBlendFile(const std::string &path)
{
  BlendProbeResult result;
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) {
    return Failure(result, BlendProbeStatus::IoError, "Cannot open local file");
  }
  const std::streampos end_position = file.tellg();
  if (end_position < std::streampos(0)) {
    return Failure(result, BlendProbeStatus::IoError, "Cannot determine file size");
  }
  const uint64_t total = static_cast<uint64_t>(static_cast<std::streamoff>(end_position));
  result.byte_size = total;
  std::array<unsigned char, kCurrentHeaderSize> header{};
  if (total < 4 || !ReadAt(file, 0, header.data(), static_cast<size_t>(total < 12 ? total : 12), total)) {
    return Failure(result, BlendProbeStatus::InvalidStructure, "File is too short for a Blender header");
  }
  if (header[0] == 0x1F && header[1] == 0x8B) {
    return Failure(result, BlendProbeStatus::CompressedGzip,
                   "Gzip-compressed Blender candidate. Only upstream Blender BLO can validate its contents");
  }
  if (header[0] == 0x28 && header[1] == 0xB5 &&
      header[2] == 0x2F && header[3] == 0xFD) {
    return Failure(result, BlendProbeStatus::CompressedZstd,
                   "Zstd-compressed Blender candidate. Only upstream Blender BLO can validate its contents");
  }
  if (total < kLegacyHeaderSize || std::memcmp(header.data(), "BLENDER", 7) != 0) {
    return Failure(result, BlendProbeStatus::InvalidStructure, "Missing valid BLENDER file signature");
  }

  size_t header_size = kLegacyHeaderSize;
  size_t bhead_size = 0;
  if (header[7] == '_' || header[7] == '-') {
    result.format_version = 0;
    result.pointer_size = header[7] == '_' ? 4 : 8;
    if (header[8] != 'v' && header[8] != 'V') {
      return Failure(result, BlendProbeStatus::UnknownFutureFormat,
                     "Unrecognized legacy endian field");
    }
    result.little_endian = header[8] == 'v';
    if (!Digits(header.data() + 9, 3)) {
      return Failure(result, BlendProbeStatus::UnknownFutureFormat, "Invalid legacy version");
    }
    result.blender_version = ParseDigits(header.data() + 9, 3);
    bhead_size = result.pointer_size == 4 ? 20 : 24;
  }
  else {
    if (!Digits(header.data() + 7, 2) || ParseDigits(header.data() + 7, 2) != 17) {
      return Failure(result, BlendProbeStatus::UnknownFutureFormat,
                     "Unknown Blender file header length");
    }
    if (total < kCurrentHeaderSize ||
        !ReadAt(file, 0, header.data(), kCurrentHeaderSize, total)) {
      return Failure(result, BlendProbeStatus::InvalidStructure,
                     "Truncated modern Blender file header");
    }
    if (header[9] != '-' || !Digits(header.data() + 10, 2) ||
        ParseDigits(header.data() + 10, 2) != 1 || header[12] != 'v' ||
        !Digits(header.data() + 13, 4)) {
      return Failure(result, BlendProbeStatus::UnknownFutureFormat,
                     "Unknown modern Blender header fields");
    }
    result.format_version = 1;
    result.pointer_size = 8;
    result.little_endian = true;
    result.blender_version = ParseDigits(header.data() + 13, 4);
    header_size = kCurrentHeaderSize;
    bhead_size = 32;
  }

  uint64_t offset = header_size;
  for (uint64_t indexed = 0; indexed < kMaxIndexedBlocks; indexed++) {
    if (offset >= total) {
      return Failure(result, BlendProbeStatus::InvalidStructure,
                     "No ENDB terminator before end of file");
    }
    const uint64_t remaining = total - offset;
    if (remaining == 8 && result.format_version == 0) {
      unsigned char short_end[8] = {};
      if (ReadAt(file, offset, short_end, 8, total) &&
          std::memcmp(short_end, "ENDB", 4) == 0) {
        result.block_count++;
        result.status = result.dna_blocks ? BlendProbeStatus::StructuralIndex
                                          : BlendProbeStatus::IncompleteDNA;
        result.detail = "Indexed Blender block framing only; no scene deserialization";
        return result;
      }
    }
    if (remaining < bhead_size) {
      return Failure(result, BlendProbeStatus::InvalidStructure, "Truncated BHead");
    }
    std::array<unsigned char, 32> bytes{};
    if (!ReadAt(file, offset, bytes.data(), bhead_size, total)) {
      return Failure(result, BlendProbeStatus::IoError, "Failed to read Blender block header");
    }

    // Upstream v1 LargeBHead8 has different offsets and signed 64-bit lengths.
    const bool modern = result.format_version == 1;
    const int pointer_bytes = result.pointer_size;
    const size_t length_offset = modern ? 16 : 4;
    const size_t count_offset = modern ? 24 : static_cast<size_t>(12 + pointer_bytes);
    const int length_bytes = modern ? 8 : 4;
    const int count_bytes = modern ? 8 : 4;
    const uint64_t length = ReadInteger(bytes.data() + length_offset, length_bytes,
                                         result.little_endian);
    const uint64_t item_count = ReadInteger(bytes.data() + count_offset, count_bytes,
                                             result.little_endian);
    if ((length_bytes == 4 && length > INT32_MAX) ||
        (length_bytes == 8 && length > INT64_MAX) ||
        (count_bytes == 4 && item_count > INT32_MAX) ||
        (count_bytes == 8 && item_count > INT64_MAX)) {
      return Failure(result, BlendProbeStatus::InvalidStructure,
                     "Negative Blender block length or element count");
    }
    // Repeated offset checks prevent integer wrap and out-of-bounds seeks.
    const uint64_t payload_offset = offset + bhead_size;
    if (length > total - payload_offset) {
      return Failure(result, BlendProbeStatus::InvalidStructure,
                     "Block payload extends past end of file");
    }
    result.block_count++;

    if (std::memcmp(bytes.data(), "DNA1", 4) == 0) {
      unsigned char sig[4] = {};
      if (length < 4 || !ReadAt(file, payload_offset, sig, 4, total) ||
          std::memcmp(sig, "SDNA", 4) != 0) {
        return Failure(result, BlendProbeStatus::InvalidStructure,
                       "DNA1 block is missing SDNA signature");
      }
      result.dna_blocks++;
    }
    if (std::memcmp(bytes.data(), "ENDB", 4) == 0) {
      if (length != 0) {
        return Failure(result, BlendProbeStatus::InvalidStructure,
                       "ENDB terminator has a nonzero payload");
      }
      result.trailing_bytes = total - payload_offset;
      result.status = result.dna_blocks ? BlendProbeStatus::StructuralIndex
                                        : BlendProbeStatus::IncompleteDNA;
      result.detail = result.trailing_bytes
                          ? "Structural index complete; extra bytes after ENDB; no scene deserialization"
                          : "Indexed Blender block framing only; no scene deserialization";
      return result;
    }
    offset = payload_offset + length;
  }
  return Failure(result, BlendProbeStatus::InspectionLimit,
                 "Block index limit reached; file preserved and not treated as corrupt");
}

std::string ProbeToJson(const BlendProbeResult &r)
{
  std::ostringstream out;
  out << "{\"status\":\"" << StatusName(r.status)
      << "\",\"formatVersion\":" << r.format_version
      << ",\"blenderVersion\":" << r.blender_version
      << ",\"pointerBytes\":" << r.pointer_size
      << ",\"littleEndian\":" << (r.little_endian ? "true" : "false")
      << ",\"byteSize\":" << r.byte_size
      << ",\"blocks\":" << r.block_count
      << ",\"dnaBlocks\":" << r.dna_blocks
      << ",\"trailingBytes\":" << r.trailing_bytes
      << ",\"engineIntegrated\":false"
      << ",\"message\":\"" << EscapeJson(r.detail) << "\"}";
  return out.str();
}
}  // namespace render
