#pragma once
#include "StarByteArray.hpp"
#include <zstd.h>
#include <string>
// Native-only observation shim. Implementations forward real library/ByteArray
// operations; controlled deviations are selected explicitly, never normal mode.
void labTraceReset(int mode);
void labTraceCaught();
std::string labTraceSerialize();
size_t labTraceCompress(ZSTD_CCtx*,ZSTD_outBuffer*,ZSTD_inBuffer*,ZSTD_EndDirective);
size_t labTraceDecompress(ZSTD_DCtx*,ZSTD_outBuffer*,ZSTD_inBuffer*);
void labTraceResize(Star::ByteArray&,size_t);
