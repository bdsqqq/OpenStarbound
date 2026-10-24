#pragma once

#include "StarJson.hpp"
#include "StarImage.hpp"
#include "StarPathEmbed.hpp"

namespace Star {
// Opt-in receipts around real asset operations, never supplied by Lua.
bool compressionLabSource(Image const& image);
String compressionLabEmbed(ByteArray const& png, EmbeddedCompressionMethod method);
void compressionLabEmbedPath(String const& path);
Json compressionBehaviorAssetProof();
}
