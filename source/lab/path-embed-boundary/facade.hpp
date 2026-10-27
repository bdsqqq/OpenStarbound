#pragma once
#include "StarPathEmbed.hpp"
namespace PathEmbedBoundary {
Star::String compress(Star::ByteArray const& data, Star::EmbeddedCompressionMethod const& method);
Star::String escape(Star::String const& data);
}
