-- Frozen independent bytes, URL-base64 encoded offline with Python's base64.
-- NEVER serialize these inputs using the candidate encoder or preload the paths.
local pairPath = '/opensb_data;json;BgIEgQEEggA'
local stringPath = '/opensb_data;json;BYEAeHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg'
local function readMeasured(path)
  local before = assets.vlqLabCounts()
  local value = assets.json(path)
  local after = assets.vlqLabCounts()
  local calls = {}
  for i = 1, 6 do calls[i] = after[i] - before[i] end
  return value, calls
end
local pair, pairCalls = readMeasured(pairPath)
local text, stringCalls = readMeasured(stringPath)
assert(pair[1] == -65 and pair[2] == 128 and #pair == 2)
assert(text == string.rep('x', 128))
local seed = assets.image('/objects/behaviorlab/constantlight/constantlight.png')
-- The unchanged lighting fixture is 8x8. Crop a one-pixel seed rather than
-- replace the old lamp asset or accidentally produce a 128x128 result.
assert(seed:size()[1] == 8 and seed:size()[2] == 8)
seed = seed:subImage({0, 0}, {1, 1})
assert(seed:size()[1] == 1 and seed:size()[2] == 1)
local image = seed:process('?scale=16')
assert(image:size()[1] == 16 and image:size()[2] == 16)
local color = {(pair[2] - 127) * 255, pair[1] + 65, #text - 128, 255}
for y = 0, 15 do
  for x = 0, 15 do image:set(x, y, color) end
end
assets.add('/behaviorlab/vlq-result.png', image)
-- LAST: swallowed Lua failures must leave no completed proof. Native code
-- supplies backend from its compiled flag, outside the asset namespace.
assets.recordVlqLabProof({
  pairInputHex = '0602048101048200', pairValue = pair,
  stringInputHex = '058100' .. string.rep('78', 128), stringValue = text,
  readCalls = {pair = pairCalls, string = stringCalls}, visualColor = color
})
