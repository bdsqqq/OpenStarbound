-- First uncached normal Assets JSON load. Native callback brackets parsing,
-- before explicit-length Lua conversion or any diagnostic JSON construction.
local input = assets.json('/behaviorlab/unicode-input.json')
local text = input.text
local expected = {0x41, 0xc3, 0xa9, 0xf0, 0x9f, 0x98, 0x80, 0, 0x5a}
assert(#text == 9 and input.label == 'UNICODE')
for i = 1, #expected do assert(string.byte(text, i) == expected[i]) end
local seed = assets.image('/objects/behaviorlab/constantlight/constantlight.png')
assert(seed:size()[1] == 8 and seed:size()[2] == 8)
seed = seed:subImage({0, 0}, {1, 1})
local image = seed:process('?scale=16')
assert(image:size()[1] == 16 and image:size()[2] == 16)
local color = {string.byte(text, 1), string.byte(text, 2), string.byte(text, 3), 255}
for y = 0, 15 do
  for x = 0, 15 do image:set(x, y, color) end
end
assets.add('/behaviorlab/unicode-result.png', image)
-- LAST: swallowed postLoad errors cannot manufacture a completed proof.
assets.recordUnicodeLabProof({visualColor = color, label = input.label})
