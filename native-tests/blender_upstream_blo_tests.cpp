// SPDX-License-Identifier: GPL-2.0-or-later
// Genuine Blender BLO decoder & BHead unit tests. Synthetic binary fixtures,
// not equivalent to a complete .blend scene load.
#include "blender_reader_adapter.hh"
#include "BLO_core_bhead.hh"
#include "BLO_core_blend_header.hh"
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
#define CHECK(cond) do { if (!(cond)) throw std::runtime_error("Blender BLO test failure: " #cond); } while(false)
namespace {
using Bytes=std::vector<unsigned char>;
void Text(Bytes &b, const char *str) { while (*str) b.push_back(static_cast<unsigned char>(*str++)); }
void Num(Bytes &b, uint64_t n, int len) { for(int i=0;i<len;++i) b.push_back(static_cast<unsigned char>(n>>(8*i))); }
Bytes Fixture(int format, int ptr) {
  Bytes b;
  if(format==1) Text(b,"BLENDER17-01v0500");
  else { Text(b,"BLENDER"); b.push_back(ptr==8?'-':'_'); Text(b,"v405"); }
  Text(b,"GLOB");
  if(format==1) { Num(b,0,4);Num(b,0,8);Num(b,5,8);Num(b,1,8); }
  else { Num(b,5,4);Num(b,0,ptr);Num(b,0,4);Num(b,1,4); }
  Text(b,"hello");
  return b;
}
std::string Save(const Bytes &b) {
  static int counter=0;
  const auto path=(std::filesystem::temp_directory_path() /
                   ("render-blo-" + std::to_string(++counter) + ".blend")).string();
  std::ofstream out(path,std::ios::binary | std::ios::trunc);
  out.write(reinterpret_cast<const char*>(b.data()),static_cast<std::streamsize>(b.size()));
  CHECK(out.good());return path;
}
void CheckVersion(int format,int ptr,int version) {
  auto path=Save(Fixture(format,ptr));
  render::LocalBlendReader file(path);CHECK(file.IsOpen());
  auto decoded=blender::BLO_readfile_blender_header_decode(file.Raw());
  auto *header=std::get_if<blender::BlenderHeader>(&decoded);
  CHECK(header!=nullptr); CHECK(header->file_version==version);
  CHECK(header->pointer_size==ptr); CHECK(header->file_format_version==format);
  auto bhead=blender::BLO_readfile_read_bhead(file.Raw(),header->bhead_type());
  CHECK(bhead.has_value()); CHECK(bhead->code==blender::BLO_CODE_GLOB);
  CHECK(bhead->len==5); CHECK(bhead->nr==1);
  CHECK(render::ProbeRealBlenderCoreHeader(path).find("firstBlock=GLOB")!=std::string::npos);
  std::filesystem::remove(path);
}
}
int main() {
  static_assert(sizeof(blender::BHead4)==20);
  static_assert(sizeof(blender::SmallBHead8)==24);
  static_assert(sizeof(blender::LargeBHead8)==32);
  CheckVersion(0,4,405);CheckVersion(0,8,405);CheckVersion(1,8,500);
  {
    auto bad=Fixture(0,8);bad[9]='X';
    auto path=Save(bad);render::LocalBlendReader f(path);
    CHECK(std::holds_alternative<blender::BlenderHeaderUnknown>(
      blender::BLO_readfile_blender_header_decode(f.Raw())));
    std::filesystem::remove(path);
  }
  {
    auto bad=Fixture(1,8);bad.resize(10);
    auto path=Save(bad);render::LocalBlendReader f(path);
    CHECK(std::holds_alternative<blender::BlenderHeaderInvalid>(
      blender::BLO_readfile_blender_header_decode(f.Raw())));
    std::filesystem::remove(path);
  }
  return 0;
}
