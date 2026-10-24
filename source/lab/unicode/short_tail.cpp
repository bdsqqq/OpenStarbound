#include "StarRustUnicode.h"
#ifndef STAR_USE_RUST_UNICODE
#include "StarUnicode.hpp"
#endif
#include <cstdio>
#include <sys/mman.h>
#include <sys/wait.h>
#include <unistd.h>

// The legacy two-byte length recovery returns 2 without inspecting byte two.
// An inaccessible tail makes a forbidden extra read observable without ever
// loading an indeterminate value in this test's own comparison code.
int main() {
  size_t page = size_t(sysconf(_SC_PAGESIZE));
  auto memory = static_cast<unsigned char*>(mmap(nullptr, 2 * page,
      PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0));
  if (memory == MAP_FAILED || mprotect(memory + page, page, PROT_NONE)) return 2;
  memory[page - 1] = 0xff;
  pid_t child = fork();
  if (child < 0) return 2;
  if (!child) {
    size_t result = 999;
#ifdef STAR_USE_RUST_UNICODE
    auto status = star_unicode_length(memory + page - 1, 2, &result);
    _exit(status == 0 && result == 2 ? 0 : 1);
#else
    result = Star::utf8Length(reinterpret_cast<char*>(memory + page - 1), 2);
    _exit(result == 2 ? 0 : 1);
#endif
  }
  int status;
  if (waitpid(child, &status, 0) != child) return 2;
  munmap(memory, 2 * page);
  if (!WIFEXITED(status) || WEXITSTATUS(status)) {
    std::fputs("COMPARISON legacy length short-tail read\n", stderr);
    return 1;
  }
  std::puts("legacy length short-tail guard passed");
}
