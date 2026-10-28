-- Normal Root callback only: explicit seeds do not bypass its eager RNG default.
local pools = {"behaviorWeightedRepeat", "behaviorWeightedUnique", "behaviorWeightedFiltered"}
local function equal(a, b)
  if type(a) ~= type(b) then return false end
  if type(a) ~= "table" then return a == b end
  for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
  for k in pairs(b) do if a[k] == nil then return false end end
  return true
end
function proof(stage)
  assert(stage == 0 or stage == 1 or stage == 2)
  local results = {}
  local function get(index, count)
    local descriptors = root.createTreasure(pools[index], 1, 17)
    assert(#descriptors == count)
    for _, d in ipairs(descriptors) do
      assert(d.name == "behaviorweightedtoken" and d.count == 1)
      assert(type(d.parameters) == "table" and d.parameters.tag == "kept")
    end
    results[#results + 1] = {pool = pools[index], descriptors = descriptors}
    return descriptors
  end
  local repeated = get(1, 2)
  if stage ~= 1 then assert(equal(repeated, get(1, 2))) end
  local unique = get(2, 1)
  local filtered = get(3, 0)
  local selected = stage == 1 and unique or repeated
  local selectedCount, uniqueCount = #selected, #unique
  local c = {selectedCount * 70, uniqueCount * 80, (stage + 1) * 70, 255}
  return {phase = stage, results = results, selected = selected,
    selectedCount = selectedCount, uniqueCount = uniqueCount,
    color = c, label = string.format("Weighted %d/3 count=%d tag=%s", stage + 1, selectedCount, selected[1].parameters.tag),
    imagePath = "/behaviorlab/weighted-white.png?multiply=" ..
      string.format("%02x%02x%02x%02x", c[1], c[2], c[3], c[4])}
end
