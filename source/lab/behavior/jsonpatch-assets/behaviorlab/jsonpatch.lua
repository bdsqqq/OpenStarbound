assert(assets.patch('/behaviorlab/jsonpatch-input.json', '/behaviorlab/jsonpatch-ops.json'))
assert(assets.patch('/behaviorlab/jsonpatch-input.json', '/behaviorlab/jsonpatch-rollback.json'))
-- Exactly one first uncached normal JSON load; native code owns its receipt.
local value = assets.json('/behaviorlab/jsonpatch-input.json')
local expected = sb.parseJson('{"a/b":{"~é":[64,128]},"items":[{"id":"x","n":10,"extra":true}],"visual":{"rgb":[64,128,192],"scale":4,"label":"PATCH"},"selected":{"id":"x","n":10,"extra":true},"picked":{"id":"b","n":2},"after":true}')
local function equal(a, b)
  if type(a) ~= type(b) then return false end
  if type(a) ~= 'table' then return a == b end
  for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
  for k, v in pairs(b) do if not equal(v, a[k]) then return false end end
  return true
end
assert(equal(value, expected), 'full jsonpatch result mismatch')
local visual = value.visual
local seed = assets.image('/objects/behaviorlab/constantlight/constantlight.png')
assert(seed:size()[1] == 8 and seed:size()[2] == 8)
local image = seed:subImage({0, 0}, {1, 1}):process('?scale=16')
assert(image:size()[1] == 16 and image:size()[2] == 16)
local color = {visual.rgb[1], visual.rgb[2], visual.rgb[3], 255}
for y = 0, 15 do
  for x = 0, 15 do image:set(x, y, color) end
end
assets.add('/behaviorlab/jsonpatch-result.png', image)
-- LAST: swallowed postLoad errors cannot publish completion.
assets.recordJsonPatchLabProof({
  imagePath = '/behaviorlab/jsonpatch-result.png',
  color = color, scale = visual.scale, label = visual.label
})
