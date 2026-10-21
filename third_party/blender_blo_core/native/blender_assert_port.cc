// SPDX-License-Identifier: GPL-2.0-or-later
// Android/host port of Blender BLI_assert logging ABI; assertions remain enabled.
// Native backtraces need further platform integration.
#include <cstdio>
#include <cstdlib>
void _BLI_assert_print_pos(const char *file, int line, const char *function, const char *id) {
  std::fprintf(stderr, "BLI assertion at %s:%d in %s: %s\n", file, line, function, id);
}
void _BLI_assert_print_extra(const char *s) { std::fprintf(stderr, "BLI: %s\n", s); }
void _BLI_assert_print_backtrace() {}
void _BLI_assert_abort() { std::abort(); }
void _BLI_assert_unreachable_print(const char *file, int line, const char *function) {
  std::fprintf(stderr, "BLI unreachable at %s:%d in %s\n", file, line, function);
}
