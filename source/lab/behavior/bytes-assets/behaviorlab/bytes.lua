-- Independent literal binary JSON, never serialized by a candidate formatter.
local path = '/opensb_data;json;BgMCP9AAAAAAAAACP-AAAAAAAAACP-gAAAAAAAA'
local before = assets.bytesLabCounts()
local values = assets.json(path)
local after = assets.bytesLabCounts()
local calls = {}
for i = 1, 6 do calls[i] = after[i] - before[i] end
assert(#values == 3 and values[1] == 0.25 and values[2] == 0.5 and values[3] == 0.75)
local seed = assets.image('/objects/behaviorlab/constantlight/constantlight.png')
assert(seed:size()[1] == 8 and seed:size()[2] == 8)
seed = seed:subImage({0, 0}, {1, 1})
local image = seed:process('?scale=16')
assert(image:size()[1] == 16 and image:size()[2] == 16)
local color = {math.floor(values[1] * 256), math.floor(values[2] * 256), math.floor(values[3] * 256), 255}
for y = 0, 15 do
  for x = 0, 15 do image:set(x, y, color) end
end
assets.add('/behaviorlab/bytes-result.png', image)
-- LAST: swallowed postLoad failures must not produce a completed proof.
assets.recordBytesLabProof({
  inputHex = '0603023fd0000000000000023fe0000000000000023fe8000000000000',
  values = values, rustCalls = calls, visualColor = color
})
