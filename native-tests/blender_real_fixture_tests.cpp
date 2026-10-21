// SPDX-License-Identifier: GPL-2.0-or-later
// Tests real .blend files created with the Blender desktop engine on Linux CI.
// This executable itself is Render's portable native reader, not Blender.
#include "dna_catalog.h"
#include "blender_reader_adapter.hh"
#include <cstdio>
#include <filesystem>
#include <stdexcept>
#include <string>

#define VERIFY(cond,msg) do { if(!(cond)) throw std::runtime_error(msg); } while(false)

render::DnaCatalogResult CheckReal(const char *path, const bool animated)
{
  VERIFY(std::filesystem::exists(path), std::string("Missing Blender fixture: ") + path);
  const render::DnaCatalogResult r = render::InspectDnaCatalog(path);
  const std::string report = render::DnaCatalogJson(r);
  std::printf("Native Render inspection of REAL Blender file %s:\n%s\n",
              path,report.c_str());
  VERIFY(r.status == render::DnaCatalogStatus::Indexed,
         std::string("Failed actual Blender SDNA import: ") + report);
  VERIFY(r.blender_version >= 280, "Unexpected Blender file format version");
  VERIFY(r.mesh_blocks >= 2, "Real Blender scene has fewer mesh datablocks than expected");
  VERIFY(r.object_blocks >= 2, "Real Blender scene has fewer object datablocks than expected");
  VERIFY(r.scene_blocks >= (animated ? 2u : 1u),
         "Real Blender scene datablock count is below expectation");
  VERIFY(r.member_names > 100, "Real SDNA did not enumerate member names");
  VERIFY(r.structures > 100, "Real SDNA did not enumerate structure definitions");
  VERIFY(r.types > 100, "Real SDNA did not enumerate type table");
  VERIFY(r.structure_fields > 100, "Real SDNA did not enumerate struct fields");
  VERIFY(r.id_blocks >= r.object_blocks + r.mesh_blocks + r.scene_blocks,
         "Top-level ID code inventory omitted real object or mesh types");
  VERIFY(r.unique_id_tokens >= 2, "Real Blender saved ID pointers were not indexed");
  VERIFY(!r.sample_object_names.empty(), "No saved Blender Object ID names were read");
  VERIFY(!r.sample_scene_names.empty(), "No saved Blender Scene ID names were read");
  VERIFY(!r.sample_mesh_names.empty(), "No saved Blender Mesh ID names were read");
  VERIFY(report.find("\"sceneLoaded\":false") != std::string::npos,
         "Diagnostic must never claim to load a Blender scene");
  return r;
}

int main(int argc, char **argv)
{
  VERIFY(argc == 4, "Usage: blender_real_fixture_tests PLAIN ADVANCED GZIP");
  const auto basic = CheckReal(argv[1], false);
  const auto advanced = CheckReal(argv[2], true);
  const auto gzip = CheckReal(argv[3], false);
  VERIFY(gzip.object_blocks == basic.object_blocks,
         "Gzip fixture changed native object block indexing");
  VERIFY(gzip.mesh_blocks == basic.mesh_blocks,
         "Gzip fixture changed native mesh block indexing");
  VERIFY(gzip.sample_object_names == basic.sample_object_names,
         "Gzip changed on-disk saved Object ID names");
  VERIFY(gzip.structures == basic.structures,
         "Gzip fixture changed SDNA schema parsing");
  VERIFY(advanced.scene_blocks >= basic.scene_blocks,
         "Additional Blender scene was lost");
  std::puts("PASS genuine Blender-generated scene metadata compatibility (NOT rendering)");
  return 0;
}
