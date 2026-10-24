#pragma once

#include "StarJson.hpp"

namespace Star {

// Lab-only diagnostic snapshot, published after Assets construction completes.
// Null until available; never contributes files to the asset digest input.
Json sha256BehaviorAssetProof();

}
