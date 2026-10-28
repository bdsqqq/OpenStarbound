-- Lua contexts are recreated per phase; only the real player's controller persists.
local stat = "behaviorLabIdMap"
local a, b = "behaviorLabIdMapA", "behaviorLabIdMapB"
local function effect(amount)
  return {{stat = stat, amount = amount}}
end

function proof(stage)
  assert(stage == 0 or stage == 1 or stage == 2)
  local observations = {}
  local function read(expected)
    local actual = status.stat(stat)
    assert(type(actual) == "number" and actual == expected,
      string.format("IdMap stat: expected %d, got %s", expected, tostring(actual)))
    observations[#observations + 1] = actual
    return actual
  end
  local value
  if stage == 0 then
    status.addPersistentEffects(a, effect(8))
    read(8)
    status.addPersistentEffects(a, effect(4))
    read(12)
    status.setPersistentEffects(a, effect(16))
    read(16)
    status.addPersistentEffects(b, effect(2))
    value = read(18)
  elseif stage == 1 then
    status.clearPersistentEffects(a)
    value = read(2)
  else
    status.addPersistentEffects(a, effect(32))
    value = read(34)
  end
  -- Convert only after exact numeric assertions, never to repair a readback.
  local c = {math.floor(value * 4), 40, (stage + 1) * 60, 255}
  return {phase = stage, observations = observations, value = value,
    color = c, label = string.format("IdMap %d/3 stat=%d", stage + 1, value),
    imagePath = "/behaviorlab/id-map-white.png?multiply=" ..
      string.format("%02x%02x%02x%02x", c[1], c[2], c[3], c[4])}
end

function restore()
  -- Never clear unrelated categories, even when a preceding phase failed.
  status.clearPersistentEffects(a)
  status.clearPersistentEffects(b)
  local value = status.stat(stat)
  assert(type(value) == "number" and value == 0, "IdMap owned cleanup left a stat modifier")
  return 0
end
