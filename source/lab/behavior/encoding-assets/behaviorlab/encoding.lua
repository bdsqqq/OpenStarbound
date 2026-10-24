-- Each receipt brackets one production operation on this Lua/Assets thread.
-- Add the proof last: Assets logs/swallowing a script failure must not look like
-- a completed fixture. The client requires both generated assets before capture.
local function measured(operation)
  local before = assets.encodingLabCounts()
  local result = operation()
  local after = assets.encodingLabCounts()
  local receipt = {}
  for i = 1, 5 do
    receipt[i] = after[i] - before[i]
  end
  return result, receipt
end

local seed = assets.image('/behaviorlab/encoding-seed.png')
local processed, directives = measured(function()
  return seed:process('?replace;f00=00ff00ff;0f0f=0000ffff;0000ff=ffffffff;ffffffff=ff0000ff')
end)
local embeddedPath, embed = measured(function()
  return processed:embed('None')
end)
-- This fresh embedded path is not preloaded or inspected before this call.
local decoded, decode = measured(function()
  return assets.image(embeddedPath)
end)
local dataUri, standard = measured(function()
  return decoded:toDataURI()
end)
assets.add('/objects/behaviorlab/constantlight/constantlight.png', decoded)
assets.add('/behaviorlab/encoding-roundtrip.png', decoded)
assets.add('/behaviorlab/encoding-proof.json', {
  version = 1,
  patternSize = {16, 16},
  embeddedPath = embeddedPath,
  dataUri = dataUri,
  receipts = {
    directives = directives,
    embed = embed,
    decode = decode,
    standard = standard
  }
})
