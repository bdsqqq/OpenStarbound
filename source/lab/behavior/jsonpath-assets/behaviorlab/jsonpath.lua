assert(assets.patch('/behaviorlab/jsonpath-input.json', '/behaviorlab/jsonpath-ops.json'))
local rgb = assets.json('/behaviorlab/jsonpath-input.json:visual.rgb')
local scale = assets.json('/behaviorlab/jsonpath-input.json:visual.scale')
local label = assets.json('/behaviorlab/jsonpath-input.json:visual.label')
assert(#rgb == 3 and rgb[1] == 64 and rgb[2] == 128 and rgb[3] == 192)
assert(scale == 4 and label == 'JSONPATH')

local function delta(before, after)
  return {after[1] - before[1], after[2] - before[2]}
end
local input = sb.parseJson('{"é":[{"雪":9}]}')
local before = assets.jsonPathLabCounts()
local value = sb.jsonQuery(input, 'é[0].雪', -1)
local after = assets.jsonPathLabCounts()
local queryCalls = delta(before, after)
assert(value == 9)
before = assets.jsonPathLabCounts()
local missing = sb.jsonQuery(input, 'missing', 77)
after = assets.jsonPathLabCounts()
local missingCalls = delta(before, after)
assert(missing == 77)
before = assets.jsonPathLabCounts()
local accepted, err = pcall(sb.jsonQuery, input, 'é[0x].雪', -1)
after = assets.jsonPathLabCounts()
local malformedCalls = delta(before, after)
local nativeError = 'Array has no trailing \']\' or has invalid character in query path "é[0x].雪"'
local nativeErrorMatched = not accepted and type(err) == 'string' and string.find(err, nativeError, 1, true) ~= nil
assert(not accepted and nativeErrorMatched)

local seed = assets.image('/objects/behaviorlab/constantlight/constantlight.png')
assert(seed:size()[1] == 8 and seed:size()[2] == 8)
local image = seed:subImage({0, 0}, {1, 1}):process('?scale=16')
assert(image:size()[1] == 16 and image:size()[2] == 16)
local color = {rgb[1], rgb[2], rgb[3], 255}
for y = 0, 15 do
  for x = 0, 15 do image:set(x, y, color) end
end
assets.add('/behaviorlab/jsonpath-result.png', image)
-- LAST: a swallowed postLoad error cannot look like a successful run.
assets.recordJsonPathLabProof({
  script = {
    query = {path = 'é[0].雪', value = value, rustCalls = queryCalls},
    missing = {path = 'missing', value = missing, rustCalls = missingCalls},
    malformed = {path = 'é[0x].雪', accepted = false, nativeErrorMatched = nativeErrorMatched, rustCalls = malformedCalls}
  },
  visual = {imagePath = '/behaviorlab/jsonpath-result.png', color = color, scale = scale, label = label}
})
