local key = "behavior-ttl-a"
local missing = "behavior-ttl-unknown"
function proof(stage)
  local results = {}
  local function get()
    local metadata = root.tenantConfig(key)
    assert(metadata.name == key and metadata.priority == 17 and metadata.labIndex == 17)
    assert(metadata.labLiteral == "normal-tenant-constructor")
    results[#results + 1] = {name = key, ok = true, metadata = metadata}
    return metadata
  end
  local selected
  if stage == 0 then get(); selected = get()
  elseif stage == 1 then selected = get()
  elseif stage == 2 then
    local ok, err = pcall(root.tenantConfig, missing)
    assert(not ok and type(err) == "string" and err:find(missing, 1, true))
    results[#results + 1] = {name = missing, ok = false, error = err}
    selected = get()
  else error("invalid TTL phase") end
  local c = {selected.labIndex * 8, selected.priority * 4, (stage + 1) * 80, 255}
  return {phase = stage, results = results, selected = selected, continuation = true,
    color = c, label = string.format("TTL %d/3 metadata=17 continue=ok", stage + 1),
    imagePath = "/behaviorlab/ttl-white.png?multiply=" ..
      string.format("%02x%02x%02x%02x", c[1], c[2], c[3], c[4])}
end
