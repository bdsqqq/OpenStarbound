#include "aliases.h"
_Static_assert(PE_OK == 0 && PE_INVALID == 2 && PE_PANIC_RESERVED == 3, "status");
static uint32_t (*select_signature)(uint32_t, uint32_t*) = pe_select;
static uint32_t (*escape_signature)(const uint8_t*, size_t, uint8_t*, size_t, size_t*) = pe_escape;
int main(void) { uint32_t a = 9; size_t n = 9; return select_signature(0, &a) || a || escape_signature(NULL, 0, NULL, 0, &n) || n; }
