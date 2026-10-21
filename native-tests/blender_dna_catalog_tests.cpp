// SPDX-License-Identifier: GPL-2.0-or-later
// Synthetic binary fixtures exercise bounded read-only SDNA catalog, not scene loading.
#include "dna_catalog.h"
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <zlib.h>
#define CHECK(expr) do { if(!(expr)) throw std::runtime_error("SDNA catalog: " #expr); } while(false)
namespace {
using Bytes=std::vector<uint8_t>;
void Str(Bytes &b,const std::string &s){b.insert(b.end(),s.begin(),s.end());}
void Num(Bytes &b,uint64_t v,int n){for(int i=0;i<n;++i)b.push_back(static_cast<uint8_t>(v>>(i*8)));}
void Align(Bytes &b){while(b.size()%4)b.push_back(0);}
Bytes Dna(){
  Bytes b;
  Str(b,"SDNA");Str(b,"NAME");Num(b,3,4);
  Str(b,"*next");b.push_back(0);
  Str(b,"value");b.push_back(0);
  Str(b,"label[4]");b.push_back(0);Align(b);
  Str(b,"TYPE");Num(b,3,4);
  Str(b,"int");b.push_back(0);
  Str(b,"char");b.push_back(0);
  Str(b,"Sample");b.push_back(0);Align(b);
  Str(b,"TLEN");Num(b,4,2);Num(b,1,2);Num(b,16,2);Align(b);
  Str(b,"STRC");Num(b,1,4);
  Num(b,2,2);Num(b,3,2); // Sample: three members.
  Num(b,0,2);Num(b,1,2); // int value
  Num(b,1,2);Num(b,2,2); // char label[4]
  Num(b,2,2);Num(b,0,2); // Sample *next
  return b;
}
void Block(Bytes &file,int format,int pointer,const std::string &code,const Bytes &data,uint64_t old_token=0){
  CHECK(code.size()==4);Str(file,code);
  if(format==1){Num(file,0,4);Num(file,old_token,8);Num(file,data.size(),8);Num(file,1,8);}
  else{Num(file,data.size(),4);Num(file,old_token,pointer);Num(file,0,4);Num(file,1,4);}
  file.insert(file.end(),data.begin(),data.end());
}
Bytes Fixture(int format,int pointer,const Bytes &dna= Dna(),bool include_dna=true){
  Bytes b;
  if(format==1)Str(b,"BLENDER17-01v0500");
  else{Str(b,"BLENDER");b.push_back(pointer==8?'-':'_');Str(b,"v405");}
  Block(b,format,pointer,std::string("OB\0\0",4),{},0x1000);
  Block(b,format,pointer,std::string("SC\0\0",4),{},0x2000);
  Block(b,format,pointer,std::string("ME\0\0",4),{},0x3000);
  if(include_dna)Block(b,format,pointer,"DNA1",dna);
  Block(b,format,pointer,"ENDB",{});
  return b;
}
Bytes Gzip(const Bytes &input){
  z_stream s{};
  CHECK(deflateInit2(&s, Z_DEFAULT_COMPRESSION, Z_DEFLATED, MAX_WBITS + 16,
                     8, Z_DEFAULT_STRATEGY) == Z_OK);
  Bytes compressed(compressBound(static_cast<uLong>(input.size())) + 128);
  s.next_in = const_cast<Bytef *>(input.data());
  s.avail_in = static_cast<uInt>(input.size());
  s.next_out = compressed.data();
  s.avail_out = static_cast<uInt>(compressed.size());
  const int code = deflate(&s, Z_FINISH);
  CHECK(code == Z_STREAM_END);
  compressed.resize(s.total_out);
  CHECK(deflateEnd(&s) == Z_OK);
  return compressed;
}
std::string Write(const Bytes &bytes){
  static unsigned serial=0;
  const auto path=(std::filesystem::temp_directory_path() /
      ("render-dna-catalog-" + std::to_string(++serial) + ".blend")).string();
  std::ofstream f(path,std::ios::binary|std::ios::trunc);
  f.write(reinterpret_cast<const char *>(bytes.data()),static_cast<std::streamsize>(bytes.size()));
  CHECK(f.good());return path;
}
render::DnaCatalogResult Inspect(const Bytes &bytes) {
  const auto path=Write(bytes);
  const auto result=render::InspectDnaCatalog(path);
  std::filesystem::remove(path);
  return result;
}
void Valid(int fmt,int ptr){
  const auto a=Inspect(Fixture(fmt,ptr));
  CHECK(a.status==render::DnaCatalogStatus::Indexed);
  CHECK(a.blender_version==(fmt?500:405));
  CHECK(a.object_blocks==1);
  CHECK(a.mesh_blocks==1);
  CHECK(a.scene_blocks==1);
  CHECK(a.structures==1);
  CHECK(a.member_names==3);
  CHECK(a.types==3);
  CHECK(a.id_blocks==3);
  CHECK(a.unique_id_tokens==3);
  CHECK(a.duplicate_id_tokens==0);
  CHECK(a.structure_fields==3);
  CHECK(a.sample_structures.size()==1);
  CHECK(a.sample_structures[0]=="Sample");
  const std::string json=render::DnaCatalogJson(a);
  CHECK(json.find("\"sceneLoaded\":false")!=std::string::npos);
  CHECK(json.find("\"objectBlocks\":1")!=std::string::npos);
}
}
int main(){
  Valid(0,4);Valid(0,8);Valid(1,8);
  {
    Bytes repeated;
    Str(repeated,"BLENDER17-01v0500");
    Block(repeated,1,8,std::string("OB\0\0",4),{},0x9000);
    Block(repeated,1,8,std::string("ME\0\0",4),{},0x9000);
    Block(repeated,1,8,"DNA1",Dna());
    Block(repeated,1,8,"ENDB",{});
    auto info=Inspect(repeated);
    CHECK(info.status==render::DnaCatalogStatus::Indexed);
    CHECK(info.id_blocks==2);
    CHECK(info.unique_id_tokens==1);
    CHECK(info.duplicate_id_tokens==1);
  }
  CHECK(Inspect(Gzip(Fixture(0,8))).status == render::DnaCatalogStatus::Indexed);
  CHECK(Inspect(Gzip(Fixture(1,8))).status == render::DnaCatalogStatus::Indexed);
  CHECK(Inspect(Gzip(Fixture(0,8,Dna(),false))).status == render::DnaCatalogStatus::NoSchema);
  CHECK(Inspect(Fixture(0,8,Dna(),false)).status==render::DnaCatalogStatus::NoSchema);
  {
    Bytes bad=Dna();bad[0]='X';
    CHECK(Inspect(Fixture(1,8,bad)).status==render::DnaCatalogStatus::InvalidSchema);
  }
  {
    Bytes bad=Dna();bad.resize(bad.size()-3);
    CHECK(Inspect(Fixture(0,4,bad)).status==render::DnaCatalogStatus::InvalidSchema);
  }
  {
    Bytes bad=Dna();
    // SDNA member index in STRC is last two bytes of fixture.
    bad[bad.size()-2]=255;
    CHECK(Inspect(Fixture(1,8,bad)).status==render::DnaCatalogStatus::InvalidSchema);
  }
  {
    Bytes missing=Fixture(1,8);
    missing.resize(missing.size()-32); // remove complete ENDB header.
    CHECK(Inspect(missing).status==render::DnaCatalogStatus::InvalidBlock);
  }
  {
    Bytes duplicated=Fixture(1,8);
    duplicated.resize(duplicated.size()-32); // remove ENDB
    Block(duplicated,1,8,"DNA1",Dna());
    Block(duplicated,1,8,"ENDB",{});
    CHECK(Inspect(duplicated).status==render::DnaCatalogStatus::InvalidSchema);
  }
  {
    Bytes big=Fixture(0,8);
    big[8]='V';
    CHECK(Inspect(big).status==render::DnaCatalogStatus::UnsupportedEndian);
  }
  CHECK(Inspect({0x1f,0x8b,0x08,0}).status==render::DnaCatalogStatus::UnrecognizedHeader);
  CHECK(Inspect({0x28,0xb5,0x2f,0xfd}).status==render::DnaCatalogStatus::CompressedNeedsUpstreamReader);
  CHECK(Inspect({}).status==render::DnaCatalogStatus::UnrecognizedHeader);
  std::puts("PASS: SDNA catalog diagnostics (synthetic fixtures)");
  return 0;
}
