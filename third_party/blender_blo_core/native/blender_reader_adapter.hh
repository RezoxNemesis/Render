// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <fstream>
#include <string>
#include "BLI_filereader.hh"

namespace render {
// Local app-file callback adapter for the original Blender FileReader ABI.
// This is an adapter, not an alternative implementation of Blender's BLO core.
class LocalBlendReader final : public blender::FileReader {
 public:
  explicit LocalBlendReader(const std::string &path);
  ~LocalBlendReader() = default;
  LocalBlendReader(const LocalBlendReader &) = delete;
  LocalBlendReader &operator=(const LocalBlendReader &) = delete;
  bool IsOpen() const { return file_.is_open(); }
  blender::FileReader *Raw() { return this; }

 private:
  static int64_t Read(blender::FileReader *self, void *data, size_t length);
  static off64_t Seek(blender::FileReader *self, off64_t pos, int whence);
  static void Close(blender::FileReader *self);
  std::ifstream file_;
  uint64_t byte_size_ = 0;
};
std::string ProbeRealBlenderCoreHeader(const std::string &path);
}  // namespace render
