// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Narrow header shim; Blender's Zstd FileReader uses only SEEK_* macros here.
// This is NOT full Blender BLI_fileops.
#include <cstdio>
