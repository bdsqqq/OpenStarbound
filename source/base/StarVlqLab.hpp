#pragma once

#include "StarJson.hpp"

namespace Star {
// Completed postLoad proof lives outside the asset set: diagnostics must not
// change the normal Assets digest or require application access during Root load.
Json vlqBehaviorAssetProof();
}
