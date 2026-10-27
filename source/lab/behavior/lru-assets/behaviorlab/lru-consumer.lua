-- only the lab scene loads this script. these are real .dungeon assets, not a
-- replacement cache or constructor. no cache clear, resizing or synthetic hit.
local function name(i) return string.format("behavior-lru-%02d", i) end
local missing = "behavior-lru-unknown"
function proof(stage)
  local results = {}
  local function get(i)
    local n = name(i)
    local metadata = root.dungeonMetadata(n)
    assert(metadata.name == n and metadata.labIndex == i and metadata.maxParts == i)
    results[#results + 1] = {name = n, ok = true, metadata = metadata}
    return metadata
  end
  local selected
  if stage == 0 then
    -- 21 distinct accesses converge from the OBSERVED initial cache, not an
    -- assumed empty cache; the native receipts retain that initial state.
    for i = 1, 21 do get(i) end
    selected = get(21) -- full-cache MRU hit still pre-evicts key 2
  elseif stage == 1 then
    get(1)
    local ok, err = pcall(root.dungeonMetadata, missing)
    assert(not ok and type(err) == "string" and err:find(missing, 1, true))
    results[#results + 1] = {name = missing, ok = false, error = err}
    selected = get(1) -- SAME Lua invocation must continue after producer error
  elseif stage == 2 then
    get(2)
    selected = get(2) -- another full-cache hit pre-evicts key 4
  else error("invalid LRU phase") end
  local c = {selected.labIndex * 8, selected.maxParts * 4, (stage + 1) * 80, 255}
  local label = string.format("LRU %d/3 metadata=%02d continue=ok", stage + 1, selected.labIndex)
  return {phase = stage, results = results, continuation = true, selected = selected,
    color = c, label = label, scale = 4,
    imagePath = "/behaviorlab/lru-white.png?multiply=" ..
      string.format("%02x%02x%02x%02x", c[1], c[2], c[3], c[4])}
end
