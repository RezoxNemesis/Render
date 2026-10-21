// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic fixtures exercise upstream Blender file-header and BHead framing.
// These are NOT genuine .blend scenes and do not prove BKE/BLO scene loading.
#include "blend_probe.h"
#include <array>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

using render::BlendProbeStatus;
using render::ProbeBlendFile;

#define REQUIRE(condition) \
  do { if (!(condition)) throw std::runtime_error(std::string("Failed: ") + #condition); } while (false)

namespace {
using Bytes = std::vector<uint8_t>;

void AddNumber(Bytes &out, uint64_t value, int n, bool little)
{
  for (int i = 0; i < n; i++) {
    int shift = (little ? i : n - i - 1) * 8;
    out.push_back(static_cast<uint8_t>(value >> shift));
  }
}

void AddText(Bytes &out, const std::string &str)
{
  out.insert(out.end(), str.begin(), str.end());
}

Bytes Header(int format, int ptr, bool little)
{
  Bytes out;
  if (format == 1) {
    AddText(out, "BLENDER17-01v0500");
  }
  else {
    AddText(out, "BLENDER");
    out.push_back(ptr == 4 ? '_' : '-');
    out.push_back(little ? 'v' : 'V');
    AddText(out, "405");
  }
  return out;
}

void Block(Bytes &out, int format, int ptr, bool little, std::string code,
           const Bytes &payload, uint64_t length_override = 0, bool override_size = false)
{
  REQUIRE(code.size() == 4);
  AddText(out, code);
  uint64_t length = override_size ? length_override : payload.size();
  if (format == 1) {
    AddNumber(out, 0, 4, little); // SDNAnr.
    AddNumber(out, 0, 8, little); // Old pointer.
    AddNumber(out, length, 8, little);
    AddNumber(out, 1, 8, little);
  }
  else {
    AddNumber(out, length, 4, little);
    AddNumber(out, 0, ptr, little); // Old pointer.
    AddNumber(out, 0, 4, little); // SDNAnr.
    AddNumber(out, 1, 4, little);
  }
  out.insert(out.end(), payload.begin(), payload.end());
}

std::filesystem::path Write(const Bytes &bytes)
{
  static unsigned counter = 0;
  const auto path = std::filesystem::temp_directory_path() /
                    ("render-blend-probe-" + std::to_string(++counter) + ".bin");
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  out.write(reinterpret_cast<const char *>(bytes.data()),
            static_cast<std::streamsize>(bytes.size()));
  REQUIRE(out.good());
  return path;
}

render::BlendProbeResult Inspect(const Bytes &bytes)
{
  auto path = Write(bytes);
  auto report = ProbeBlendFile(path.string());
  std::filesystem::remove(path);
  return report;
}

void CheckComplete(int format, int ptr, bool little)
{
  Bytes source = Header(format, ptr, little);
  Block(source, format, ptr, little, "GLOB", {0, 1, 2, 3});
  Block(source, format, ptr, little, "DNA1", {'S', 'D', 'N', 'A'});
  Block(source, format, ptr, little, "ENDB", {});
  auto r = Inspect(source);
  REQUIRE(r.status == BlendProbeStatus::StructuralIndex);
  REQUIRE(r.format_version == format);
  REQUIRE(r.pointer_size == ptr);
  REQUIRE(r.little_endian == little);
  REQUIRE(r.dna_blocks == 1);
  REQUIRE(r.block_count == 3);
  REQUIRE(render::ProbeToJson(r).find("\"engineIntegrated\":false") != std::string::npos);
}
}  // namespace

int main()
{
  CheckComplete(0, 4, true);
  CheckComplete(0, 8, true);
  CheckComplete(0, 4, false);
  CheckComplete(0, 8, false);
  CheckComplete(1, 8, true);

  {
    Bytes file = Header(0, 8, true);
    AddText(file, "ENDB");
    AddNumber(file, 0, 4, true);
    REQUIRE(Inspect(file).status == BlendProbeStatus::IncompleteDNA);
  }
  {
    Bytes file = Header(1, 8, true);
    Block(file, 1, 8, true, "ENDB", {});
    REQUIRE(Inspect(file).status == BlendProbeStatus::IncompleteDNA);
  }
  {
    Bytes file = Header(1, 8, true);
    Block(file, 1, 8, true, "DNA1", {'S', 'D', 'N', 'A'});
    REQUIRE(Inspect(file).status == BlendProbeStatus::InvalidStructure);
  }
  {
    Bytes file = Header(0, 8, true);
    Block(file, 0, 8, true, "DNA1", {'F', 'A', 'K', 'E'});
    Block(file, 0, 8, true, "ENDB", {});
    REQUIRE(Inspect(file).status == BlendProbeStatus::InvalidStructure);
  }
  {
    Bytes file = Header(1, 8, true);
    Block(file, 1, 8, true, "GLOB", {}, UINT64_MAX, true);
    REQUIRE(Inspect(file).status == BlendProbeStatus::InvalidStructure);
  }
  {
    Bytes file = Header(0, 4, true);
    Block(file, 0, 4, true, "DATA", {}, 2147483647u, true);
    REQUIRE(Inspect(file).status == BlendProbeStatus::InvalidStructure);
  }
  REQUIRE(Inspect({0x1f, 0x8b, 0x08, 0x00}).status == BlendProbeStatus::CompressedGzip);
  REQUIRE(Inspect({0x28, 0xb5, 0x2f, 0xfd}).status == BlendProbeStatus::CompressedZstd);
  REQUIRE(Inspect({'n', 'o', 'p', 'e'}).status == BlendProbeStatus::InvalidStructure);
  REQUIRE(Inspect({}).status == BlendProbeStatus::InvalidStructure);
  {
    Bytes unknown;
    AddText(unknown, "BLENDER19-01v0600");
    REQUIRE(Inspect(unknown).status == BlendProbeStatus::UnknownFutureFormat);
  }
  {
    Bytes file = Header(0, 8, true);
    Block(file, 0, 8, true, "DNA1", {'S', 'D', 'N', 'A'});
    Block(file, 0, 8, true, "ENDB", {});
    file.push_back('X');
    auto r = Inspect(file);
    REQUIRE(r.status == BlendProbeStatus::StructuralIndex);
    REQUIRE(r.trailing_bytes == 1);
  }
  std::puts("PASS: 14 synthetic Blender framing/corruption cases");
  return 0;
}
